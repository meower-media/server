package users

import (
	"context"
	"crypto/rand"

	"github.com/meower-media/server/pkg/db"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
)

var AccSessionSigningKey []byte
var EmailTicketSigningKey []byte

func InitTokenSigningKeys() error {
	var signingKeys struct {
		Id    string `bson:"_id"`
		Acc   []byte `bson:"acc"`
		Email []byte `bson:"email"`
	}
	err := db.Config.FindOne(context.TODO(), bson.M{"_id": "signing_keys"}).Decode(&signingKeys)
	if err == mongo.ErrNoDocuments {
		signingKeys.Id = "signing_keys"
		signingKeys.Acc = make([]byte, 64)
		signingKeys.Email = make([]byte, 64)
		if _, err := rand.Read(AccSessionSigningKey); err != nil {
			return err
		}
		if _, err := rand.Read(EmailTicketSigningKey); err != nil {
			return err
		}
		if _, err := db.Config.InsertOne(context.TODO(), signingKeys); err != nil {
			return err
		}
	} else if err != nil {
		return err
	} else {
		AccSessionSigningKey = signingKeys.Acc
		EmailTicketSigningKey = signingKeys.Email
	}

	return nil
}
