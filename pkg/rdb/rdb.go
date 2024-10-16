package rdb

import (
	"context"

	"github.com/redis/go-redis/v9"
)

var Client *redis.Client

func Init(uri string) error {
	// Get Redis options
	rdbOpts, err := redis.ParseURL(uri)
	if err != nil {
		return err
	}

	// Create Redis client
	Client = redis.NewClient(rdbOpts)

	// Ping Redis cluster
	if err := Client.Ping(context.Background()).Err(); err != nil {
		return err
	}

	return nil
}
