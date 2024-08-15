package packets

import "github.com/meower-media-co/server/pkg/api/events/models"

type V0CreatePost struct {
	Mode  int `json:"mode,omitempty" msgpack:"mode,omitempty"`   // will be 1 for home posts, otherwise will be absent
	State int `json:"state,omitempty" msgpack:"state,omitempty"` // will be 2 for chat posts, otherwise will be absent
	*models.V0Post
}

type V1CreatePost V0CreatePost
