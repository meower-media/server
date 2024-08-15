package rdb

import (
	"context"
	"log"
	"os"

	"github.com/redis/go-redis/v9"
)

var Client *redis.Client

func init() {
	// Get Redis options
	rdbOpts, err := redis.ParseURL(os.Getenv("REDIS_URI"))
	if err != nil {
		log.Fatalln(err)
	}

	// Create Redis client
	Client = redis.NewClient(rdbOpts)

	// Ping Redis cluster
	status := Client.Ping(context.Background())
	if status.Err() != nil {
		log.Fatalln(err)
	}
}
