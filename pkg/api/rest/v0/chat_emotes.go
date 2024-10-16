package v0_rest

import (
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/meower-media/server/pkg/chats"
	"github.com/meower-media/server/pkg/structs"
)

func ChatEmotesRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Get("/", getChatEmotes)

	r.Get("/{emoteId}", getChatEmote)
	r.Put("/{emoteId}", createChatEmote)
	r.Patch("/{emoteId}", updateChatEmote)
	r.Delete("/{emoteId}", deleteChatEmote)

	return r
}

func getChatEmotes(w http.ResponseWriter, r *http.Request) {
	// Get chat ID
	chatId, err := strconv.ParseInt(chi.URLParam(r, "chatId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get chat
	chat, err := chats.GetChat(chatId)
	if err != nil {
		returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		return
	}

	// Get emotes
	emotes, err := chat.GetEmotes(
		map[string]int8{
			"emojis":   chats.ChatEmoteTypeEmoji,
			"stickers": chats.ChatEmoteTypeSticker,
		}[chi.URLParam(r, "emoteType")],
	)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Parse emotes
	v0Emotes := []structs.V0ChatEmote{}
	for _, emote := range emotes {
		v0Emotes = append(v0Emotes, emote.V0())
	}

	returnData(w, http.StatusOK, ListResp{
		Autoget: v0Emotes,
		Page:    1,
		Pages:   1,
	})
}

func getChatEmote(w http.ResponseWriter, r *http.Request) {
	// Get chat ID
	chatId, err := strconv.ParseInt(chi.URLParam(r, "chatId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get chat
	chat, err := chats.GetChat(chatId)
	if err != nil {
		returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		return
	}

	// Get emote
	emote, err := chat.GetEmote(
		map[string]int8{
			"emojis":   chats.ChatEmoteTypeEmoji,
			"stickers": chats.ChatEmoteTypeSticker,
		}[chi.URLParam(r, "emoteType")],
		chi.URLParam(r, "emoteId"),
	)
	if err != nil {
		if err == chats.ErrEmoteNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	returnData(w, http.StatusOK, emote.V0())
}

func createChatEmote(w http.ResponseWriter, r *http.Request) {
	// Get chat ID
	chatId, err := strconv.ParseInt(chi.URLParam(r, "chatId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get chat
	chat, err := chats.GetChat(chatId)
	if err != nil {
		returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		return
	}

	// Decode body
	var body CreateChatEmoteReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Create chat emote
	emote, err := chat.CreateEmote(
		map[string]int8{
			"emojis":   chats.ChatEmoteTypeEmoji,
			"stickers": chats.ChatEmoteTypeSticker,
		}[chi.URLParam(r, "emoteType")],
		chi.URLParam(r, "emoteId"),
		body.Name,
	)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, emote.V0())
}

func updateChatEmote(w http.ResponseWriter, r *http.Request) {
	// Get chat ID
	chatId, err := strconv.ParseInt(chi.URLParam(r, "chatId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get chat
	chat, err := chats.GetChat(chatId)
	if err != nil {
		returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		return
	}

	// Get emote
	emote, err := chat.GetEmote(
		map[string]int8{
			"emojis":   chats.ChatEmoteTypeEmoji,
			"stickers": chats.ChatEmoteTypeSticker,
		}[chi.URLParam(r, "emoteType")],
		chi.URLParam(r, "emoteId"),
	)
	if err != nil {
		if err == chats.ErrEmoteNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	// Decode body
	var body CreateChatEmoteReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Update chat emote
	err = emote.Update(body.Name)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, emote.V0())
}

func deleteChatEmote(w http.ResponseWriter, r *http.Request) {
	// Get chat ID
	chatId, err := strconv.ParseInt(chi.URLParam(r, "chatId"), 10, 64)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get authed user
	authedUser := getAuthedUser(r, nil)
	if authedUser == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get chat
	chat, err := chats.GetChat(chatId)
	if err != nil {
		returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		return
	}

	// Get emote
	emote, err := chat.GetEmote(
		map[string]int8{
			"emojis":   chats.ChatEmoteTypeEmoji,
			"stickers": chats.ChatEmoteTypeSticker,
		}[chi.URLParam(r, "emoteType")],
		chi.URLParam(r, "emoteId"),
	)
	if err != nil {
		if err == chats.ErrEmoteNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	// Delete chat emote
	if err := emote.Delete(); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}
