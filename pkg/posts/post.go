package posts

import (
	"context"
	"log"
	"regexp"
	"strconv"
	"time"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/structs"
	"github.com/meower-media/server/pkg/users"
	"github.com/meower-media/server/pkg/utils"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

var customEmojiRegex = regexp.MustCompile(`<:([a-zA-Z0-9]{24})>`)

type Post struct {
	Id              meowid.MeowID   `bson:"_id" msgpack:"id"`
	ChatId          meowid.MeowID   `bson:"chat" msgpack:"chat"` // 0: home, 1: livechat
	AuthorId        meowid.MeowID   `bson:"author" msgpack:"author"`
	ReplyToPostIds  []meowid.MeowID `bson:"reply_to" msgpack:"reply_to"`
	Content         string          `bson:"content,omitempty" msgpack:"content,omitempty"`
	StickerIds      []string        `bson:"stickers" msgpack:"stickers"`
	AttachmentIds   []string        `bson:"attachments" msgpack:"attachments"`
	ReactionIndexes []ReactionIndex `bson:"reactions" msgpack:"reactions"`
	LastEditedAt    int64           `bson:"last_edited,omitempty" msgpack:"last_edited,omitempty"`
	Pinned          bool            `bson:"pinned,omitempty" msgpack:"pinned,omitempty"`
}

type GetPostOpts struct {
	BeforeId *meowid.MeowID
	AfterId  *meowid.MeowID
	Skip     *int64
	Limit    *int64
}

type PaginationOpts interface {
	BeforeId() *meowid.MeowID
	AfterId() *meowid.MeowID
	Skip() int64
	Limit() int64
}

func GetPost(postId meowid.MeowID) (Post, error) {
	var p Post
	err := db.Posts.FindOne(context.TODO(), bson.M{"_id": postId}).Decode(&p)
	if err == mongo.ErrNoDocuments {
		return p, ErrPostNotFound
	}
	return p, err
}

func GetPosts(chatId meowid.MeowID, onlyIncludePinned bool, paginationOpts PaginationOpts) ([]Post, error) {
	queryFilter := bson.M{"$and": []bson.M{{"chat": chatId}}}
	if onlyIncludePinned {
		queryFilter["$and"] = append(
			queryFilter["$and"].([]bson.M),
			bson.M{"pinned": true},
		)
	}

	beforeId := paginationOpts.BeforeId()
	afterId := paginationOpts.AfterId()
	if beforeId != nil {
		queryFilter["$and"] = append(
			queryFilter["$and"].([]bson.M),
			bson.M{"_id": bson.M{"$lt": beforeId}},
		)
	}
	if afterId != nil {
		queryFilter["$and"] = append(
			queryFilter["$and"].([]bson.M),
			bson.M{"_id": bson.M{"$gt": afterId}},
		)
	}

	queryOpts := options.Find()
	queryOpts.SetSort(bson.M{"_id": -1})
	queryOpts.SetSkip(paginationOpts.Skip())
	queryOpts.SetLimit(paginationOpts.Limit())

	var posts []Post
	cur, err := db.Posts.Find(context.TODO(), queryFilter, queryOpts)
	if err != nil {
		return posts, err
	}
	if err := cur.All(context.TODO(), &posts); err != nil {
		return posts, err
	}

	return posts, nil
}

func CreatePost(
	chatId meowid.MeowID,
	authorId meowid.MeowID,
	replyToPostIds []meowid.MeowID,
	content string,
	stickerIds []string,
	attachmentIds []string,
	nonce string,
) (Post, error) {
	var p Post

	// De-dupe and validate reply to posts
	if len(replyToPostIds) > 0 {
		replyToPostIds = utils.RemoveDuplicates(replyToPostIds).([]meowid.MeowID)
		count, err := db.Posts.CountDocuments(
			context.TODO(),
			bson.M{
				"_id":  bson.M{"$in": replyToPostIds},
				"chat": chatId,
			},
		)
		if err != nil {
			return p, err
		}
		if count != int64(len(replyToPostIds)) {
			return p, err
		}
	}

	// De-dupe and validate stickers
	if len(stickerIds) > 0 {
		stickerIds = utils.RemoveDuplicates(stickerIds).([]string)
		count, err := db.ChatEmotes.CountDocuments(
			context.TODO(),
			bson.M{
				"_id":  bson.M{"$in": stickerIds},
				"type": 0,
			},
		)
		if err != nil {
			return p, err
		}
		if count != int64(len(stickerIds)) {
			return p, err
		}
	}

	// De-dupe, validate, and claim attachments
	if len(attachmentIds) > 0 {
		attachmentIds = utils.RemoveDuplicates(attachmentIds).([]string)
		result, err := db.Files.UpdateMany(
			context.TODO(),
			bson.M{
				"_id":      bson.M{"$in": attachmentIds},
				"uploader": authorId,
				"claimed":  false,
			},
			bson.M{"$set": bson.M{"claimed": true}},
		)
		if err != nil {
			return p, err
		}
		if result.ModifiedCount != int64(len(attachmentIds)) {
			return p, err
		}
	}

	// Create post
	p = Post{
		Id:              meowid.GenId(),
		ChatId:          chatId,
		AuthorId:        authorId,
		ReplyToPostIds:  replyToPostIds,
		Content:         content,
		StickerIds:      stickerIds,
		AttachmentIds:   attachmentIds,
		ReactionIndexes: []ReactionIndex{},
	}
	if _, err := db.Posts.InsertOne(context.TODO(), &p); err != nil {
		return p, err
	}

	// Emit event
	if err := EmitCreatePostEvent(&p, nil, nonce); err != nil {
		return p, err
	}

	return p, nil
}

func (p *Post) V0(includeReplies bool, requesterId *meowid.MeowID) structs.V0Post {
	// Chat ID
	var chatIdStr string
	if p.ChatId == 0 {
		chatIdStr = "home"
	} else if p.ChatId == 1 {
		chatIdStr = "livechat"
	} else {
		chatIdStr = strconv.FormatInt(p.Id, 10)
	}

	// Get author
	author, _ := users.GetUser(p.AuthorId)

	// Get replied to posts
	replyToV0 := []*structs.V0Post{}
	for _, postId := range p.ReplyToPostIds {
		if includeReplies {
			post, _ := GetPost(postId)
			postV0 := post.V0(false, requesterId)
			replyToV0 = append(replyToV0, &postV0)
		} else {
			replyToV0 = append(replyToV0, nil)
		}
	}

	// Get custom emojis
	for _, match := range customEmojiRegex.FindAllStringSubmatch(p.Content, -1) {
		customEmojiId := match[1]
		log.Println(customEmojiId)
	}

	// Parse reaction indexes
	reactionIndexesV0 := []structs.V0ReactionIndex{}
	for _, reactionIndex := range p.ReactionIndexes {
		reactionIndexesV0 = append(reactionIndexesV0, reactionIndex.V0(p.Id, requesterId))
	}

	return structs.V0Post{
		Id:             strconv.FormatInt(p.Id, 10),
		PostId:         strconv.FormatInt(p.Id, 10),
		ChatId:         chatIdStr,
		Type:           1,
		Author:         author.V0(true, false),
		AuthorUsername: author.Username,
		ReplyTo:        replyToV0,
		Timestamp: structs.V0PostTimestamp{
			Unix: meowid.Extract(p.Id).Timestamp / 1000,
		},
		Content:         p.Content,
		Emojis:          []*structs.V0Emote{},
		Stickers:        []*structs.V0Emote{},
		Attachments:     []interface{}{},
		ReactionIndexes: reactionIndexesV0,
		Pinned:          p.Pinned,
		LastEditedAt:    &p.LastEditedAt,
	}
}

func (p *Post) UpdateContent(newContent string) error {
	// Update content
	p.Content = newContent
	p.LastEditedAt = time.Now().UnixMilli()
	if _, err := db.Posts.UpdateByID(context.TODO(), p.Id, bson.M{"content": p.Content}); err != nil {
		return err
	}

	// Emit event
	if err := EmitUpdatePostEvent(p.ChatId, p.Id, &p.Content, nil, nil, &p.LastEditedAt); err != nil {
		return err
	}

	return nil
}

func (p *Post) RemoveAttachment(attachmentId string) error {
	// Remove and unclaim any matching attachment
	for i := range p.AttachmentIds {
		if p.AttachmentIds[i] == attachmentId {
			p.AttachmentIds = append(p.AttachmentIds[:i], p.AttachmentIds[i+1:]...)

			if _, err := db.Posts.UpdateByID(context.TODO(), p.Id, bson.M{"attachments": p.AttachmentIds}); err != nil {
				return err
			}

			if err := EmitUpdatePostEvent(
				p.ChatId,
				p.Id,
				nil,
				&p.AttachmentIds,
				nil,
				&p.LastEditedAt,
			); err != nil {
				return err
			}

			return nil
		}
	}

	return ErrAttachmentNotFound
}

func (p *Post) SetPinnedState(pinned bool) error {
	// Set pinned state
	p.Pinned = pinned
	if _, err := db.Posts.UpdateByID(context.TODO(), p.Id, bson.M{"pinned": p.Pinned}); err != nil {
		return err
	}

	// Emit event
	if err := EmitUpdatePostEvent(p.ChatId, p.Id, nil, nil, &p.Pinned, &p.LastEditedAt); err != nil {
		return err
	}

	return nil
}

func (p *Post) Delete(sendEvent bool) error {
	// Unclaim attachments
	go func() {}()

	// Delete reactions
	go func() {

	}()

	// Delete post
	if _, err := db.Posts.DeleteOne(context.TODO(), bson.M{"_id": p.Id}); err != nil {
		return err
	}

	// Emit event
	if sendEvent {
		if err := EmitDeletePostEvent(p.ChatId, p.Id); err != nil {
			return err
		}
	}

	return nil
}
