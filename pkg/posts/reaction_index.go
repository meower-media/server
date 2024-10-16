package posts

import (
	"context"

	"github.com/getsentry/sentry-go"
	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/structs"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo/options"
)

type ReactionIndex struct {
	Emoji string `bson:"emoji" msgpack:"emoji"`
	Count int64  `bson:"count" msgpack:"count"`
}

func (ri *ReactionIndex) V0(postId meowid.MeowID, requesterId *meowid.MeowID) structs.V0ReactionIndex {
	var userReacted bool
	if requesterId != nil {
		q := bson.M{"_id": bson.M{
			"post":  postId,
			"emoji": ri.Emoji,
			"user":  requesterId,
		}}
		opts := options.CountOptions{}
		opts.SetLimit(1)
		count, err := db.PostReactions.CountDocuments(context.TODO(), q, &opts)
		if err != nil {
			sentry.CaptureException(err)
		}
		userReacted = count > 0
	}
	return structs.V0ReactionIndex{
		Emoji:       ri.Emoji,
		Count:       ri.Count,
		UserReacted: userReacted,
	}
}
