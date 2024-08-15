package events

import "github.com/meower-media-co/server/pkg/users"

type UpdateUser struct {
	User users.User `msgpack:"user"`
}
