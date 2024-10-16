package users

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"golang.org/x/crypto/bcrypt"
)

const BcryptCost = 14

type Account struct {
	Id meowid.MeowID `bson:"_id"`

	Email               string `bson:"email,omitempty"`
	NormalizedEmailHash string `bson:"normalized_email,omitempty"`

	PasswordHash   []byte          `bson:"password,omitempty"`
	RecoveryCode   string          `bson:"recovery_code,omitempty"`
	Authenticators []Authenticator `bson:"authenticators,omitempty"`

	LastAuthAt int64 `bson:"last_auth_at"`
}

func CreateAccount(username string, password string) (Account, User, error) {
	userId := meowid.GenId()
	var account Account
	var user User

	// Make sure username hasn't been taken
	taken, err := UsernameTaken(username)
	if err != nil {
		fmt.Println(err)
		return account, user, err
	} else if taken {
		return account, user, ErrUsernameTaken
	}

	// Create user
	user = User{
		Id:       userId,
		Username: username,
	}
	if _, err := db.Users.InsertOne(context.TODO(), user); err != nil {
		return account, user, err
	}

	// Hash password
	passwordHash, err := bcrypt.GenerateFromPassword([]byte(password), BcryptCost)
	if err != nil {
		return account, user, err
	}

	// Create account
	recoveryCode := make([]byte, 5)
	rand.Read(recoveryCode)
	account = Account{
		Id:           userId,
		PasswordHash: passwordHash,
		RecoveryCode: hex.EncodeToString(recoveryCode),
		LastAuthAt:   time.Now().UnixMilli(),
	}
	if _, err := db.Accounts.InsertOne(context.TODO(), account); err != nil {
		return account, user, err
	}

	return account, user, nil
}

func GetAccount(id meowid.MeowID) (Account, error) {
	var account Account
	err := db.Accounts.FindOne(context.TODO(), bson.M{"_id": id}).Decode(&account)
	if err == mongo.ErrNoDocuments {
		err = ErrUserNotFound
	}
	return account, err
}

func (a *Account) CheckPassword(password string) error {
	return bcrypt.CompareHashAndPassword(a.PasswordHash, []byte(password))
}

func (a *Account) ChangePassword(newPassword string) error {
	var err error
	a.PasswordHash, err = bcrypt.GenerateFromPassword([]byte(newPassword), BcryptCost)
	if err != nil {
		return err
	}

	if _, err := db.Accounts.UpdateByID(
		context.TODO(),
		a.Id,
		bson.M{"password": a.PasswordHash},
	); err != nil {
		return err
	}

	return nil
}

func (a *Account) MfaMethods() []string {
	methodsMap := make(map[string]bool)
	for _, authenticator := range a.Authenticators {
		methodsMap[authenticator.Type] = true
	}

	methodsSlice := []string{}
	for method := range methodsMap {
		methodsSlice = append(methodsSlice, method)
	}
	return methodsSlice
}

func (a *Account) ResetRecoveryCode() error {
	recoveryCode := make([]byte, 5)
	if _, err := rand.Read(recoveryCode); err != nil {
		return err
	}
	a.RecoveryCode = hex.EncodeToString(recoveryCode)
	if _, err := db.Accounts.UpdateByID(
		context.TODO(),
		a.Id,
		bson.M{"recovery_code": a.RecoveryCode},
	); err != nil {
		return err
	}
	return nil
}
