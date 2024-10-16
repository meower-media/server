package chats

import (
	"context"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/files"
	"github.com/meower-media/server/pkg/structs"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
)

const (
	ChatEmoteTypeEmoji   = 0
	ChatEmoteTypeSticker = 1
)

type Emote struct {
	Id       string `bson:"_id" msgpack:"id"`
	ChatId   int64  `bson:"chat" msgpack:"chat_id"`
	Type     int8   `bson:"type" msgpack:"type"` // 0: emoji, 1: sticker
	Name     string `bson:"name" msgpack:"name"`
	Animated bool   `bson:"animated" msgpack:"animated"`
}

func (c *Chat) CreateEmote(emoteType int8, id string, name string) (Emote, error) {
	var e Emote

	// Claim emote file
	f, err := files.GetFile(id)
	if err != nil {
		return e, err
	}
	if err := f.Claim(); err != nil {
		return e, err
	}

	// Create emote
	e = Emote{
		Id:       id,
		ChatId:   c.Id,
		Type:     emoteType,
		Name:     name,
		Animated: f.Mime == "image/gif",
	}
	if _, err := db.ChatEmotes.InsertOne(context.TODO(), &e); err != nil {
		return e, err
	}

	// Emit event
	if err := EmitCreateEmoteEvent(&e); err != nil {
		return e, err
	}

	return e, err
}

func (c *Chat) GetEmotes(emoteType int8) ([]Emote, error) {
	var emotes []Emote
	cur, err := db.ChatEmotes.Find(context.TODO(), bson.M{"chat": c.Id, "type": emoteType})
	if err != nil {
		return emotes, err
	}
	return emotes, cur.All(context.TODO(), &emotes)
}

func (c *Chat) GetEmote(emoteType int8, id string) (Emote, error) {
	var e Emote
	err := db.ChatEmotes.FindOne(context.TODO(), bson.M{"_id": id, "type": emoteType}).Decode(&e)
	if err == mongo.ErrNoDocuments {
		return e, ErrEmoteNotFound
	}
	return e, err
}

func (e *Emote) V0() structs.V0ChatEmote {
	return structs.V0ChatEmote{
		Id:       e.Id,
		Name:     e.Name,
		Animated: e.Animated,
	}
}

func (e *Emote) Update(name string) error {
	e.Name = name
	_, err := db.ChatEmotes.UpdateByID(context.TODO(), e.Id, bson.M{"name": name})
	return err
}

func (e *Emote) Delete() error {
	_, err := db.ChatEmotes.DeleteOne(context.TODO(), bson.M{"_id": e.Id})
	return err
}
