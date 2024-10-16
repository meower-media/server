package files

import (
	"context"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"go.mongodb.org/mongo-driver/bson"
)

type File struct {
	Id           string        `bson:"_id" msgpack:"id"`
	Bucket       string        `bson:"bucket" msgpack:"bucket"`
	Hash         string        `bson:"hash" msgpack:"hash"`
	Mime         string        `bson:"mime" msgpack:"mime"`
	Filename     string        `bson:"filename,omitempty" msgpack:"filename,omitempty"`
	Width        int           `bson:"width,omitempty" msgpack:"width,omitempty"`
	Height       int           `bson:"height,omitempty" msgpack:"height,omitempty"`
	UploadRegion string        `bson:"upload_region" msgpack:"upload_region"`
	UploaderId   meowid.MeowID `bson:"uploader" msgpack:"uploader"`
	UploadedAt   int64         `bson:"uploaded_at" msgpack:"uploaded_at"`
	Claimed      bool          `bson:"claimed,omitempty" msgpack:"claimed,omitempty"`
}

func GetFile(id string) (File, error) {
	var f File
	err := db.Files.FindOne(context.TODO(), bson.M{"_id": id}).Decode(&f)
	return f, err
}

func (f *File) Claim() error {
	if f.Claimed {
		return ErrFileAlreadyClaimed
	}
	_, err := db.Files.UpdateOne(
		context.TODO(),
		bson.M{"_id": f.Id},
		bson.M{"$set": bson.M{"claimed": true}},
	)
	return err
}
