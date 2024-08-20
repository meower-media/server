package chats

type Emote struct {
	Id        int64  `msgpack:"id"`
	ChatId    int64  `msgpack:"chat_id"`
	Name      string `msgpack:"name"`
	Animated  bool   `msgpack:"animated"`
	CreatorId int64  `msgpack:"creator_id,omitempty"`
}
