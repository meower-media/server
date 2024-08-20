package main

import (
	"log"
	"os"

	"github.com/getsentry/sentry-go"
	"github.com/joho/godotenv"
	"github.com/meower-media-co/server/pkg/api/events"
)

func main() {
	// Load dotenv
	godotenv.Load()

	// Initialise Sentry
	sentry.Init(sentry.ClientOptions{
		Dsn: os.Getenv("EVENTS_SENTRY_DSN"),
	})

	// Get expose address
	exposeAddr := os.Getenv("EVENTS_ADDRESS")
	if exposeAddr == "" {
		exposeAddr = ":3000"
	}

	// Create & run server
	server := events.NewServer()
	err := server.Run(exposeAddr)
	if err != nil {
		log.Fatalln(err)
	}
}
