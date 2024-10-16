package posts

import "errors"

var (
	ErrPostNotFound          = errors.New("post not found")
	ErrAttachmentNotFound    = errors.New("attachment not found")
	ErrReactionAlreadyExists = errors.New("reaction already exists")
)
