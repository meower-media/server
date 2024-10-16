package safety

import (
	"context"
	"crypto/sha256"
	"encoding/base64"

	"github.com/getsentry/sentry-go"
	"github.com/meower-media/server/pkg/chats"
	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/posts"
	"github.com/meower-media/server/pkg/users"
	"github.com/vmihailenco/msgpack/v5"
	"go.mongodb.org/mongo-driver/mongo"
)

type Snapshot struct {
	Hash  string       `bson:"_id" msgpack:"-"`
	Users []users.User `bson:"users" msgpack:"users"`
	Chats []chats.Chat `bson:"chats" msgpack:"chats"`
	Posts []posts.Post `bson:"posts" msgpack:"posts"`
}

func CreateUserSnapshot(userId meowid.MeowID) (Snapshot, error) {
	s := Snapshot{
		Users: []users.User{},
		Chats: []chats.Chat{},
		Posts: []posts.Post{},
	}

	// Snapshot user
	user, err := users.GetUser(userId)
	if err != nil {
		return s, err
	}
	s.Users = append(s.Users, user)

	// Add hash
	s.Hash, err = s.GetHash()
	if err != nil {
		return s, err
	}

	// Add to database
	if _, err := db.ReportSnapshots.InsertOne(context.TODO(), s); err != nil && !mongo.IsDuplicateKeyError(err) {
		return s, err
	}

	return s, nil
}

func CreatePostSnapshot(postId meowid.MeowID) (Snapshot, error) {
	s := Snapshot{
		Users: []users.User{},
		Chats: []chats.Chat{},
		Posts: []posts.Post{},
	}

	// Get post
	post, err := posts.GetPost(postId)
	if err != nil {
		return s, err
	}

	// Get surrounding posts
	paginationOpts := SnapshotPaginationOpts{
		ChatId: post.ChatId,
		PostId: post.Id,
	}
	paginationOpts.Mode = 0
	beforePosts, err := posts.GetPosts(post.ChatId, false, &paginationOpts)
	if err != nil {
		return s, err
	}
	paginationOpts.Mode = 1
	afterPosts, err := posts.GetPosts(post.ChatId, false, &paginationOpts)
	if err != nil {
		return s, err
	}

	// Add posts to snapshot
	s.Posts = append(append(beforePosts, post), afterPosts...)

	// Snapshot authors
	seenAuthors := make(map[meowid.MeowID]bool)
	for _, post := range s.Posts {
		if seenAuthors[post.AuthorId] {
			continue
		} else {
			seenAuthors[post.AuthorId] = true
		}
		user, err := users.GetUser(post.AuthorId)
		if err != nil {
			sentry.CaptureException(err)
			continue
		}
		s.Users = append(s.Users, user)
	}

	// Snapshot chat
	if post.ChatId != chats.ChatDefaultIdHome {
		return s, nil
	}

	// Add hash
	s.Hash, err = s.GetHash()
	if err != nil {
		return s, err
	}

	// Add to database
	if _, err := db.ReportSnapshots.InsertOne(context.TODO(), s); err != nil && !mongo.IsDuplicateKeyError(err) {
		return s, err
	}

	return s, nil
}

func (s *Snapshot) GetHash() (string, error) {
	marshaled, err := msgpack.Marshal(s)
	if err != nil {
		return "", err
	}
	h := sha256.New()
	if _, err := h.Write(marshaled); err != nil {
		return "", err
	}
	return base64.RawStdEncoding.EncodeToString(h.Sum(nil)), nil
}
