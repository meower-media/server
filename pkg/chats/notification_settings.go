package chats

type NotificationSettings struct {
	Mode       int8  `bson:"mode,omitempty" msgpack:"mode,omitempty"` // 2: all, 1: mentions, 0: none
	Push       bool  `bson:"push,omitempty" msgpack:"push,omitempty"`
	MutedUntil int64 `bson:"muted_until,omitempty" msgpack:"muted_until,omitempty"` // -1 for permanent mute
}
