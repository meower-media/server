package models

import (
	"strconv"

	"github.com/meower-media-co/server/pkg/users"
)

type V0User struct {
	Id           string  `json:"uuid" msgpack:"uuid"`
	Username     string  `json:"_id" msgpack:"_id"` // required for v0 and v1
	Flags        *int64  `json:"flags" msgpack:"flags"`
	Avatar       *string `json:"avatar" msgpack:"avatar"`
	LegacyAvatar *int8   `json:"pfp_data" msgpack:"pfp_data"`
	Color        *string `json:"avatar_color" msgpack:"avatar_color"`
	Quote        *string `json:"quote,omitempty" msgpack:"quote,omitempty"`
}

type V1User V0User

func ConstructUserV0(u *users.User) *V0User {
	if u == nil {
		u = &users.DeletedUser
	}

	return &V0User{
		Id:           strconv.FormatInt(u.Id, 10),
		Username:     u.Username,
		Flags:        u.Flags,
		Avatar:       u.Avatar,
		LegacyAvatar: u.LegacyAvatar,
		Color:        u.Color,
		Quote:        u.Quote,
	}
}
