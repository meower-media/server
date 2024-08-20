package models

import (
	"strconv"

	"github.com/meower-media-co/server/pkg/chats"
	"github.com/meower-media-co/server/pkg/meowid"
	"github.com/meower-media-co/server/pkg/posts"
	"github.com/meower-media-co/server/pkg/users"
)

type V0Post struct {
	Id             string    `json:"_id" msgpack:"_id"`
	PostId         string    `json:"post_id" msgpack:"post_id"`
	ChatId         string    `json:"post_origin" msgpack:"post_origin"`
	Type           int8      `json:"type" msgpack:"type"` // 1 for regular posts, 2 for inbox posts
	Author         *V0User   `json:"author" msgpack:"author"`
	AuthorUsername string    `json:"u" msgpack:"u"`
	ReplyTo        []*V0Post `json:"reply_to" msgpack:"reply_to"`
	Timestamp      struct {
		Unix int64 `json:"e" msgpack:"e"`
	} `json:"t" msgpack:"t"`
	Content         string             `json:"p" msgpack:"p"`
	Emojis          []*V0Emote         `json:"emojis" msgpack:"emojis"`
	Stickers        []*V0Emote         `json:"stickers" msgpack:"stickers"`
	Attachments     []*V0Attachment    `json:"attachments" msgpack:"attachments"`
	ReactionIndexes []*V0ReactionIndex `json:"reactions" msgpack:"reactions"`
	LastEdited      *int64             `json:"last_edited,omitempty" msgpack:"last_edited,omitempty"`
	Pinned          *bool              `json:"pinned,omitempty" msgpack:"pinned,omitempty"`
	Deleted         bool               `json:"isDeleted" msgpack:"isDeleted"`

	Nonce string `json:"nonce,omitempty" msgpack:"nonce,omitempty"`
}

type V1Post = V0Post

func ConstructPostV0(
	p *posts.Post,
	users map[int64]*users.User,
	replyTo map[int64]*posts.Post,
	emotes map[string]*chats.Emote,
	attachments map[string]*posts.Attachment,
) *V0Post {
	if p == nil {
		return nil
	}

	v0p := &V0Post{
		Id:      strconv.FormatInt(p.Id, 10),
		PostId:  strconv.FormatInt(p.Id, 10),
		ChatId:  strconv.FormatInt(p.ChatId, 10),
		Type:    1,
		ReplyTo: []*V0Post{},
		Timestamp: struct {
			Unix int64 "json:\"e\" msgpack:\"e\""
		}{Unix: meowid.Extract(p.Id).Timestamp},
		Content:         *p.Content,
		Emojis:          []*V0Emote{},
		Stickers:        []*V0Emote{},
		Attachments:     []*V0Attachment{},
		ReactionIndexes: []*V0ReactionIndex{},
		LastEdited:      p.LastEdited,
		Pinned:          p.Pinned,
	}
	if v0p.ChatId == "0" {
		v0p.ChatId = "home"
	} else if v0p.ChatId == "1" {
		v0p.ChatId = "livechat"
	}
	if p.AuthorId != nil {
		v0p.Author = ConstructUserV0(users[*p.AuthorId])
		v0p.AuthorUsername = v0p.Author.Username
	}
	if p.ReplyToIds != nil {
		for _, replyToId := range *p.ReplyToIds {
			v0p.ReplyTo = append(
				v0p.ReplyTo,
				ConstructPostV0(
					replyTo[replyToId],
					users,
					make(map[int64]*posts.Post, 0),
					emotes,
					attachments,
				),
			)
		}
	}
	if p.EmojiIds != nil {
		for _, emojiId := range *p.EmojiIds {
			v0p.Emojis = append(v0p.Emojis, ConstructEmoteV0(emotes[emojiId]))
		}
	}
	if p.StickerIds != nil {
		for _, stickerId := range *p.StickerIds {
			v0p.Stickers = append(v0p.Stickers, ConstructEmoteV0(emotes[stickerId]))
		}
	}
	if p.AttachmentIds != nil {
		for _, attachmentId := range *p.AttachmentIds {
			v0p.Attachments = append(v0p.Attachments, ConstructAttachmentV0(attachments[attachmentId]))
		}
	}
	if p.ReactionIndexes != nil {
		for _, reactionIndex := range *p.ReactionIndexes {
			v0p.ReactionIndexes = append(v0p.ReactionIndexes, ConstructReactionIndex(&reactionIndex))
		}
	}

	return v0p
}
