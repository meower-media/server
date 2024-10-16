package structs

type V0ChatBan struct {
	User          *V0User `json:"user,omitempty"`           // only included when accessing the full ban list
	DetectEvasion *bool   `json:"detect_evasion,omitempty"` // only included when accessing the full ban list
	Reason        string  `json:"reason"`
	ExpiresAt     *int64  `json:"expires_at"`
}
