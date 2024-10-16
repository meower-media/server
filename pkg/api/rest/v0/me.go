package v0_rest

import (
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/meower-media/server/pkg/structs"
	"github.com/meower-media/server/pkg/users"
	"github.com/meower-media/server/pkg/utils"
	"github.com/pquerna/otp/totp"
)

func MeRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Get("/", getMe)
	r.Patch("/config", updateConfig)
	r.Get("/relationships", getRelationships)
	r.Patch("/email", nil)
	r.Delete("/email", nil)
	r.Patch("/password", changePassword)
	r.Route("/authenticators", func(r chi.Router) {
		r.Get("/", getAuthenticators)
		r.Post("/", addAuthenticator)
		r.Patch("/{authenticatorId}", updateAuthenticator)
		r.Delete("/{authenticatorId}", removeAuthenticator)
		r.Get("/totp-secret", getNewTotpSecret)
	})
	r.Post("/reset-mfa-recovery-code", resetRecoveryCode)
	r.Delete("/tokens", nil)
	r.Route("/data", func(r chi.Router) {
		r.Get("/areas", nil)
		r.Get("/requests", nil)
		r.Post("/requests", nil)
	})

	return r
}

func getMe(w http.ResponseWriter, r *http.Request) {
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	settings := structs.V0DefaultUserSettings
	if err := user.GetSettings(0, &settings); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, MeResp{
		V0User:         user.V0(false, true),
		V0UserSettings: settings,
	})
}

func updateConfig(w http.ResponseWriter, r *http.Request) {
	// Decode body
	var body UpdateConfigReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Update user settings
	/*
		err := user.UpdateSettings(&body.UserSettingsV0)
		if err != nil {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}
	*/

	returnData(w, http.StatusOK, BaseResp{})
}

func getRelationships(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get relationships
	relationships, err := user.GetAllRelationships()
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Parse relationships
	v0relationships := []structs.V0Relationship{}
	for _, relationship := range relationships {
		v0r, err := relationship.V0()
		if err != nil {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
			return
		}
		v0relationships = append(v0relationships, v0r)
	}

	returnData(w, http.StatusOK, ListResp{
		Autoget: v0relationships,
		Page:    1,
		Pages:   1,
	})
}

func changePassword(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Decode body
	var body ChangePasswordReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Get account
	account, err := users.GetAccount(user.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Check old password
	if err := account.CheckPassword(body.OldPassword); err != nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
			"old": "Incorrect password.",
		})
		return
	}

	// Change password
	if err := account.ChangePassword(body.NewPassword); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}

func getAuthenticators(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get account
	account, err := users.GetAccount(user.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Parse authenticators
	v0Authenticators := []*structs.V0Authenticator{}
	for _, authenticator := range account.Authenticators {
		v0Authenticators = append(v0Authenticators, authenticator.V0())
	}

	returnData(w, http.StatusOK, ListResp{
		Autoget: v0Authenticators,
		Page:    1,
		Pages:   1,
	})
}

func addAuthenticator(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get account
	account, err := users.GetAccount(user.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Decode body
	var body AddAuthenticatorReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Check TOTP code
	tempAuthenticator := users.Authenticator{TotpSecret: body.TotpSecret}
	if !tempAuthenticator.CheckTotp(body.TotpCode) {
		returnErr(w, http.StatusUnauthorized, ErrInvalidTOTPCode, map[string]string{
			"totp_code": "Invalid TOTP code.",
		})
		return
	}

	// Check password
	if err := account.CheckPassword(body.Password); err != nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
			"password": "Incorrect password.",
		})
		return
	}

	// Add authenticator
	var authenticator *users.Authenticator
	if body.Type == "totp" {
		authenticator, err = account.AddTotpAuthenticator(body.Nickname, body.TotpSecret)
	}
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, NewMfaResp{
		Authenticator: authenticator.V0(),
		RecoveryCode:  &account.RecoveryCode,
	})
}

func updateAuthenticator(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get account
	account, err := users.GetAccount(user.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Decode body
	var body UpdateAuthenticatorReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Update authenticator
	authenticatorId, _ := strconv.ParseInt(chi.URLParam(r, "authenticatorId"), 10, 64)
	authenticator, err := account.ChangeAuthenticatorNickname(authenticatorId, body.Nickname)
	if err != nil {
		if err == users.ErrAuthenticatorNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	returnData(w, http.StatusOK, UpdatedAuthenticatorResp{
		V0Authenticator: authenticator.V0(),
	})
}

func removeAuthenticator(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Get account
	account, err := users.GetAccount(user.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Decode body
	var body AccountVerificationReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Check password
	if err := account.CheckPassword(body.Password); err != nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
			"password": "Incorrect password.",
		})
		return
	}

	// Remove authenticator
	authenticatorId, _ := strconv.ParseInt(chi.URLParam(r, "authenticatorId"), 10, 64)
	if err := account.RemoveAuthenticator(authenticatorId); err != nil {
		if err == users.ErrAuthenticatorNotFound {
			returnErr(w, http.StatusNotFound, ErrNotFound, nil)
		} else {
			returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		}
		return
	}

	returnData(w, http.StatusOK, BaseResp{})
}

func getNewTotpSecret(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Generate new TOTP secret
	totpSecret, err := totp.Generate(totp.GenerateOpts{
		Issuer:      "Meower",
		AccountName: user.Username,
	})
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, NewTotpSecretResp{
		Secret:          totpSecret.Secret(),
		ProvisioningUri: totpSecret.URL(),
		QRCodeSVG:       utils.GenerateSVGQRCode(totpSecret.URL()),
	})
}

func resetRecoveryCode(w http.ResponseWriter, r *http.Request) {
	// Get authed user
	user := getAuthedUser(r, nil)
	if user == nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, nil)
		return
	}

	// Decode body
	var body AccountVerificationReq
	if !decodeBody(w, r, &body) {
		return
	}

	// Get account
	account, err := users.GetAccount(user.Id)
	if err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	// Check password
	if err := account.CheckPassword(body.Password); err != nil {
		returnErr(w, http.StatusUnauthorized, ErrUnauthorized, map[string]string{
			"password": "Incorrect password.",
		})
		return
	}

	// Reset recovery code
	if err := account.ResetRecoveryCode(); err != nil {
		returnErr(w, http.StatusInternalServerError, ErrInternal, nil)
		return
	}

	returnData(w, http.StatusOK, NewMfaResp{
		RecoveryCode: &account.RecoveryCode,
	})
}
