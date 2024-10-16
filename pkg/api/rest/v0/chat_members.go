package v0_rest

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/meower-media/server/pkg/chats"
	"github.com/meower-media/server/pkg/users"
)

func ChatMembersRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Get("/", nil)
	r.Post("/bulk-remove", nil)

	r.Get("/{username}", nil)
	r.Put("/{username}", createMember)
	r.Patch("/{username}", nil)
	r.Delete("/{username}", nil)

	// deprecated
	r.Post("/{username}/transfer", nil)

	return r
}

func createMember(w http.ResponseWriter, r *http.Request) {
	var key CtxKey = "chat"
	chat := r.Context().Value(key).(*chats.Chat)

	reqedUser, err := getUserByUrlParam(r, "username")
	if err != nil {
		if err == users.ErrUserNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	_, err = chat.CreateMember(
		reqedUser.Id,
		false,
		false,
		2,
		false,
	)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}
