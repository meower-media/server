package structs

type V0ReactionIndex struct {
	Emoji       string `json:"emoji" msgpack:"emoji"`
	Count       int64  `json:"count" msgpack:"count"`
	UserReacted bool   `json:"user_reacted" msgpack:"user_reacted"`
}
