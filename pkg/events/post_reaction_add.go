package events

import "github.com/meower-media-co/server/pkg/users"

type PostReactionAdd struct {
	ChatId int64      `msgpack:"chat_id"`
	PostId int64      `msgpack:"post_id"`
	Emoji  string     `msgpack:"emoji"`
	User   users.User `msgpack:"user"`
}
