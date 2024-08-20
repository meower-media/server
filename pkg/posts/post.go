package posts

import "github.com/meower-media-co/server/pkg/meowid"

type Post struct {
	Id              meowid.MeowID    `msgpack:"id"`
	ChatId          meowid.MeowID    `msgpack:"chat_id"` // 0: home, 1: livechat, 2: inbox
	AuthorId        *meowid.MeowID   `msgpack:"author_id"`
	ReplyToIds      *[]meowid.MeowID `msgpack:"reply_to_ids"`
	Content         *string          `msgpack:"content"`
	EmojiIds        *[]string        `msgpack:"emoji_ids"`
	StickerIds      *[]string        `msgpack:"sticker_ids"`
	AttachmentIds   *[]string        `msgpack:"attachment_ids"`
	ReactionIndexes *[]ReactionIndex `msgpack:"reactions"`
	LastEdited      *int64           `msgpack:"last_edited"`
	Pinned          *bool            `msgpack:"pinned"`
}
