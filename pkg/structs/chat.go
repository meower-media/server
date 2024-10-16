package structs

type V0Chat struct {
	Id   string `json:"_id"`
	Type int8   `json:"type"`

	// not included on DMs
	Nickname *string `json:"nickname,omitempty"`
	IconId   *string `json:"icon,omitempty"`
	Color    *string `json:"icon_color,omitempty"`

	// only on DMs
	DirectRecipient *V0User `json:"direct_recipient,omitempty"`

	OwnerUsername   *string  `json:"owner,omitempty"`        // requester if they are an admin | not included on DMs
	MemberUsernames []string `json:"members"`                // only includes first 256 members (this will be deprecated in the future)
	MemberCount     *int64   `json:"member_count,omitempty"` // not included on DMs

	CreatedAt    int64  `json:"created"`
	LastPostId   string `json:"last_post_id"`
	LastActiveAt int64  `json:"last_active"`

	AllowPinning bool `json:"allow_pinning"`

	Deleted bool `json:"deleted"` // deprecated
}
