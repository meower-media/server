package structs

type V0Post struct {
	Id              string            `json:"_id" msgpack:"_id"`
	PostId          string            `json:"post_id" msgpack:"post_id"`
	ChatId          string            `json:"post_origin" msgpack:"post_origin"`
	Type            int8              `json:"type" msgpack:"type"` // 1 for regular posts, 2 for inbox posts
	Author          V0User            `json:"author" msgpack:"author"`
	AuthorUsername  string            `json:"u" msgpack:"u"`
	ReplyTo         []*V0Post         `json:"reply_to" msgpack:"reply_to"`
	Timestamp       V0PostTimestamp   `json:"t" msgpack:"t"`
	Content         string            `json:"p" msgpack:"p"`
	Emojis          []*V0Emote        `json:"emojis" msgpack:"emojis"`
	Stickers        []*V0Emote        `json:"stickers" msgpack:"stickers"`
	Attachments     []interface{}     `json:"attachments" msgpack:"attachments"`
	ReactionIndexes []V0ReactionIndex `json:"reactions" msgpack:"reactions"`
	Pinned          bool              `json:"pinned" msgpack:"pinned"`
	LastEditedAt    *int64            `json:"last_edited,omitempty" msgpack:"last_edited,omitempty"`

	Nonce string `json:"nonce,omitempty" msgpack:"nonce,omitempty"`

	// deprecated
	Deleted bool `json:"isDeleted" msgpack:"isDeleted"`
}

type V0PostTimestamp struct {
	Unix int64 `json:"e" msgpack:"e"`
}
