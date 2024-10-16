package chats

import "errors"

var (
	ErrMemberNotFound      = errors.New("chat member not found")
	ErrMemberAlreadyExists = errors.New("chat member already exists")
	ErrEmoteNotFound       = errors.New("chat emote not found")
)
