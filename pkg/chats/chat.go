package chats

type Chat struct {
	Id       int64  `msgpack:"id"`
	Type     int8   `msgpack:"type"`
	Nickname string `msgpack:"nickname"`
}
