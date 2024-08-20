package packets

type V0DeletePost struct {
	Mode   string `json:"mode" msgpack:"mode"` // will always be 'delete'
	PostId string `json:"id" msgpack:"id"`
}

type V1DeletePost struct {
	ChatId string `json:"chat_id" msgpack:"chat_id"`
	PostId string `json:"post_id" msgpack:"post_id"`
}
