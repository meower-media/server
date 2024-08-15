package posts

type Reaction struct {
	PostId int64  `msgpack:"post_id"`
	Emoji  string `msgpack:"emoji"`
	UserId int64  `msgpack:"user_id"`
}
