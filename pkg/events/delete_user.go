package events

import (
	"github.com/meower-media-co/server/pkg/meowid"
)

type DeleteUser struct {
	UserId meowid.MeowID `msgpack:"user_id"`
}
