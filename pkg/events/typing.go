package events

import "github.com/meower-media-co/server/pkg/users"

type Typing struct {
	ChatId int64      `msgpack:"chat_id"`
	User   users.User `msgpack:"user"`
}
