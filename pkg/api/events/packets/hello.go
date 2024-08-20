package packets

type V0Hello struct {
	SessionId    string `json:"session_id" msgpack:"session_id"`
	PingInterval int    `json:"ping_interval" msgpack:"ping_interval"`
}

type V1Hello = V0Hello
