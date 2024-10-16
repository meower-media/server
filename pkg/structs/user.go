package structs

type V0User struct {
	Id         string  `json:"uuid" msgpack:"uuid"`
	Username   string  `json:"_id" msgpack:"_id"`
	Flags      int64   `json:"flags" msgpack:"flags"`
	IconId     string  `json:"avatar" msgpack:"avatar"`
	LegacyIcon *int8   `json:"pfp_data" msgpack:"pfp_data"`
	Color      *string `json:"avatar_color" msgpack:"avatar_color"`

	Email       *string `json:"email,omitempty" msgpack:"email,omitempty"`
	Permissions *int64  `json:"permissions,omitempty" msgpack:"permissions,omitempty"`
	Quote       *string `json:"quote,omitempty" msgpack:"quote,omitempty"`
	LastSeenAt  *int64  `json:"last_seen,omitempty" msgpack:"last_seen,omitempty"`

	V0UserSettings
}
