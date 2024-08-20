package events

import "github.com/meower-media-co/server/pkg/users"

type UpdateRelationship struct {
	From      users.User `msgpack:"from"`
	To        users.User `msgpack:"to"`
	State     int8       `msgpack:"state"`
	UpdatedAt int64      `msgpack:"updated_at"`
}
