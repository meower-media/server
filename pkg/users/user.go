package users

import (
	"context"
	"strconv"

	"github.com/getsentry/sentry-go"
	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/structs"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

const (
	FlagSystem          int64 = 1
	FlagDeleted         int64 = 2
	FlagProtected       int64 = 4
	FlagRatelimitBypass int64 = 8
	FlagRequireEmail    int64 = 16
	FlagLocked          int64 = 32
)

type User struct {
	Id       int64  `bson:"_id" msgpack:"id"`
	Username string `bson:"username" msgpack:"username"` // required for v0 and v1 events

	Flags       int64  `bson:"flags,omitempty" msgpack:"flags"`
	Permissions *int64 `bson:"permissions,omitempty" msgpack:"permissions"`

	IconId     string  `bson:"icon_id,omitempty" msgpack:"icon_id"`
	LegacyIcon int8    `bson:"legacy_icon,omitempty" msgpack:"legacy_icon"`
	Color      string  `bson:"color,omitempty" msgpack:"color"`
	Quote      *string `bson:"quote,omitempty" msgpack:"quote"`

	LastSeenAt *int64 `bson:"last_seen_at,omitempty" msgpack:"last_seen_at"`
}

func UsernameTaken(username string) (bool, error) {
	opts := options.Count()
	opts.Collation = &options.Collation{Locale: "en_US", Strength: 2}
	limit := int64(1)
	opts.Limit = &limit
	count, err := db.Users.CountDocuments(context.TODO(), bson.M{"username": username}, opts)
	return count > 0, err
}

func GetUser(id meowid.MeowID) (User, error) {
	var user User
	err := db.Users.FindOne(context.TODO(), bson.M{"_id": id}).Decode(&user)
	if err == mongo.ErrNoDocuments {
		err = ErrUserNotFound
	}
	return user, err
}

func GetUserByUsername(username string) (User, error) {
	var user User
	opts := options.FindOne()
	opts.Collation = &options.Collation{Locale: "en_US", Strength: 2}
	err := db.Users.FindOne(context.TODO(), bson.M{"username": username}, opts).Decode(&user)
	if err == mongo.ErrNoDocuments {
		err = ErrUserNotFound
	}
	return user, err
}

func GetUsername(id meowid.MeowID) (string, error) {
	var user User
	opts := options.FindOne()
	opts.SetProjection(bson.M{"username": 1})
	err := db.Users.FindOne(context.TODO(), bson.M{"_id": id}, opts).Decode(&user)
	if err == mongo.ErrNoDocuments {
		err = ErrUserNotFound
	}
	return user.Username, err
}

func (u *User) V0(min bool, includeEmail bool) structs.V0User {
	v0u := structs.V0User{
		Id:         strconv.FormatInt(u.Id, 10),
		Username:   u.Username,
		Flags:      u.Flags,
		IconId:     u.IconId,
		LegacyIcon: &u.LegacyIcon,
		Color:      &u.Color,
	}
	if !min {
		v0u.Permissions = u.Permissions
		v0u.Quote = u.Quote
		v0u.LastSeenAt = u.LastSeenAt
	}

	if includeEmail {
		account, err := GetAccount(u.Id)
		if err != nil {
			sentry.CaptureException(err)
		}
		v0u.Email = &account.Email
	}

	return v0u
}

func (u *User) HasFlag(flag int64) bool {
	return u.Flags&flag == flag
}

func (u *User) GetSettings(version int8, v interface{}) error {
	return db.UserSettings.FindOne(
		context.TODO(),
		bson.M{"_id": bson.M{"user": u.Id, "version": version}},
	).Decode(v)
}
