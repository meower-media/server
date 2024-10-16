package v0_rest

import (
	structs "github.com/meower-media/server/pkg/structs"
)

type BaseResp struct {
	Error bool `json:"error"`
}

type ErrResp struct {
	Error  bool              `json:"error"`
	Type   string            `json:"type"`
	Fields map[string]string `json:"fields,omitempty"`

	// very special field only for logging in
	MFAMethods []string `json:"mfa_methods,omitempty"`
}

type ListResp struct {
	Error   bool        `json:"error"`
	Autoget interface{} `json:"autoget"`
	Page    int64       `json:"page#"`
	Pages   int64       `json:"pages"`
}

type WelcomeResp struct {
	Error   bool        `json:"error"`
	Captcha CaptchaResp `json:"captcha"`
}

type CaptchaResp struct {
	Enabled bool   `json:"enabled"`
	Sitekey string `json:"sitekey"`
}

type StatusResp struct {
	RegistrationEnabled bool `json:"registrationEnabled"`
	RepairMode          bool `json:"isRepairMode"`
	IPBlocked           bool `json:"ipBlocked"`

	IPRegBlocked      bool `json:"ipRegistrationBlocked"` // deprecated (should always be false)
	ScratchDeprecated bool `json:"scratchDeprecated"`     // should always be true
}

type StatisticsResp struct {
	UserCount int64 `json:"users"`
	ChatCount int64 `json:"chats"`
	PostCount int64 `json:"posts"`
}

type AuthResp struct {
	Error   bool `json:"error"`
	Account struct {
		structs.V0User
		structs.V0UserSettings
	} `json:"account"`
	Session structs.V0Session `json:"session"`
	Token   string            `json:"token"`
}

type MeResp struct {
	Error bool `json:"error"`
	structs.V0User
	structs.V0UserSettings
}

type NewTotpSecretResp struct {
	Error           bool   `json:"error"`
	Secret          string `json:"secret"`
	ProvisioningUri string `json:"provisioning_uri"`
	QRCodeSVG       string `json:"qr_code_svg"`
}

type NewMfaResp struct {
	Error         bool                     `json:"error"`
	Authenticator *structs.V0Authenticator `json:"authenticator,omitempty"`
	RecoveryCode  *string                  `json:"mfa_recovery_code,omitempty"`
}

type UpdatedAuthenticatorResp struct {
	Error bool `json:"error"`
	*structs.V0Authenticator
}
