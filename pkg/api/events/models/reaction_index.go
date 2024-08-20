package models

import "github.com/meower-media-co/server/pkg/posts"

type V0ReactionIndex struct {
	Emoji       string `json:"emoji" msgpack:"emoji"`
	Count       int    `json:"count" msgpack:"count"`
	UserReacted bool   `json:"user_reacted" msgpack:"user_reacted"`
}

func ConstructReactionIndex(r *posts.ReactionIndex) *V0ReactionIndex {
	return &V0ReactionIndex{
		Emoji:       r.Emoji,
		Count:       r.Count,
		UserReacted: false,
	}
}
