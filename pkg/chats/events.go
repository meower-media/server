package chats

import (
	"context"
	"fmt"

	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/rdb"
	"github.com/meower-media/server/pkg/utils"
	"github.com/vmihailenco/msgpack/v5"
)

type UpdateChatEvent struct {
	IconId *string `msgpack:"icon,omitempty"`
	Color  *string `msgpack:"color,omitempty"`
}

func EmitUpdateChatEvent(chatId meowid.MeowID, d *UpdateChatEvent) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(d)
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpUpdateChat)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", chatId), marshaledPacket).Err()
}

func EmitDeleteChatEvent(chatId meowid.MeowID) error {
	return rdb.Client.Publish(
		context.TODO(),
		fmt.Sprint("c", chatId),
		[]byte{utils.EvOpDeleteChat},
	).Err()
}

func EmitCreateMemberEvent(m *Member) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(m)
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpCreateChatMember)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", m.Id.ChatId), marshaledPacket).Err()
}

func EmitDeleteMemberEvent(chatId meowid.MeowID, userId meowid.MeowID) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(userId)
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpDeleteChatMember)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", chatId), marshaledPacket).Err()
}

func EmitCreateEmoteEvent(e *Emote) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(e)
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpCreateChatEmote)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", e.ChatId), marshaledPacket).Err()
}

func EmitUpdateEmoteEvent(e *Emote) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(e)
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpUpdateChatEmote)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", e.ChatId), marshaledPacket).Err()
}

func EmitDeleteEmoteEvent(chatId meowid.MeowID, emoteId meowid.MeowID) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(emoteId)
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpDeleteChatEmote)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", chatId), marshaledPacket).Err()
}

func EmitTypingEvent(chatId meowid.MeowID, userId meowid.MeowID) error {
	// Marshal packet
	marshaledPacket, err := msgpack.Marshal(userId)
	if err != nil {
		return err
	}
	marshaledPacket = append(marshaledPacket, utils.EvOpTyping)

	// Send packet
	return rdb.Client.Publish(context.TODO(), fmt.Sprint("c", chatId), marshaledPacket).Err()
}
