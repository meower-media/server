package models

import (
	"strconv"

	"github.com/meower-media-co/server/pkg/chats"
)

type V0Emote struct {
	Id       string `json:"_id" msgpack:"_id"`
	ChatId   string `json:"chat_id" msgpack:"chat_id"`
	Name     string `json:"name" msgpack:"name"`
	Animated bool   `json:"animated" msgpack:"animated"`
}

func ConstructEmoteV0(e *chats.Emote) *V0Emote {
	return &V0Emote{
		Id:       strconv.FormatInt(e.Id, 10),
		ChatId:   strconv.FormatInt(e.ChatId, 10),
		Name:     e.Name,
		Animated: e.Animated,
	}
}
