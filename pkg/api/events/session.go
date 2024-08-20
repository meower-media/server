package events

import (
	"fmt"
	"strconv"
	"time"

	"github.com/gorilla/websocket"
	"github.com/meower-media-co/server/pkg/api/events/packets"
)

type Session struct {
	id     int64
	server *Server

	userId        int64
	relationships map[int64]bool
	chats         map[int64]bool

	send          chan *Packet
	packets       []*Packet
	lastSeenNonce int64

	conn           *websocket.Conn
	protoVersion   int8
	protoFormat    int8 // 0: json, 1: msgpack (future use)
	disconnectedAt int64

	ended bool
}

const pingInterval = 45_000 // 45 seconds

func newSession(server *Server) *Session {
	// Create & register session
	s := Session{
		id:     server.getNextNonce(),
		server: server,

		relationships: make(map[int64]bool),
		chats:         make(map[int64]bool),

		send:    make(chan *Packet, 256),
		packets: []*Packet{},
	}
	s.server.sessions[s.id] = &s

	// Write thread
	go func() {
		for packet := range s.send {
			// Make sure to not re-send packets
			if packet.Nonce <= s.lastSeenNonce {
				continue
			} else {
				s.lastSeenNonce = packet.Nonce
			}

			// Add to packets history
			s.packets = append(s.packets, packet)

			// Write message to conn if one exists
			if s.conn != nil {
				s.writeToConn(packet)
			}
		}
	}()

	// Background thread
	go func() {
		for {
			time.Sleep(time.Millisecond * pingInterval)

			// Ping

			// Check for session timeout & remove old packet history
			if s.ended {
				break
			} else if s.conn == nil { // end session if there has been no conn for more than the ping interval
				if s.disconnectedAt < time.Now().Add(-(time.Millisecond * pingInterval)).UnixMilli() {
					s.endSession()
					break
				}
			} else { // remove packets from history that are more than the ping interval
				ts45SecsAgo := time.Now().Add(-(time.Millisecond * pingInterval)).UnixMilli()
				itemsToRemove := 0
				for _, packet := range s.packets {
					if packet.CreatedAt < ts45SecsAgo {
						itemsToRemove++
					}
				}
				s.packets = s.packets[itemsToRemove:]
			}
		}
	}()

	return &s
}

func (s *Session) registerConn(conn *websocket.Conn, protoVersion int8, protoFormat int8) error {
	// Close current connection if one exists
	if s.conn != nil {
		s.conn.WriteMessage(websocket.CloseAbnormalClosure, []byte{})
		err := s.conn.Close()
		if err != nil {
			return err
		}
	}

	// Set conn and protocol
	s.conn = conn
	s.protoVersion = protoVersion
	s.protoFormat = protoFormat

	// Read incoming messages until connection ends
	go func() {
		for {
			// Get next message
			_, msg, err := conn.ReadMessage()
			if err != nil {
				if websocket.IsCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway) {
					s.endSession()
				} else {
					conn.Close()
					s.conn = nil
					s.disconnectedAt = time.Now().Unix()
				}
				break
			}
			fmt.Println(msg)
		}
	}()

	// Send hello
	hello := &packets.V0Hello{
		SessionId:    strconv.FormatInt(s.id, 10),
		PingInterval: pingInterval,
	}
	p, _ := createPacket(
		s.server,
		&packets.V0Packet{
			Cmd: "hello",
			Val: hello,
		},
		&packets.V1Packet{
			Cmd: "hello",
			Val: hello,
		},
	)
	s.send <- p

	return nil
}

func (s *Session) writeToConn(packet *Packet) {
	if s.conn == nil {
		return
	}

	var err error

	// v0 - json
	if s.protoVersion == 0 && s.protoFormat == 0 && packet.V0JsonEncoded != nil {
		err = s.conn.WriteMessage(websocket.TextMessage, packet.V0JsonEncoded)
	}

	// v0 - msgpack
	if s.protoVersion == 0 && s.protoFormat == 1 && packet.V0MsgpackEncoded != nil {
		err = s.conn.WriteMessage(websocket.BinaryMessage, packet.V0MsgpackEncoded)
	}

	if err != nil {
		s.conn.Close()
	}
}

func (s *Session) regRelationship(userId int64) {
	s.relationships[userId] = true
	//s.server.relationships[s.userId] = userId
}

func (s *Session) endSession() error {
	// Make sure session hasn't already ended
	if s.ended {
		return nil
	}

	// Set ended state
	s.ended = true

	// De-register
	delete(s.server.sessions, s.id)

	// Close send channel & wipe vars
	close(s.send)
	//s.channels = nil
	s.packets = nil

	// Close connection if one exists
	if s.conn != nil {
		s.conn.WriteMessage(websocket.CloseAbnormalClosure, []byte{})
		s.conn.Close()
		s.conn = nil
	}

	return nil
}
