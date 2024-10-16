package structs

type V0Relationship struct {
	Username  string `json:"username"`
	State     int8   `json:"state"`
	UpdatedAt int64  `json:"updated_at"`
}
