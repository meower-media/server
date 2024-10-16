package v0_rest

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"reflect"
	"strconv"
	"strings"
	"time"

	"github.com/getsentry/sentry-go"
	"github.com/go-chi/chi/v5"
	"github.com/go-playground/validator/v10"
	"github.com/meower-media/server/pkg/rdb"
	"github.com/meower-media/server/pkg/users"
	"github.com/redis/go-redis/v9"
	"golang.org/x/crypto/sha3"
)

const CaptchaVerifyUrl = "https://api.hcaptcha.com/siteverify"

var validate = validator.New()

type CtxKey string

type AuthOpts struct {
	CheckRestriction bool
	SkipBanCheck     bool
}

func decodeBody(w http.ResponseWriter, r *http.Request, v interface{}) bool {
	// Decode body
	contentType := r.Header.Get("Content-Type")
	if contentType == "application/json" || contentType == "" { // default
		err := json.NewDecoder(r.Body).Decode(v)
		if err != nil {
			returnErr(w, http.StatusBadRequest, ErrBadRequest, nil)
			return false
		}
	} else {
		returnErr(w, http.StatusBadRequest, ErrBadRequest, nil)
		return false
	}

	// Get struct type
	structType := reflect.TypeOf(v)
	if structType.Kind() == reflect.Ptr {
		structType = structType.Elem()
	}

	// Validate
	err := validate.Struct(v)
	if err != nil {
		errFields := make(map[string]string, len(err.(validator.ValidationErrors)))
		for _, err := range err.(validator.ValidationErrors) {
			field, _ := structType.FieldByName(err.StructField())
			errFields[field.Tag.Get("json")] = err.Error()
		}
		returnErr(w, http.StatusBadRequest, ErrBadRequest, errFields)
		return false
	}

	return true
}

func returnData(w http.ResponseWriter, code int, data interface{}) {
	marshaled, err := json.Marshal(data)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
	} else {
		w.WriteHeader(code)
		w.Write(marshaled)
	}
}

func returnErr(w http.ResponseWriter, code int, errType error, fields map[string]string) {
	marshaled, err := json.Marshal(ErrResp{
		Error:  true,
		Type:   errType.Error(),
		Fields: fields,
	})
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("An error occurred while sending the error response."))
	} else {
		w.WriteHeader(code)
		w.Write(marshaled)
	}
}

// Update a ratelimit for a resource (bucket) based on a scope and identifier.
//
// Only 1 ratelimit should be set before returning a response.
// Otherwise, the ratelimit headers might accidentally be overwritten.
//
// The bucket should be the action, such as 'login'.
// The scope should be one of the following: ip, user.
// The identifier should be the IP address or user ID.
func ratelimit(w http.ResponseWriter, bucket string, scope string, id string, limit int, seconds int) error {
	// Get ratelimit hash
	ratelimitHash := getRatelimitHash(bucket, scope, id)

	// Get remaining limit and TTL
	var newRemaining int
	var newTTL time.Duration
	remaining, err := rdb.Client.Get(context.TODO(), ratelimitHash).Int()
	if err == redis.Nil {
		newRemaining = limit - 1
		newTTL = time.Duration(seconds) * time.Second
	} else {
		newRemaining = remaining - 1
		newTTL = rdb.Client.TTL(context.TODO(), ratelimitHash).Val()
	}

	// Set new limit
	if err := rdb.Client.Set(context.TODO(), ratelimitHash, newRemaining, newTTL).Err(); err != nil {
		return err
	}

	// Set response headers
	w.Header().Add("X-Rtl-Bucket", bucket)
	w.Header().Add("X-Rtl-Scope", scope)
	w.Header().Add("X-Rtl-Remaining", strconv.FormatInt(int64(newRemaining), 10))
	w.Header().Add("X-Rtl-Reset", strconv.FormatInt(time.Now().Add(newTTL).UnixMilli(), 10))

	return nil
}

func ratelimited(bucket string, scope string, id string) bool {
	ratelimitHash := getRatelimitHash(bucket, scope, id)
	remaining, err := rdb.Client.Get(context.TODO(), ratelimitHash).Int()
	if err == redis.Nil || remaining > 0 {
		return false
	} else {
		return true
	}
}

func getRatelimitHash(bucket string, scope string, id string) string {
	h := sha3.NewShake256()
	h.Write([]byte("rtl"))
	h.Write([]byte(bucket))
	h.Write([]byte(scope))
	h.Write([]byte(id))

	return base64.URLEncoding.EncodeToString(h.Sum(nil))
}

func checkCaptcha(response string) (bool, error) {
	hCaptchaSecret := os.Getenv("HCAPTCHA_SECRET")
	if hCaptchaSecret == "" {
		log.Println("Skipping captcha check as there is no hCaptcha secret set.")
		return true, nil
	}

	marshaledReq, err := json.Marshal(map[string]string{
		"secret":   hCaptchaSecret,
		"response": response,
	})
	if err != nil {
		return false, err
	}

	resp, err := http.Post(CaptchaVerifyUrl, "application/json", bytes.NewReader(marshaledReq))
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()

	var unmarshaledResp struct {
		Success bool `json:"success"`
	}
	err = json.NewDecoder(resp.Body).Decode(&unmarshaledResp)
	return unmarshaledResp.Success, err
}

func getAuthedUser(r *http.Request, opts *AuthOpts) *users.User {
	if opts == nil {
		opts = &AuthOpts{}
	}

	session, err := users.GetAccSessionByToken(r.Header.Get("token"))
	if err != nil {
		log.Println(1, err)
		if err != users.ErrTokenExpired && err != users.ErrSessionNotFound {
			sentry.CaptureException(err)
		}
		return nil
	}

	user, err := users.GetUser(session.UserId)
	if err != nil {
		log.Println(err)
		sentry.CaptureException(err)
		return nil
	}

	return &user
}

func getUserByUrlParam(r *http.Request, urlParam string) (users.User, error) {
	var user users.User
	var err error
	username := chi.URLParam(r, urlParam)
	if strings.HasPrefix(username, "$") {
		userId, _ := strconv.ParseInt(strings.Replace(username, "$", "", 1), 10, 64)
		user, err = users.GetUser(userId)
	} else {
		user, err = users.GetUserByUsername(username)
	}
	return user, err
}
