package users

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"strconv"
	"strings"
	"time"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	structs "github.com/meower-media/server/pkg/structs"
	"github.com/vmihailenco/msgpack/v5"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
)

type AccSession struct {
	Id          meowid.MeowID `bson:"_id" msgpack:"_id"`
	UserId      meowid.MeowID `bson:"user" msgpack:"user"`
	IPAddress   string        `bson:"ip" msgpack:"ip"`
	UserAgent   string        `bson:"ua" msgpack:"ua"`
	RefreshedAt int64         `bson:"refreshed" msgpack:"refreshed"`
}

func CreateAccSession(userId meowid.MeowID, ipAddress string, userAgent string) (AccSession, error) {
	s := AccSession{
		Id:          meowid.GenId(),
		UserId:      userId,
		IPAddress:   ipAddress,
		UserAgent:   userAgent,
		RefreshedAt: time.Now().UnixMilli(),
	}

	if _, err := db.AccSessions.InsertOne(context.TODO(), s); err != nil {
		return s, err
	}

	return s, nil
}

func GetAccSession(id meowid.MeowID) (AccSession, error) {
	var s AccSession
	err := db.AccSessions.FindOne(context.TODO(), bson.M{"_id": id}).Decode(&s)
	if err == mongo.ErrNoDocuments {
		err = ErrSessionNotFound
	}
	return s, err
}

func GetAccSessionByToken(token string) (AccSession, error) {
	var s AccSession

	// Split token into claims and signature
	parts := strings.Split(token, ".")
	if len(parts) != 2 {
		return s, ErrInvalidTokenFormat
	}

	// Get claims
	claims, err := base64.URLEncoding.DecodeString(parts[0])
	if err != nil {
		return s, err
	}

	// Get signature
	signature, err := base64.URLEncoding.DecodeString(parts[1])
	if err != nil {
		return s, err
	}

	// Check signature
	h := hmac.New(sha256.New, AccSessionSigningKey)
	if _, err := h.Write(claims); err != nil {
		return s, err
	}
	if !hmac.Equal(signature, h.Sum(nil)) {
		return s, ErrInvalidTokenSignature
	}

	// Decode claims
	var decodedClaims []int64
	if err := msgpack.Unmarshal(claims, &decodedClaims); err != nil {
		return s, err
	}

	// Make sure token hasn't expired (less than 21 days since last refresh)
	if decodedClaims[1] > time.Now().Add((time.Hour*24)*21).UnixMilli() {
		return s, ErrTokenExpired
	}

	return GetAccSession(decodedClaims[0])
}

func (s *AccSession) V0() structs.V0Session {
	return structs.V0Session{
		Id:          strconv.FormatInt(s.Id, 10),
		IPAddress:   s.IPAddress,
		UserAgent:   s.UserAgent,
		RefreshedAt: s.RefreshedAt,
	}
}

func (s *AccSession) Token() (string, error) {
	// Claims
	claims, err := msgpack.Marshal([]int64{s.Id, s.RefreshedAt})
	if err != nil {
		return "", err
	}

	// Signature
	h := hmac.New(sha256.New, AccSessionSigningKey)
	if _, err := h.Write(claims); err != nil {
		return "", err
	}

	return base64.URLEncoding.EncodeToString(claims) + "." + base64.URLEncoding.EncodeToString(h.Sum(nil)), nil
}
