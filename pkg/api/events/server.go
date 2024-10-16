package events

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"

	"github.com/gorilla/websocket"
	"github.com/meower-media/server/pkg/events"
	"github.com/redis/go-redis/v9"
	"github.com/vmihailenco/msgpack/v5"
)

type Server struct {
	httpMux *http.ServeMux

	sessions      map[int64]*Session
	users         map[int64][]*Session
	relationships map[int64][]*Session
	chats         map[int64][]*Session

	nextNonce  int64
	nonceMutex sync.Mutex
}

func NewServer() *Server {
	// Create WebSocket upgrader
	upgrader := websocket.Upgrader{
		ReadBufferSize:    1024,
		WriteBufferSize:   1024,
		CheckOrigin:       func(r *http.Request) bool { return true },
		EnableCompression: true,
	}

	// Create server
	s := Server{
		httpMux: http.NewServeMux(),

		sessions:      make(map[int64]*Session),
		users:         make(map[int64][]*Session),
		relationships: make(map[int64][]*Session),
		chats:         make(map[int64][]*Session),

		nextNonce:  0,
		nonceMutex: sync.Mutex{},
	}
	s.httpMux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		// Get current session or create new session
		var session *Session
		if r.URL.Query().Has("sid") && r.URL.Query().Has("nonce") {
			sid, _ := strconv.ParseInt(r.URL.Query().Get("sid"), 10, 64)
			session = s.sessions[sid]
			if session == nil {
				w.WriteHeader(http.StatusInternalServerError)
				w.Write([]byte("Session not found."))
				return
			}
		} else {
			session = newSession(&s)
		}

		// Upgrade connection
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}

		// Register connection
		err = session.registerConn(conn, 0, 0)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte("Failed registering connection to session."))
			return
		}

		// Re-send missed packets
		if r.URL.Query().Has("sid") && r.URL.Query().Has("nonce") {
			lastNonce, _ := strconv.ParseInt(r.URL.Query().Get("nonce"), 10, 64)
			for _, packet := range session.packets {
				if packet.Nonce > lastNonce {
					session.writeToConn(packet)
				}
			}
		}
	})

	return &s
}

func (s *Server) getNextNonce() int64 {
	s.nonceMutex.Lock()
	defer s.nonceMutex.Unlock()
	nonce := s.nextNonce
	s.nextNonce++
	return nonce
}

func (s *Server) pubSub() error {
	// Create client
	opt, err := redis.ParseURL(os.Getenv("REDIS_URL"))
	if err != nil {
		return err
	}
	rdb := redis.NewClient(opt)

	// Create ctx
	ctx := context.Background()

	// Create pub/sub channel
	pubsub := rdb.Subscribe(ctx, "events")

	// Listen to incoming pub/sub events
	go func() {
		for msg := range pubsub.Channel() {
			// Parse event
			payload := []byte(msg.Payload)
			eventType := payload[0]
			payload = payload[1:]

			// Construct and send event
			switch eventType {
			case events.OpUpdateUser:
				var evData events.UpdateUser
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendUpdateUser(s, &evData); err != nil {
					log.Println(err)
					continue
				}

			case events.OpUpdateRelationship:
				var evData events.UpdateRelationship
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendUpdateRelationship(s, &evData); err != nil {
					log.Println(err)
					continue
				}

			case events.OpTyping:
				var evData events.Typing
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendTyping(s, &evData); err != nil {
					log.Println(err)
					continue
				}

			case events.OpCreatePost:
				var evData events.CreatePost
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendCreatePost(s, &evData); err != nil {
					log.Println(err)
					continue
				}
			case events.OpUpdatePost:
				var evData events.UpdatePost
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendUpdatePost(s, &evData); err != nil {
					log.Println(err)
					continue
				}
			case events.OpDeletePost:
				var evData events.DeletePost
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendDeletePost(s, &evData); err != nil {
					log.Println(err)
					continue
				}
			case events.OpBulkDeletePosts:
				var evData events.BulkDeletePosts
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendBulkDeletePosts(s, &evData); err != nil {
					log.Println(err)
					continue
				}

			case events.OpPostReactionAdd:
				var evData events.PostReactionAdd
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendPostReactionAdd(s, &evData); err != nil {
					log.Println(err)
					continue
				}
			case events.OpPostReactionRemove:
				var evData events.PostReactionRemove
				if err := msgpack.Unmarshal(payload, &evData); err != nil {
					log.Println(err)
					continue
				}
				if err := sendPostReactionRemove(s, &evData); err != nil {
					log.Println(err)
					continue
				}
			}
		}
	}()

	return nil
}

func (s *Server) Run(exposeAddr string) error {
	// Start pub/sub
	err := s.pubSub()
	if err != nil {
		return err
	}

	// Start HTTP server
	fmt.Println("Serving events HTTP on", exposeAddr)
	return http.ListenAndServe(exposeAddr, s.httpMux)
}
