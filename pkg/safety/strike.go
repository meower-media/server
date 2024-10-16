package safety

import (
	"context"
	"time"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"go.mongodb.org/mongo-driver/bson"
)

type Strike struct {
	Id      meowid.MeowID `bson:"_id" msgpack:"id"`
	UserId  meowid.MeowID `bson:"user" msgpack:"user"`
	Reason  string        `bson:"reason" msgpack:"reason"`
	Content Snapshot      `bson:"content" msgpack:"content"`

	/*
		A strike can have an impact of warning, restriction, or ban.

		Warning carries no additional punishment.

		Restriction blocks the user from starting new chats, joining public chats, and editing their profile.

		Ban blocks the user from logging in.
	*/
	Impact string `bson:"impact" msgpack:"impact"`

	ExpiresAt int64 `bson:"expires" msgpack:"expires"` // -1 for permanent
}

func GetActiveStrikes(userId meowid.MeowID) ([]Strike, error) {
	var strikes []Strike

	cur, err := db.Strikes.Find(
		context.TODO(),
		bson.M{
			"user": userId,
			"$or": []bson.M{
				{"expires": -1},
				{"expires": bson.M{"$gt": time.Now().UnixMilli()}},
			},
		},
	)
	if err != nil {
		return strikes, err
	}

	err = cur.All(context.TODO(), &strikes)
	return strikes, err
}
