package chats

import (
	"context"
	"strconv"
	"time"

	"github.com/getsentry/sentry-go"
	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/structs"
	"github.com/meower-media/server/pkg/users"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

const (
	ChatDefaultIdHome = 0

	ChatTypeGroup  = 0
	ChatTypeDirect = 1
)

type Chat struct {
	Id   meowid.MeowID `bson:"_id" msgpack:"id"`
	Type int8          `bson:"type" msgpack:"type"`

	Nickname *string `bson:"nickname,omitempty" msgpack:"nickname,omitempty"`
	IconId   *string `bson:"icon_id,omitempty" msgpack:"icon_id,omitempty"`
	Color    *string `bson:"color,omitempty" msgpack:"color,omitempty"`

	// used for DMs
	DirectRecipientIds *[]meowid.MeowID `bson:"direct_recipients,omitempty" msgpack:"direct_recipients,omitempty"`

	MemberCount int64 `bson:"member_count,omitempty" msgpack:"member_count,omitempty"`

	LastPostId meowid.MeowID `bson:"last_post_id,omitempty" msgpack:"last_post_id,omitempty"`

	// this should be made a permission chat admins can grant to members
	AllowPinning bool `bson:"allow_pinning,omitempty" msgpack:"allow_pinning,omitempty"`
}

func CreateGroupChat(nickname string, iconId string, color string) (Chat, error) {
	chat := Chat{
		Id:       meowid.GenId(),
		Type:     ChatTypeGroup,
		Nickname: &nickname,
		IconId:   &iconId,
		Color:    &color,
	}
	_, err := db.Chats.InsertOne(context.TODO(), &chat)
	return chat, err
}

func GetChat(chatId meowid.MeowID) (Chat, error) {
	var chat Chat
	return chat, db.Chats.FindOne(
		context.TODO(),
		bson.M{"_id": chatId},
	).Decode(&chat)
}

func GetDM(userId1 meowid.MeowID, userId2 meowid.MeowID) (Chat, error) {
	var chat Chat
	q := bson.M{"direct_recipients": []meowid.MeowID{userId1, userId2}}
	if err := db.Chats.FindOne(context.TODO(), q).Decode(&chat); err != nil {
		if err == mongo.ErrNoDocuments {
			chat = Chat{
				Id:                 meowid.GenId(),
				Type:               1,
				DirectRecipientIds: &[]meowid.MeowID{userId1, userId2},
				AllowPinning:       true,
			}
			if _, err := db.Chats.InsertOne(context.TODO(), chat); err != nil {
				return chat, err
			}

			if _, err := chat.AddMember(userId1, true, false, false); err != nil {
				return chat, err
			}
			if userId1 != userId2 { // if it's a self-DM, we will get an error with trying to add the same user
				if _, err := chat.AddMember(userId2, true, false, false); err != nil {
					return chat, err
				}
			}
		} else {
			return chat, err
		}
	}
	return chat, nil
}

func GetActiveChats(userId meowid.MeowID) ([]Chat, error) {
	// Get chat IDs (limited to the latest 200 acked chats)
	chatIds := []meowid.MeowID{}
	opts := options.Find()
	opts.Projection = bson.M{"_id.chat": 1}
	opts.Sort = bson.M{"last_acked_post": -1}
	limit := int64(200)
	opts.Limit = &limit
	cur, err := db.ChatMembers.Find(context.TODO(), bson.M{"_id.user": userId, "active": true}, opts)
	if err != nil {
		return nil, err
	}
	for cur.Next(context.TODO()) {
		var m Member
		if err := cur.Decode(&m); err != nil {
			return nil, err
		}
		chatIds = append(chatIds, m.Id.ChatId)
	}

	// Get chats
	var chats []Chat
	cur, err = db.Chats.Find(context.TODO(), bson.M{"_id": bson.M{"$in": chatIds}})
	if err != nil {
		return nil, err
	}
	if err := cur.All(context.TODO(), &chats); err != nil {
		return nil, err
	}

	return chats, nil
}

func (c *Chat) V0(requester users.User) structs.V0Chat {
	// Get direct recipient
	var directRecipient users.User
	var directRecipientV0 *structs.V0User
	var err error
	if c.DirectRecipientIds != nil {
		for _, userId := range *c.DirectRecipientIds {
			if userId == requester.Id {
				continue
			}

			directRecipient, err = users.GetUser(userId)
			if err != nil {
				sentry.CaptureException(err)
			} else {
				userV0 := directRecipient.V0(true, false)
				directRecipientV0 = &userV0
			}
			break
		}
	}

	// Get member usernames
	var memberUsernames []string
	if c.Type == 0 {
		memberUsernames = []string{}
	} else if c.Type == 1 { // DMs
		requester, err := users.GetUser(requester.Id)
		if err != nil {
			sentry.CaptureException(err)
		}
		memberUsernames = []string{directRecipient.Username, requester.Username}
	}

	return structs.V0Chat{
		Id:   strconv.FormatInt(c.Id, 10),
		Type: c.Type,

		Nickname: c.Nickname,
		IconId:   c.IconId,
		Color:    c.Color,

		DirectRecipient: directRecipientV0,

		MemberUsernames: memberUsernames,

		CreatedAt:    meowid.Extract(c.Id).Timestamp / 1000,
		LastPostId:   strconv.FormatInt(c.LastPostId, 10),
		LastActiveAt: meowid.Extract(c.LastPostId).Timestamp / 1000,

		AllowPinning: c.AllowPinning,
	}
}

func (c *Chat) EditChatIcon(iconId *string, color *string) error {
	if iconId != nil && *iconId != *c.IconId {
		c.IconId = iconId
	}
	if color != nil {
		c.Color = color
	}
	if _, err := db.Chats.UpdateByID(
		context.TODO(),
		c.Id,
		bson.M{"icon": c.IconId, "color": c.Color},
	); err != nil {
		return err
	}
	if err := EmitUpdateChatEvent(c.Id, &UpdateChatEvent{
		IconId: iconId,
		Color:  color,
	}); err != nil {
		return err
	}
	return nil
}

func (c *Chat) AddMember(userId meowid.MeowID, dm bool, active bool, admin bool) (Member, error) {
	m := Member{
		Id: MemberIdCompound{
			ChatId: c.Id,
			UserId: userId,
		},
		JoinedAt: time.Now().UnixMilli(),
		DM:       dm,
		Active:   active,
		Admin:    admin,
		NotificationSettings: NotificationSettings{
			Mode: 2,
			Push: true,
		},
	}
	_, err := db.ChatMembers.InsertOne(context.TODO(), m)
	return m, err
}

// This should be executed within a background Goroutine
func (c *Chat) UpdateMemberCount() {
	// Get member count
	memberCount, err := db.ChatMembers.CountDocuments(
		context.Background(),
		bson.M{"_id.chat": c.Id},
	)
	if err != nil {
		sentry.CaptureException(err)
	}

	// Delete chat if no members remain or if only 1 member remains in a DM
	if (memberCount == 0) || (memberCount == 1 && c.Type == ChatTypeDirect) {
		if err := c.Delete(); err != nil {
			sentry.CaptureException(err)
		}
		return
	}

	// Update chat member count
	if _, err := db.Chats.UpdateByID(
		context.Background(),
		c.Id,
		bson.M{"$set": bson.M{"member_count": memberCount}},
	); err != nil {
		sentry.CaptureException(err)
	}
}

// This should be executed within a background Goroutine
func (c *Chat) UpdateLastPostId(postId meowid.MeowID) {
	c.LastPostId = postId
	if _, err := db.Chats.UpdateOne(
		context.TODO(),
		bson.M{"_id": c.Id},
		bson.M{"last_post_id": c.LastPostId},
	); err != nil {
		sentry.CaptureException(err)
	}

	// reset active state on DM
	if c.Type == 1 {
		if _, err := db.ChatMembers.UpdateMany(
			context.TODO(),
			bson.M{"_id.chat": c.Id, "active": false},
			bson.M{"active": true},
		); err != nil {
			sentry.CaptureException(err)
		}
	}
}

func (c *Chat) Delete() error {
	// Delete members
	if _, err := db.ChatMembers.DeleteMany(
		context.TODO(),
		bson.M{"_id.chat": c.Id},
	); err != nil {
		return err
	}

	// Emit event
	if err := EmitDeleteChatEvent(c.Id); err != nil {
		return err
	}

	// Delete chat
	if _, err := db.Chats.DeleteOne(
		context.TODO(),
		bson.M{"_id": c.Id},
	); err != nil {
		return err
	}

	// Delete emojis
	go func() {
		emojis, _ := c.GetEmotes(ChatEmoteTypeEmoji)
		for _, emoji := range emojis {
			emoji.Delete()
		}
	}()

	// Delete stickers
	go func() {
		stickers, _ := c.GetEmotes(ChatEmoteTypeSticker)
		for _, sticker := range stickers {
			sticker.Delete()
		}
	}()

	return nil
}
