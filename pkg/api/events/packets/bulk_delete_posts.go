package packets

type V1BulkDeletePosts struct {
	ChatId  string   `json:"chat_id" msgpack:"chat_id"`
	StartId string   `json:"start_id" msgpack:"start_id"`
	EndId   string   `json:"end_id" msgpack:"end_id"`
	PostIds []string `json:"post_ids" msgpack:"post_ids"`
}
