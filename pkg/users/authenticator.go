package users

import (
	"context"
	"strconv"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/structs"
	"github.com/pquerna/otp/totp"
	"go.mongodb.org/mongo-driver/bson"
)

type Authenticator struct {
	Id         meowid.MeowID `bson:"_id"`
	Type       string        `bson:"type"`
	Nickname   string        `bson:"nickname,omitempty"`
	TotpSecret string        `bson:"totp_secret,omitempty"`
}

func (a *Account) AddTotpAuthenticator(nickname string, secret string) (*Authenticator, error) {
	authenticator := Authenticator{
		Id:         meowid.GenId(),
		Type:       "totp",
		Nickname:   nickname,
		TotpSecret: secret,
	}
	a.Authenticators = append(a.Authenticators, authenticator)
	_, err := db.Accounts.UpdateByID(
		context.TODO(),
		a.Id,
		bson.M{"$addToSet": bson.M{"authenticators": &authenticator}},
	)
	return &authenticator, err
}

func (a *Account) GetAuthenticator(authenticatorId meowid.MeowID) (*Authenticator, error) {
	var authenticator *Authenticator
	for _, _authenticator := range a.Authenticators {
		if _authenticator.Id == authenticatorId {
			authenticator = &_authenticator
			break
		}
	}
	if authenticator == nil {
		return authenticator, ErrAuthenticatorNotFound
	}
	return authenticator, nil
}

func (a *Account) ChangeAuthenticatorNickname(authenticatorId meowid.MeowID, nickname string) (*Authenticator, error) {
	authenticator, err := a.GetAuthenticator(authenticatorId)
	if err != nil {
		return authenticator, err
	}
	authenticator.Nickname = nickname
	_, err = db.Accounts.UpdateOne(
		context.TODO(),
		bson.M{"_id": a.Id, "authenticators._id": authenticatorId},
		bson.M{"$set": bson.M{"authenticators.$.nickname": nickname}},
	)
	return authenticator, err
}

func (a *Account) RemoveAuthenticator(authenticatorId meowid.MeowID) error {
	newAuthenticators := []Authenticator{}
	for _, authenticator := range a.Authenticators {
		if authenticator.Id == authenticatorId {
			continue
		}
		newAuthenticators = append(newAuthenticators, authenticator)
	}
	a.Authenticators = newAuthenticators
	_, err := db.Accounts.UpdateOne(
		context.TODO(),
		bson.M{"_id": a.Id},
		bson.M{"$pull": bson.M{"authenticators": bson.M{"_id": authenticatorId}}},
	)
	return err
}

func (a *Account) CheckTotp(code string) bool {
	for _, authenticator := range a.Authenticators {
		if authenticator.Type != "totp" {
			continue
		}

		if valid := authenticator.CheckTotp(code); valid {
			return true
		}
	}

	return false
}

func (a *Authenticator) V0() *structs.V0Authenticator {
	return &structs.V0Authenticator{
		Id:           strconv.FormatInt(a.Id, 10),
		Type:         a.Type,
		Nickname:     a.Nickname,
		RegisteredAt: meowid.Extract(a.Id).Timestamp,
	}
}

func (a *Authenticator) CheckTotp(code string) bool {
	return totp.Validate(code, a.TotpSecret)
}
