package events

import (
	"encoding/json"
	"strconv"
	"time"

	"github.com/meower-media/server/pkg/api/events/packets"
	"github.com/vmihailenco/msgpack/v5"
)

type Packet struct {
	Nonce     int64
	CreatedAt int64

	V0JsonEncoded    []byte
	V0MsgpackEncoded []byte

	V1JsonEncoded []byte
}

func createPacket(server *Server, v0 *packets.V0Packet, v1 *packets.V1Packet) (*Packet, error) {
	var p = Packet{
		Nonce:     server.getNextNonce(),
		CreatedAt: time.Now().UnixMilli(),
	}
	var err error

	// Add nonce to versioned packets
	strNonce := strconv.FormatInt(p.Nonce, 10)
	v0.Nonce = strNonce
	v1.Nonce = strNonce

	// v0 json
	p.V0JsonEncoded, err = json.Marshal(v0)
	if err != nil {
		return nil, err
	}

	// v0 msgpack
	p.V0MsgpackEncoded, err = msgpack.Marshal(v0)
	if err != nil {
		return nil, err
	}

	// v1 json
	p.V1JsonEncoded, err = json.Marshal(v1)
	if err != nil {
		return nil, err
	}

	return &p, err
}
