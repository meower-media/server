package structs

type V0ChatNotificationSettings struct {
	Mode       int8  `json:"mode"` // 2: all, 1: mentions, 0: none
	Push       bool  `json:"push"`
	MutedUntil int64 `json:"muted_until"` // -1 for permanent mute
}
