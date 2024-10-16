package structs

type V0Authenticator struct {
	Id           string `json:"_id"`
	Type         string `json:"type"`
	Nickname     string `json:"nickname"`
	RegisteredAt int64  `json:"registered_at"`
}
