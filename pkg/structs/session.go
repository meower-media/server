package structs

type V0Session struct {
	Id          string `json:"_id" msgpack:"_id"`
	IPAddress   string `json:"ip" msgpack:"ip"`
	Location    string `json:"location" msgpack:"location"`
	UserAgent   string `json:"user_agent" msgpack:"user_agent"`
	RefreshedAt int64  `json:"refreshed_at" msgpack:"refreshed_at"`
}
