package models

import (
	"github.com/meower-media/server/pkg/posts"
)

type V0Attachment struct {
	Id       string `json:"id" msgpack:"id"`
	Filename string `json:"filename" msgpack:"filename"`
	Mime     string `json:"mime" msgpack:"mime"`
	Size     int    `json:"size" msgpack:"size"`
	Width    int    `json:"width" msgpack:"width"`
	Height   int    `json:"height" msgpack:"height"`
}

func ConstructAttachmentV0(a *posts.Attachment) *V0Attachment {
	return &V0Attachment{
		Id:       a.Id,
		Filename: a.Filename,
		Mime:     a.Mime,
		Size:     a.Size,
		Width:    a.Width,
		Height:   a.Height,
	}
}
