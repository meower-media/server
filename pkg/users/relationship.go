package users

import (
	"context"
	"time"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/structs"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

const (
	RelationshipStateNone                  int8 = 0
	RelationshipStateFollowing             int8 = 1
	RelationshipStateBlocked               int8 = 2
	RelationshipStateOutgoingFriendRequest int8 = 3
	RelationshipStateIncomingFriendRequest int8 = 4
	RelationshipStateFriend                int8 = 5
)

type Relationship struct {
	Id        RelationshipIdCompound `bson:"_id" msgpack:"id"`
	State     int8                   `bson:"state" msgpack:"state"`
	UpdatedAt int64                  `bson:"updated_at" msgpack:"updated_at"`
}

type RelationshipIdCompound struct {
	From meowid.MeowID `bson:"from" msgpack:"from"`
	To   meowid.MeowID `bson:"to" msgpack:"to"`
}

func (u *User) GetRelationship(toId meowid.MeowID) (Relationship, error) {
	var relationship Relationship
	err := db.Relationships.FindOne(
		context.TODO(),
		bson.M{"_id": RelationshipIdCompound{
			From: u.Id,
			To:   toId,
		}},
	).Decode(&relationship)
	if err == mongo.ErrNoDocuments {
		err = nil
	}
	return relationship, err
}

func (u *User) GetAllRelationships() ([]Relationship, error) {
	relationships := []Relationship{}

	cur, err := db.Relationships.Find(context.TODO(), bson.M{"_id.from": u.Id})
	if err != nil {
		return relationships, err
	}

	err = cur.All(context.TODO(), &relationships)
	if err != nil {
		return relationships, err
	}

	return relationships, nil
}

func (r *Relationship) V0() (structs.V0Relationship, error) {
	v0r := structs.V0Relationship{
		State:     r.State,
		UpdatedAt: r.UpdatedAt / 1000,
	}
	var err error
	v0r.Username, err = GetUsername(r.Id.To)
	return v0r, err
}

func (r *Relationship) Update(state int8) error {
	r.State = state
	r.UpdatedAt = time.Now().UnixMilli()

	if r.State == 0 {
		if _, err := db.Relationships.DeleteOne(context.TODO(), bson.M{"_id": r.Id}); err != nil {
			return err
		}
	} else {
		opts := options.UpdateOptions{}
		opts.SetUpsert(true)
		if _, err := db.Relationships.UpdateByID(
			context.TODO(),
			r.Id,
			bson.M{"$set": bson.M{
				"state":      r.State,
				"updated_at": r.UpdatedAt,
			}},
			&opts,
		); err != nil {
			return err
		}
	}

	return nil
}
