package structs

import (
	"github.com/meower-media/server/pkg/meowid"
)

type V0ChatMember struct {
	User *V0User `json:"user,omitempty"` // only included

	JoinedAt int64 `json:"joined_at"`
	Admin    bool  `json:"admin"`

	Ban *V0ChatBan `json:"ban"`

	// only included when getting own membership
	NotificationSettings *V0ChatNotificationSettings `json:"notification_settings,omitempty"`
	LastAckedPostId      *meowid.MeowID              `json:"last_acked_post_id,omitempty"`
	UnreadCount          *int64                      `json:"unread_count,omitempty"`
	UnreadMentionCount   *int64                      `json:"unread_mention_count,omitempty"`
}
