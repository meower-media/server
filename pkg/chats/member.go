package chats

import (
	"context"
	"time"

	"github.com/getsentry/sentry-go"
	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

type Member struct {
	Id                   MemberIdCompound     `bson:"_id" msgpack:"id"`
	JoinedAt             int64                `bson:"joined_at" msgpack:"joined_at"`
	DM                   bool                 `bson:"dm" msgpack:"dm"`                             // whether this membership belongs to a DM chat
	Active               bool                 `bson:"active,omitempty" msgpack:"active,omitempty"` // only used for DMs
	Admin                bool                 `bson:"admin,omitempty" msgpack:"admin,omitempty"`
	NotificationSettings NotificationSettings `bson:"notification_settings" msgpack:"notification_settings"`
	LastAckedPostId      meowid.MeowID        `bson:"last_acked_post" msgpack:"last_acked_post"`
}

type MemberIdCompound struct {
	ChatId meowid.MeowID `bson:"chat" msgpack:"chat"`
	UserId meowid.MeowID `bson:"user" msgpack:"user"`
}

func GetChatMemberships(userId meowid.MeowID) ([]Member, error) {
	// Get latest DM memberships
	var dmChatMemberships []Member
	f := bson.M{"_id.user": userId, "dm": true, "active": true}
	opts := options.Find()
	opts.SetSort(bson.M{"last_acked_post": -1})
	opts.SetLimit(100)
	cur, err := db.ChatMembers.Find(context.TODO(), f, opts)
	if err != nil {
		return nil, err
	}
	if err := cur.All(context.TODO(), &dmChatMemberships); err != nil {
		return nil, err
	}

	// Get all group memberships
	var groupChatMemberships []Member
	f = bson.M{"_id.user": userId, "dm": false}
	cur, err = db.ChatMembers.Find(context.TODO(), f)
	if err != nil {
		return nil, err
	}
	if err := cur.All(context.TODO(), &groupChatMemberships); err != nil {
		return nil, err
	}

	return append(dmChatMemberships, groupChatMemberships...), nil
}

func (c *Chat) GetMember(userId meowid.MeowID) (Member, error) {
	var member Member
	err := db.ChatMembers.FindOne(
		context.TODO(),
		bson.M{"_id": bson.M{"chat": c.Id, "user": userId}},
	).Decode(&member)
	if err == mongo.ErrNoDocuments {
		return member, ErrMemberNotFound
	}
	return member, err
}

func (c *Chat) CreateMember(
	userId meowid.MeowID,
	dm bool,
	admin bool,
	notificationsMode int8,
	notificationsPush bool,
) (Member, error) {
	// Create membership
	m := Member{
		Id: MemberIdCompound{
			ChatId: c.Id,
			UserId: userId,
		},
		JoinedAt: time.Now().UnixMilli(),
		DM:       dm,
		Active:   !dm,
		Admin:    admin,
		NotificationSettings: NotificationSettings{
			Mode: notificationsMode,
			Push: notificationsPush,
		},
		LastAckedPostId: c.LastPostId,
	}
	if _, err := db.ChatMembers.InsertOne(context.TODO(), &m); err != nil {
		return m, err
	}

	// Emit event
	if err := EmitCreateMemberEvent(&m); err != nil {
		return m, err
	}

	// Update member count on chat
	go c.UpdateMemberCount()

	return m, nil
}

func (m *Member) EmitTyping() error {
	return EmitTypingEvent(m.Id.ChatId, m.Id.UserId)
}

func (m *Member) SetActiveStatus(active bool) error {
	// Set active status
	m.Active = active
	if _, err := db.ChatMembers.UpdateByID(
		context.TODO(),
		m.Id,
		bson.M{"$set": bson.M{"active": active}},
	); err != nil {
		return err
	}

	return nil
}

func (m *Member) Delete() error {
	// Delete chat member
	if _, err := db.ChatMembers.DeleteOne(
		context.TODO(),
		bson.M{"_id": bson.M{"chat": m.Id.ChatId, "user": m.Id.UserId}},
	); err != nil {
		return err
	}

	// Emit event
	if err := EmitDeleteMemberEvent(m.Id.ChatId, m.Id.UserId); err != nil {
		return err
	}

	// Update member count on chat
	go func() {
		chat, err := GetChat(m.Id.ChatId)
		if err != nil {
			sentry.CaptureException(err)
			return
		}
		chat.UpdateMemberCount()
	}()

	return nil
}
