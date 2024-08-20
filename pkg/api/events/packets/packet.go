package packets

type V0Packet struct {
	Cmd      string      `json:"cmd,omitempty" msgpack:"cmd,omitempty"`
	Mode     interface{} `json:"mode,omitempty" msgpack:"mode,omitempty"`
	Val      interface{} `json:"val,omitempty" msgpack:"val,omitempty"`
	Payload  interface{} `json:"payload,omitempty" msgpack:"payload,omitempty"`
	Listener string      `json:"listener,omitempty" msgpack:"listener,omitempty"`
	Nonce    string      `json:"nonce,omitempty" msgpack:"nonce,omitempty"`
}

type V1Packet struct {
	Cmd      string      `json:"cmd"`
	Val      interface{} `json:"val"`
	Listener string      `json:"listener,omitempty"`
	Nonce    string      `json:"nonce,omitempty"`
}
