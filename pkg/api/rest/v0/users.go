package v0_rest

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/meower-media/server/pkg/chats"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/posts"
	"github.com/meower-media/server/pkg/safety"
	"github.com/meower-media/server/pkg/structs"
	"github.com/meower-media/server/pkg/users"
)

func UsersRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Get("/", getUser)
	r.Get("/posts", getUserPosts)
	r.Get("/relationship", getRelationship)
	r.Patch("/relationship", updateRelationship)
	r.Get("/dm", getDMChat)
	r.Post("/report", reportUser)

	return r
}

func getUser(w http.ResponseWriter, r *http.Request) {
	reqedUser, err := getUserByUrlParam(r, "username")
	if err != nil {
		if err == users.ErrUserNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	returnData(w, http.StatusOK, reqedUser.V0(false, false))
}

func getUserPosts(w http.ResponseWriter, r *http.Request) {
	reqedUser, err := getUserByUrlParam(r, "username")
	if err != nil {
		if err == users.ErrUserNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	var requesterId meowid.MeowID
	authedUser := getAuthedUser(r, nil)
	if authedUser != nil {
		requesterId = authedUser.Id
	}

	// Get pagination opts
	paginationOpts := PaginationOpts{Request: r}

	// Get posts
	posts, err := posts.GetPosts(reqedUser.Id, false, paginationOpts)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	v0posts := []structs.V0Post{}
	for _, p := range posts {
		v0posts = append(v0posts, p.V0(true, &requesterId))
	}

	returnData(w, http.StatusOK, ListResp{
		Autoget: v0posts,
	})
}

func getRelationship(w http.ResponseWriter, r *http.Request) {
	reqedUser, err := getUserByUrlParam(r, "username")
	if err != nil {
		if err == users.ErrUserNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	relationship, err := authedUser.GetRelationship(reqedUser.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	relationshipV0, err := relationship.V0()
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, relationshipV0)
}

func updateRelationship(w http.ResponseWriter, r *http.Request) {
	var body UpdateRelationshipReq
	if !decodeBody(w, r, &body) {
		return
	}

	reqedUser, err := getUserByUrlParam(r, "username")
	if err != nil {
		if err == users.ErrUserNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	relationship, err := authedUser.GetRelationship(reqedUser.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	if err := relationship.Update(*body.State); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	relationshipV0, err := relationship.V0()
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, relationshipV0)
}

func getDMChat(w http.ResponseWriter, r *http.Request) {
	reqedUser, err := getUserByUrlParam(r, "username")
	if err != nil {
		if err == users.ErrUserNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	chat, err := chats.GetDM(authedUser.Id, reqedUser.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, chat.V0(*authedUser))
}

func reportUser(w http.ResponseWriter, r *http.Request) {
	var body CreateReportReq
	if !decodeBody(w, r, &body) {
		return
	}
	if body.Reason == "" {
		body.Reason = "No reason provided"
	}

	reqedUser, err := getUserByUrlParam(r, "username")
	if err != nil {
		if err == users.ErrUserNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	report, err := safety.CreateReport("user", reqedUser.Id, authedUser.Id, body.Reason, body.Comment)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, report.V0())
}
