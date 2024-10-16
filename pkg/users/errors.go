package users

import "errors"

var (
	ErrUsernameTaken         = errors.New("username taken")
	ErrUserNotFound          = errors.New("user not found")
	ErrAccountNotFound       = errors.New("account not found")
	ErrAuthenticatorNotFound = errors.New("authenticator not found")
	ErrSessionNotFound       = errors.New("session not found")
	ErrInvalidTokenFormat    = errors.New("invalid token format")
	ErrInvalidTokenSignature = errors.New("invalid token signature")
	ErrTokenExpired          = errors.New("token expired")
)
