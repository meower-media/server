package events

import "github.com/meower-media-co/server/pkg/users"

type CreateUser struct {
	User users.User `msgpack:"user"`
}
