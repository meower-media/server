package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"github.com/getsentry/sentry-go"
	"github.com/joho/godotenv"
	"github.com/meower-media/server/pkg/api/rest"
	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/emails"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/rdb"
	"github.com/meower-media/server/pkg/users"
)

func main() {
	// Load dotenv
	godotenv.Load()

	// Init Sentry
	if err := sentry.Init(sentry.ClientOptions{
		Dsn: os.Getenv("SENTRY_DSN"),
	}); err != nil {
		panic(err)
	}

	// Init MeowID
	if err := meowid.Init(os.Getenv("NODE_ID")); err != nil {
		panic(err)
	}

	// Init MongoDB
	if err := db.Init(os.Getenv("MONGO_URI"), os.Getenv("MONGO_DB")); err != nil {
		panic(err)
	}

	// Init Redis
	if err := rdb.Init(os.Getenv("REDIS_URI")); err != nil {
		panic(err)
	}

	// Init token signing keys
	if err := users.InitTokenSigningKeys(); err != nil {
		panic(err)
	}

	// Send test email
	emails.SendEmail("verify", "Tnix", "test@tnix.dev", "abc123")

	// Serve HTTP router
	port := os.Getenv("HTTP_PORT")
	if port == "" {
		port = "3000"
	}
	log.Println("Serving HTTP server on :" + port)
	http.ListenAndServe(":"+port, rest.Router())

	// Wait for Sentry events to flush
	sentry.Flush(time.Second * 5)
}
