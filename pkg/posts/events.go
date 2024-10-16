package posts

import (
	"context"
	"fmt"

	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/rdb"
	"github.com/meower-media/server/pkg/utils"
	"github.com/vmihailenco/msgpack/v5"
)

type CreatePostEvent struct {
	Post        *Post        `msgpack:"post"`
	Attachments []Attachment `msgpack:"attachments"`
	Nonce       string       `msgpack:"nonce,omitempty"`
}

type UpdatePostEvent struct {
	PostId        meowid.MeowID `msgpack:"post"`
	Content       *string       `msgpack:"content,omitempty"`
	AttachmentIds *[]string     `msgpack:"attachments,omitempty"`
	Pinned        *bool         `msgpack:"pinned,omitempty"`
	LastEditedAt  *int64        `msgpack:"last_edited,omitempty"`
}

type BulkDeletePostsEvent struct {
	StartId       meowid.MeowID    `msgpack:"start"`
	EndId         meowid.MeowID    `msgpack:"end"`
	FilterPostIds *[]meowid.MeowID `msgpack:"posts"`
	FilterUserIds *[]meowid.MeowID `msgpack:"users"`
}

func EmitCreatePostEvent(post *Post, attachments []Attachment, nonce string) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(&CreatePostEvent{
		Post:        post,
		Attachments: attachments,
		Nonce:       nonce,
	})
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpCreatePost)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", post.ChatId), marshaledPacket).Err()
}

func EmitUpdatePostEvent(
	chatId meowid.MeowID,
	postId meowid.MeowID,
	content *string,
	attachmentIds *[]string,
	pinned *bool,
	lastEditedAt *int64,
) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(&UpdatePostEvent{
		PostId:        postId,
		Content:       content,
		AttachmentIds: attachmentIds,
		Pinned:        pinned,
		LastEditedAt:  lastEditedAt,
	})
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpUpdatePost)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", chatId), marshaledPacket).Err()
}

func EmitDeletePostEvent(chatId meowid.MeowID, postId meowid.MeowID) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(&postId)
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpDeletePost)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", chatId), marshaledPacket).Err()
}

func EmitBulkDeletePostsEvent(
	chatId meowid.MeowID,
	startId meowid.MeowID,
	endId meowid.MeowID,
	filterPostIds *[]meowid.MeowID,
	filterUserIds *[]meowid.MeowID,
) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(&BulkDeletePostsEvent{
		StartId:       startId,
		EndId:         endId,
		FilterPostIds: filterPostIds,
		FilterUserIds: filterUserIds,
	})
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpBulkDeletePosts)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", chatId), marshaledPacket).Err()
}
