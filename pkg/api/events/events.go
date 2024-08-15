package events

import (
	"strconv"

	"github.com/meower-media-co/server/pkg/api/events/models"
	"github.com/meower-media-co/server/pkg/api/events/packets"
	"github.com/meower-media-co/server/pkg/events"
)

func sendUpdateUser(s *Server, e *events.UpdateUser) error {
	// Construct v0/v1 packets
	v0 := &packets.V0UpdateUser{
		Username:     e.User.Username,
		Avatar:       e.User.Avatar,
		LegacyAvatar: e.User.LegacyAvatar,
		Color:        e.User.Color,
		Flags:        e.User.Flags,
		Quote:        e.User.Quote,
	}
	v1 := v0

	// Create packet to send to clients
	p, err := createPacket(
		s,
		&packets.V0Packet{
			Cmd: "direct",
			Val: &packets.V0Packet{
				Mode:    "update_profile",
				Payload: v0,
			},
		},
		&packets.V1Packet{
			Cmd: "update_profile",
			Val: v1,
		},
	)
	if err != nil {
		return err
	}

	go func() {
		// Send to self
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}

		// Send to related users
		relatedSessions := s.relationships[e.User.Id]
		for _, sess := range relatedSessions {
			sess.send <- p
		}

		// Send to chats (somehow)
	}()

	return nil
}

func sendUpdateRelationship(s *Server, e *events.UpdateRelationship) error {
	v0p := &packets.V0UpdateRelationship{
		User:      models.ConstructUserV0(&e.To),
		Username:  e.To.Username,
		State:     e.State,
		UpdatedAt: e.UpdatedAt,
	}
	p, err := createPacket(
		s,
		&packets.V0Packet{
			Cmd: "direct",
			Val: &packets.V0Packet{
				Mode:    "update_relationship",
				Payload: v0p,
			},
		},
		&packets.V1Packet{
			Cmd: "update_relationship",
			Val: v0p,
		},
	)
	if err != nil {
		return err
	}

	go func() {
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}
	}()

	return nil
}

func sendTyping(s *Server, e *events.Typing) error {
	v0p := &packets.V0Typing{
		ChatId:   strconv.FormatInt(e.ChatId, 10),
		State:    100,
		Username: e.User.Username,
	}
	v1p := &packets.V1Typing{
		ChatId:   strconv.FormatInt(e.ChatId, 10),
		User:     models.ConstructUserV0(&e.User),
		Username: e.User.Username,
	}
	if e.ChatId == 0 || e.ChatId == 1 {
		v0p.ChatId = "livechat"
		v1p.ChatId = "livechat"
		if e.ChatId == 0 {
			v0p.State = 101
		}
	}

	p, err := createPacket(
		s,
		&packets.V0Packet{
			Cmd: "direct",
			Val: v0p,
		},
		&packets.V1Packet{
			Cmd: "typing",
			Val: v1p,
		},
	)
	if err != nil {
		return err
	}

	go func() {
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}
	}()

	return nil
}

func sendCreatePost(s *Server, e *events.CreatePost) error {
	// Construct v0/v1 posts
	v0Post := models.ConstructPostV0(
		&e.Post,
		e.Users,
		e.ReplyTo,
		e.Emotes,
		e.Attachments,
	)

	// Construct v0/v1 packets
	v0p := &packets.V0Packet{
		Cmd: "direct",
		Val: &packets.V0CreatePost{
			V0Post: v0Post,
		},
	}
	if v0Post.ChatId == "home" {
		v0p.Val.(*packets.V0CreatePost).Mode = 1
	} else {
		v0p.Val.(*packets.V0CreatePost).State = 2
	}

	// Create packet to send to clients
	p, err := createPacket(
		s,
		v0p,
		&packets.V1Packet{
			Cmd: "post",
			Val: v0Post, // same as v1
		},
	)
	if err != nil {
		return err
	}

	go func() {
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}
	}()

	return nil
}

func sendUpdatePost(s *Server, e *events.UpdatePost) error {
	// Construct v0/v1 posts
	v0Post := models.ConstructPostV0(
		&e.Post,
		e.Users,
		e.ReplyTo,
		e.Emotes,
		e.Attachments,
	)

	// Create packet to send to clients
	p, err := createPacket(
		s,
		&packets.V0Packet{
			Cmd: "direct",
			Val: &packets.V0Packet{
				Mode:    "update_post",
				Payload: &v0Post,
			},
		},
		&packets.V1Packet{
			Cmd: "update_post",
			Val: &v0Post,
		},
	)
	if err != nil {
		return err
	}

	go func() {
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}
	}()

	return nil
}

func sendDeletePost(s *Server, e *events.DeletePost) error {
	v1p := &packets.V1DeletePost{
		ChatId: strconv.FormatInt(e.ChatId, 10),
		PostId: strconv.FormatInt(e.PostId, 10),
	}
	if e.ChatId == 0 {
		v1p.ChatId = "home"
	}

	p, err := createPacket(
		s,
		&packets.V0Packet{
			Cmd: "direct",
			Val: &packets.V0DeletePost{
				Mode:   "delete",
				PostId: strconv.FormatInt(e.PostId, 10),
			},
		},
		&packets.V1Packet{
			Cmd: "delete_post",
			Val: v1p,
		},
	)
	if err != nil {
		return err
	}

	go func() {
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}
	}()

	return nil
}

func sendBulkDeletePosts(s *Server, e *events.BulkDeletePosts) error {
	v1p := &packets.V1BulkDeletePosts{
		ChatId:  strconv.FormatInt(e.ChatId, 10),
		StartId: strconv.FormatInt(e.StartId, 10),
		EndId:   strconv.FormatInt(e.EndId, 10),
	}
	if e.ChatId == 0 {
		v1p.ChatId = "home"
	}
	for _, postId := range e.PostIds {
		v1p.PostIds = append(v1p.PostIds, strconv.FormatInt(postId, 10))
	}

	p, err := createPacket(
		s,
		nil,
		&packets.V1Packet{
			Cmd: "bulk_delete_posts",
			Val: v1p,
		},
	)
	if err != nil {
		return err
	}

	go func() {
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}
	}()

	return nil
}

func sendPostReactionAdd(s *Server, e *events.PostReactionAdd) error {
	v0p := &packets.V0PostReactionAdd{
		ChatId:   strconv.FormatInt(e.ChatId, 10),
		PostId:   strconv.FormatInt(e.PostId, 10),
		Emoji:    e.Emoji,
		User:     models.ConstructUserV0(&e.User),
		Username: e.User.Username,
	}
	if e.ChatId == 0 {
		v0p.ChatId = "home"
	}

	p, err := createPacket(
		s,
		&packets.V0Packet{
			Cmd: "direct",
			Val: &packets.V0Packet{
				Mode:    "post_reaction_add",
				Payload: v0p,
			},
		},
		&packets.V1Packet{
			Cmd: "post_reaction_add",
			Val: v0p,
		},
	)
	if err != nil {
		return err
	}

	go func() {
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}
	}()

	return nil
}

func sendPostReactionRemove(s *Server, e *events.PostReactionRemove) error {
	v0p := &packets.V0PostReactionRemove{
		ChatId:   strconv.FormatInt(e.ChatId, 10),
		PostId:   strconv.FormatInt(e.PostId, 10),
		Emoji:    e.Emoji,
		User:     models.ConstructUserV0(&e.User),
		Username: e.User.Username,
	}
	if e.ChatId == 0 {
		v0p.ChatId = "home"
	}

	p, err := createPacket(
		s,
		&packets.V0Packet{
			Cmd: "direct",
			Val: &packets.V0Packet{
				Mode:    "post_reaction_remove",
				Payload: v0p,
			},
		},
		&packets.V1Packet{
			Cmd: "post_reaction_remove",
			Val: v0p,
		},
	)
	if err != nil {
		return err
	}

	go func() {
		selfSessions := s.sessions //s.users[ps.UserId]
		for _, sess := range selfSessions {
			sess.send <- p
		}
	}()

	return nil
}
