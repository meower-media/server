package events

import (
	"github.com/meower-media/server/pkg/chats"
	"github.com/meower-media/server/pkg/posts"
	"github.com/meower-media/server/pkg/users"
)

type UpdatePost struct {
	Post        posts.Post                   `msgpack:"post"`
	ReplyTo     map[int64]*posts.Post        `msgpack:"reply_to"`
	Users       map[int64]*users.User        `msgpack:"users"`
	Emotes      map[string]*chats.Emote      `msgpack:"emotes"`
	Attachments map[string]*posts.Attachment `msgpack:"attachments"`
}
