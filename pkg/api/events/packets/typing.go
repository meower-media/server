package packets

import "github.com/meower-media/server/pkg/api/events/models"

type V0Typing struct {
	ChatId   string `json:"chatid" msgpack:"chatid"`
	State    int8   `json:"state" msgpack:"state"` // 100 for chats, 101 in 'livechat' for home
	Username string `json:"u" msgpack:"u"`
}

type V1Typing struct {
	ChatId   string         `json:"chat_id" msgpack:"chat_id"`
	User     *models.V0User `json:"user" msgpack:"user"`
	Username string         `json:"username" msgpack:"username"`
}
