package posts

import (
	"context"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"go.mongodb.org/mongo-driver/mongo"
)

type Reaction struct {
	PostId int64  `bson:"post" msgpack:"post"`
	Emoji  string `bson:"emoji" msgpack:"emoji"`
	UserId int64  `bson:"user" msgpack:"user"`
}

func (p *Post) AddPostReaction(emoji string, userId meowid.MeowID) (Reaction, error) {
	// Add reaction
	r := Reaction{
		PostId: p.Id,
		Emoji:  emoji,
		UserId: userId,
	}
	_, err := db.PostReactions.InsertOne(context.TODO(), r)
	if mongo.IsDuplicateKeyError(err) {
		err = ErrReactionAlreadyExists
	}

	// Update index in background
	go func() {}()

	return r, err
}
