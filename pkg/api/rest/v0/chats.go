package v0_rest

import (
	"context"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/meower-media/server/pkg/chats"
	"github.com/meower-media/server/pkg/structs"
	"github.com/meower-media/server/pkg/users"
)

func ChatsRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Get("/", getChats)
	r.Post("/", createGroupChat)

	r.Route("/{chatId}", func(r chi.Router) {
		r.Use(func(h http.Handler) http.Handler {
			return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				ctx := r.Context()

				// Get authed user
				user := getAuthedUser(r, nil)
				if user == nil {
					returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
					return
				}
				var key CtxKey = "user"
				ctx = context.WithValue(ctx, key, &user)

				// Get chat ID
				chatId, err := strconv.ParseInt(chi.URLParam(r, "chatId"), 10, 64)
				if err != nil {
					returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
					return
				}

				// Get chat
				chat, err := chats.GetChat(chatId)
				if err != nil {
					returnErr(w, http.StatusNotFound, ErrNotFound, nil)
					return
				}
				key = "chat"
				ctx = context.WithValue(ctx, key, &chat)

				// Get member
				member, err := chat.GetMember(user.Id)
				if err != nil {
					returnErr(w, http.StatusNotFound, ErrNotFound, nil)
					return
				}
				key = "member"
				ctx = context.WithValue(ctx, key, &member)

				h.ServeHTTP(w, r.WithContext(ctx))
			})
		})

		r.Get("/", getChat)
		r.Patch("/", nil)
		r.Delete("/", leaveChat)
		r.Post("/typing", emitTyping)
		r.Post("/delete", deleteChat)
		r.Mount("/members", ChatMembersRouter())
		r.Mount("/{emoteType:emojis|stickers}", ChatEmotesRouter())
		r.Mount("/posts", ChatPostsRouter())

		r.Get("/pins", getChatPosts) // deprecated
	})

	return r
}

func getChats(w http.ResponseWriter, r *http.Request) {
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	chats, err := chats.GetActiveChats(user.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Parse chats
	v0chats := []structs.V0Chat{}
	for _, c := range chats {
		v0chats = append(v0chats, c.V0(*user))
	}

	returnData(w, http.StatusOK, ListResp{
		Autoget: v0chats,
		Page:    1,
		Pages:   1,
	})
}

func createGroupChat(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Decode body
	var body CreateGroupChatReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Create group chat
	chat, err := chats.CreateGroupChat(body.Nickname, "", "")
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Create chat membership
	_, err = chat.CreateMember(user.Id, false, true, 2, true)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, chat.V0(*user))
}

func getChat(w http.ResponseWriter, r *http.Request) {
	var key CtxKey = "user"
	user := r.Context().Value(key).(*users.User)

	key = "chat"
	chat := r.Context().Value(key).(*chats.Chat)

	returnData(w, http.StatusOK, chat.V0(*user))
}

func leaveChat(w http.ResponseWriter, r *http.Request) {
	var key CtxKey = "member"
	member := r.Context().Value(key).(*chats.Member)

	var err error
	if member.DM {
		err = member.SetActiveStatus(false)
	} else {
		err = member.Delete()
	}
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}

func emitTyping(w http.ResponseWriter, r *http.Request) {
	var key CtxKey = "member"
	if err := r.Context().Value(key).(*chats.Member).EmitTyping(); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}
	returnData(w, http.StatusOK, BaseResp{})
}

func deleteChat(w http.ResponseWriter, r *http.Request) {
	var key CtxKey = "member"
	if !r.Context().Value(key).(*chats.Member).Admin {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	key = "chat"
	if err := r.Context().Value(key).(*chats.Chat).Delete(); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}
