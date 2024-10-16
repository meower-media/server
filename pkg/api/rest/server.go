package rest

import (
	"net"
	"net/http"
	"os"

	"github.com/go-chi/chi/v5"
	v0_rest "github.com/meower-media/server/pkg/api/rest/v0"
	"github.com/rs/cors"
)

var realIPHeader = os.Getenv("REAL_IP_HEADER")

func Router() *chi.Mux {
	r := chi.NewRouter()

	// CORS middleware
	r.Use(cors.New(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"OPTIONS", "GET", "POST", "PATCH", "PUT", "DELETE"},
		AllowedHeaders:   []string{"*"},
		AllowCredentials: true,
	}).Handler)

	// IP address middleware
	r.Use(func(h http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if realIPHeader != "" {
				r.RemoteAddr = r.Header.Get(realIPHeader)
			} else {
				r.RemoteAddr, _, _ = net.SplitHostPort(r.RemoteAddr)
			}
			h.ServeHTTP(w, r)
		})
	})

	// Mount routers
	r.Mount("/", v0_rest.Router())  // default
	r.Mount("//", v0_rest.Router()) // Meower Svelte sometimes puts 2 slashes at the start and chi doesn't like that ._.
	r.Mount("/v0", v0_rest.Router())

	return r
}
