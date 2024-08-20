package events

type BulkDeletePosts struct {
	ChatId  int64   `msgpack:"chat_id"`
	StartId int64   `msgpack:"start_id"`
	EndId   int64   `msgpack:"end_id"`
	PostIds []int64 `msgpack:"post_ids"`
}
