package v0_rest

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/meower-media/server/pkg/chats"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/posts"
	"github.com/meower-media/server/pkg/safety"
	"github.com/meower-media/server/pkg/structs"
)

func ChatPostsRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Get("/", getChatPosts)
	r.Post("/", createChatPost)
	r.Get("/pins", getChatPosts)
	r.Get("/search", nil)
	r.Post("/bulk-delete", nil)

	// The following endpoints should get the chat ID from the database
	// using the post ID. As the request may be coming from a path that doesn't
	// include the chat ID.
	r.Route("/{postId}", func(r chi.Router) {
		r.Get("/", getChatPost)
		r.Patch("/", updateChatPost)
		r.Delete("/", deleteChatPost)

		r.Delete("/attachments/{attachmentId}", removeChatPostAttachment)

		r.Post("/pin", pinChatPost)
		r.Delete("/pin", unpinChatPost)

		r.Post("/report", reportChatPost)

		r.Route("/reactions/{emoji}", func(r chi.Router) {
			r.Get("/", nil)
			r.Post("/", nil)
			r.Delete("/{username}", nil)
		})
	})

	return r
}

func getChatPosts(w http.ResponseWriter, r *http.Request) {
	// Get user and chat
	var key CtxKey = "user"
	//user := r.Context().Value(key).(users.User)
	key = "chat"
	chat := r.Context().Value(key).(*chats.Chat)

	// Get pagination opts
	paginationOpts := PaginationOpts{Request: r}

	// Get posts
	posts, err := posts.GetPosts(chat.Id, strings.HasSuffix(r.URL.Path, "/pins"), paginationOpts)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Parse posts
	v0posts := []structs.V0Post{}
	var requesterUserId *meowid.MeowID
	for _, p := range posts {
		v0posts = append(v0posts, p.V0(true, requesterUserId))
	}

	// Get pages
	pages := paginationOpts.Page()
	if len(posts) != 0 {
		pages++
	}

	returnData(w, http.StatusOK, ListResp{
		Autoget: v0posts,
		Page:    paginationOpts.Page(),
		Pages:   pages,
	})
}

func createChatPost(w http.ResponseWriter, r *http.Request) {
	// Get chat ID
	var chatId meowid.MeowID
	if r.URL.Path != "/home" && r.URL.Path != "/v0/home" {
		var err error
		chatId, err = strconv.ParseInt(chi.URLParam(r, "chatId"), 10, 64)
		if err != nil {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}
	}

	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Decode body
	var body CreatePostReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Parse reply to post IDs
	replyToPostIds := []meowid.MeowID{}
	for _, strPostId := range body.ReplyToPostIds {
		postId, err := strconv.ParseInt(strPostId, 10, 64)
		if err != nil {
			return
		}
		replyToPostIds = append(replyToPostIds, postId)
	}

	// Create post
	post, err := posts.CreatePost(
		chatId,
		authedUser.Id,
		replyToPostIds,
		body.Content,
		body.StickerIds,
		body.AttachmentIds,
		body.Nonce,
	)
	if err != nil {
		return
	}

	returnData(w, http.StatusOK, post.V0(true, &authedUser.Id))
}

func reportChatPost(w http.ResponseWriter, r *http.Request) {
	// Decode body
	var body CreateReportReq
	if !decodeBody(w, r, &body) {
		return
	}
	if body.Reason == "" {
		body.Reason = "No reason provided"
	}

	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get post ID
	postId, err := strconv.ParseInt(chi.URLParam(r, "postId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Create report
	report, err := safety.CreateReport("post", postId, authedUser.Id, body.Reason, body.Comment)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, report.V0())
}

func getChatPost(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get post ID
	postId, err := strconv.ParseInt(chi.URLParam(r, "postId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get post
	post, err := posts.GetPost(postId)
	if err != nil {
		if err == posts.ErrPostNotFound {
			returnErr(w, http.StatusNotFound, ErrInternal, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	returnData(w, http.StatusOK, post.V0(true, &authedUser.Id))
}

func updateChatPost(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get post ID
	postId, err := strconv.ParseInt(chi.URLParam(r, "postId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get post
	post, err := posts.GetPost(postId)
	if err != nil {
		if err == posts.ErrPostNotFound {
			returnErr(w, http.StatusNotFound, ErrInternal, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	// Validate ownership
	if post.AuthorId != authedUser.Id {
		returnErr(w, http.StatusForbidden, ErrMissingPermissions, nil)
		return
	}

	// Decode body
	var body CreatePostReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Update post
	if err := post.UpdateContent(body.Content); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, post.V0(true, &authedUser.Id))
}

func deleteChatPost(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get post ID
	postId, err := strconv.ParseInt(chi.URLParam(r, "postId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get post
	post, err := posts.GetPost(postId)
	if err != nil {
		if err == posts.ErrPostNotFound {
			returnErr(w, http.StatusNotFound, ErrInternal, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	// Validate ownership
	if post.AuthorId != authedUser.Id {
		returnErr(w, http.StatusForbidden, ErrMissingPermissions, nil)
		return
	}

	// Delete post
	if err := post.Delete(true); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}

func removeChatPostAttachment(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get post ID
	postId, err := strconv.ParseInt(chi.URLParam(r, "postId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get post
	post, err := posts.GetPost(postId)
	if err != nil {
		if err == posts.ErrPostNotFound {
			returnErr(w, http.StatusNotFound, ErrInternal, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	// Validate ownership
	if post.AuthorId != authedUser.Id {
		returnErr(w, http.StatusForbidden, ErrMissingPermissions, nil)
		return
	}

	// Remove attachment
	if err := post.RemoveAttachment(chi.URLParam(r, "attachmentId")); err != nil {
		if err == posts.ErrAttachmentNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	returnData(w, http.StatusOK, post.V0(true, &authedUser.Id))
}

func pinChatPost(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get post ID
	postId, err := strconv.ParseInt(chi.URLParam(r, "postId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get post
	post, err := posts.GetPost(postId)
	if err != nil {
		if err == posts.ErrPostNotFound {
			returnErr(w, http.StatusNotFound, ErrInternal, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	// Pin post
	if err := post.SetPinnedState(true); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}

func unpinChatPost(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get post ID
	postId, err := strconv.ParseInt(chi.URLParam(r, "postId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get post
	post, err := posts.GetPost(postId)
	if err != nil {
		if err == posts.ErrPostNotFound {
			returnErr(w, http.StatusNotFound, ErrInternal, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	// Unpin post
	if err := post.SetPinnedState(false); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}
