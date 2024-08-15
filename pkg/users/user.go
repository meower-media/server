package users

type User struct {
	Id       int64  `msgpack:"id"`
	Username string `msgpack:"username"` // required for v0 and v1 events

	Flags        *int64  `msgpack:"flags"`
	Avatar       *string `msgpack:"avatar"`
	LegacyAvatar *int8   `msgpack:"legacy_avatar"`
	Color        *string `msgpack:"color"`
	Quote        *string `msgpack:"quote"`
}
