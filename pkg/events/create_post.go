package events

import (
	"github.com/meower-media-co/server/pkg/chats"
	"github.com/meower-media-co/server/pkg/meowid"
	"github.com/meower-media-co/server/pkg/posts"
	"github.com/meower-media-co/server/pkg/users"
)

type CreatePost struct {
	Post        posts.Post                   `msgpack:"post"`
	ReplyTo     map[int64]*posts.Post        `msgpack:"reply_to"`
	Users       map[int64]*users.User        `msgpack:"users"`
	Emotes      map[string]*chats.Emote      `msgpack:"emotes"`
	Attachments map[string]*posts.Attachment `msgpack:"attachments"`

	// will only be added if the post was sent in a DM
	// if the DM is not open for the client, we will open it for them
	// before sending the post
	DMToId *meowid.MeowID `msgpack:"dm_to"`
	DMChat *interface{}   `msgpack:"dm_chat"`

	Nonce string `msgpack:"nonce,omitempty"`
}
