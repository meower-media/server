package events

type DeletePost struct {
	ChatId int64 `msgpack:"chat_id"`
	PostId int64 `msgpack:"post_id"`
}
