package v0_rest

import (
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"
)

func Router() *chi.Mux {
	r := chi.NewRouter()

	r.Mount("/", RootRouter())
	r.Mount("/auth", AuthRouter())
	r.Mount("/me", MeRouter())
	r.Mount("/chats", ChatsRouter())
	r.Mount("/users/{username}", UsersRouter())

	// old endpoints
	r.Get("/home", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, fmt.Sprint("/chats/0/posts", "?", r.URL.RawQuery), http.StatusPermanentRedirect)
	})
	r.Post("/home/typing", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/chats/0/typing", http.StatusPermanentRedirect)
	})

	/*r.Route("/posts", func(r chi.Router) {
		r.Get("/", nil)
		r.Patch("/", nil)
		r.Delete("/", nil)
		r.Route("/{chatId}", func(r chi.Router) {
			r.Get("/", getChatPosts)
			r.Post("/", createChatPost)
		})
		r.Route("/{postId}", func(r chi.Router) {
			r.Delete("/attachments/{attachmentId}", nil)
			r.Post("/pin", nil)
			r.Delete("/pin", nil)
			r.Post("/report", reportChatPost)
			r.Get("/reactions/{emoji}", nil)
			r.Post("/reactions/{emoji}", nil)
			r.Delete("/reactions/{emoji}/{username}", nil)
		})
	})*/

	return r
}
