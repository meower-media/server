package packets

import "github.com/meower-media-co/server/pkg/api/events/models"

type V0UpdateRelationship struct {
	User      *models.V0User `json:"user" msgpack:"user"`
	Username  string         `json:"username" msgpack:"username"`
	State     int8           `json:"state" msgpack:"state"`
	UpdatedAt int64          `json:"updated_at" msgpack:"updated_at"`
}

type V1UpdateRelationship = V0UpdateRelationship
