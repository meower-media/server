package v0_rest

import (
	"log"
	"net/http"
	"regexp"
	"strings"

	"github.com/getsentry/sentry-go"
	"github.com/go-chi/chi/v5"
	"github.com/meower-media/server/pkg/networks"
	"github.com/meower-media/server/pkg/structs"
	"github.com/meower-media/server/pkg/users"
)

var totpRegex = regexp.MustCompile(`[0-9]{6}$`)

func AuthRouter() *chi.Mux {
	r := chi.NewRouter()

	// IP block check
	r.Use(func(h http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			blocked, err := networks.IsBlocked(r.RemoteAddr)
			if err != nil {
				sentry.CaptureException(err)
				returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
				return
			} else if blocked {
				returnErr(w, http.StatusForbidden, ErrIPBlocked, nil)
				return
			}

			h.ServeHTTP(w, r)
		})
	})

	r.Post("/login", login)
	r.Post("/register", register)

	return r
}

func login(w http.ResponseWriter, r *http.Request) {
	// Decode body
	var body LoginReq
	if !decodeBody(w, r, &body) {
		return
	}

	// IP Ratelimit
	if ratelimited("login", "ip", r.RemoteAddr) {
		returnErr(w, http.StatusTooManyRequests, ErrRatelimited, nil)
		return
	}
	ratelimit(w, "login", "ip", r.RemoteAddr, 30, 900)

	// Get account and user
	var account users.Account
	var user users.User
	var err error
	if strings.Contains(body.Username, "@") {
		// Get account
		account, err = users.GetAccount(user.Id)
		if err == users.ErrAccountNotFound {
			returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
				"username": "Incorrect username/password.",
				"password": "Incorrect username/password.",
			})
			return
		} else if err != nil {
			log.Println(err)
			sentry.CaptureException(err)
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}

		// Get user
		user, err = users.GetUserByUsername(body.Username)
		if err != nil {
			log.Println(err)
			sentry.CaptureException(err)
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}
	} else {
		// Get user
		user, err = users.GetUserByUsername(body.Username)
		if err == users.ErrUserNotFound {
			returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
				"username": "Incorrect username/password.",
				"password": "Incorrect username/password.",
			})
			return
		} else if err != nil {
			log.Println(err)
			sentry.CaptureException(err)
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}

		// Get account
		account, err = users.GetAccount(user.Id)
		if err != nil {
			log.Println(err)
			sentry.CaptureException(err)
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}
	}

	// Make sure user isn't deleted
	if user.HasFlag(users.FlagDeleted) {
		returnErr(w, http.StatusUnauthorized, ErrAccountDeleted, nil)
		return
	}

	// Make sure account isn't locked
	if user.HasFlag(users.FlagLocked) {
		returnErr(w, http.StatusUnauthorized, ErrAccountLocked, nil)
		return
	}

	// Extract the TOTP code if it's at the end of the password
	body.TotpCode = totpRegex.FindString(body.Password)
	if len(account.Authenticators) > 0 && body.TotpCode != "" && account.CheckTotp(body.TotpCode) {
		body.Password = totpRegex.ReplaceAllString(body.Password, "")
	}

	// Check token
	r.Header.Add("token", body.Password)
	authedUser := getAuthedUser(r, nil)
	if authedUser != nil && authedUser.Id == user.Id {
		// Get sessions
		session, err := users.GetAccSessionByToken(body.Password)
		if err != nil {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}

		// Get token
		token, err := session.Token()
		if err != nil {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}

		returnData(w, http.StatusOK, AuthResp{
			Account: struct {
				structs.V0User
				structs.V0UserSettings
			}{
				V0User: user.V0(false, true),
				//V0UserSettings: settings,
			},
			Session: session.V0(),
			Token:   token,
		})
		return
	}

	// Check password
	if err := account.CheckPassword(body.Password); err != nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
			"username": "Incorrect username/password.",
			"password": "Incorrect username/password.",
		})
		return
	}

	// Check MFA
	if len(account.Authenticators) > 0 {
		if body.TotpCode != "" {
			if !account.CheckTotp(body.TotpCode) {
				returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
					"totp_code": "Incorrect TOTP code.",
				})
				return
			}
		} else if body.RecoveryCode != "" {
			if body.RecoveryCode == account.RecoveryCode {

			} else {
				returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
					"mfa_recovery_code": "Incorrect recovery code code.",
				})
				return
			}
		} else {
			returnData(w, http.StatusUnauthorized, ErrResp{
				Error:      true,
				Type:       ErrMFARequired.Error(),
				MFAMethods: account.MfaMethods(),
			})
			return
		}
	}

	// Create session
	session, err := users.CreateAccSession(account.Id, r.RemoteAddr, r.Header.Get("User-Agent"))
	if err != nil {
		log.Println(err)
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get session token
	token, err := session.Token()
	if err != nil {
		log.Println(err)
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get settings
	/*
		settings := structs.V0DefaultUserSettings
		err = user.GetSettings(0, &settings)
		if err != nil {
			log.Println(err)
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}
	*/

	returnData(w, http.StatusOK, AuthResp{
		Account: struct {
			structs.V0User
			structs.V0UserSettings
		}{
			V0User: user.V0(false, true),
			//V0UserSettings: settings,
		},
		Session: session.V0(),
		Token:   token,
	})
}

func register(w http.ResponseWriter, r *http.Request) {
	// Decode body
	var body RegisterReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Check IP ratelimit
	if ratelimited("register_fail", "ip", r.RemoteAddr) || ratelimited("register_success", "ip", r.RemoteAddr) {
		returnErr(w, http.StatusTooManyRequests, ErrRatelimited, nil)
		return
	}

	// Check captcha
	captchaSuccess, err := checkCaptcha(body.Captcha)
	if err != nil {
		ratelimit(w, "register_fail", "ip", r.RemoteAddr, 5, 30)
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	} else if !captchaSuccess {
		ratelimit(w, "register_fail", "ip", r.RemoteAddr, 5, 30)
		returnErr(w, http.StatusForbidden, ErrInvalidCaptcha, map[string]string{
			"captcha": "Invalid captcha response.",
		})
		return
	}

	// Create account
	account, user, err := users.CreateAccount(body.Username, body.Password)
	if err != nil {
		ratelimit(w, "register_fail", "ip", r.RemoteAddr, 5, 30)
		if err == users.ErrUsernameTaken {
			returnErr(w, http.StatusConflict, ErrUsernameExists, map[string]string{
				"username": "Username already taken.",
			})
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	// Success ratelimit
	ratelimit(w, "register_success", "ip", r.RemoteAddr, 3, 900)

	// Create session
	session, err := users.CreateAccSession(account.Id, r.RemoteAddr, r.Header.Get("User-Agent"))
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get session token
	token, err := session.Token()
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Get settings
	settings := structs.V0DefaultUserSettings
	err = user.GetSettings(0, &settings)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, AuthResp{
		Account: struct {
			structs.V0User
			structs.V0UserSettings
		}{
			V0User:         user.V0(false, true),
			V0UserSettings: settings,
		},
		Session: session.V0(),
		Token:   token,
	})
}
