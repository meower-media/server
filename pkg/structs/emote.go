package structs

type V0Emote struct {
	Id       string `json:"_id" msgpack:"_id"`
	ChatId   string `json:"chat_id" msgpack:"chat_id"`
	Name     string `json:"name" msgpack:"name"`
	Animated bool   `json:"animated" msgpack:"animated"`
}
