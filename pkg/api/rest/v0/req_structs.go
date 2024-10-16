package v0_rest

import (
	"github.com/meower-media/server/pkg/structs"
)

type LoginReq struct {
	Username     string `json:"username"`
	Password     string `json:"password"`
	TotpCode     string `json:"totp_code"`
	RecoveryCode string `json:"mfa_recovery_code"`
}

type RegisterReq struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Captcha  string `json:"captcha" validate:"max=5000"`
}

type RecoverReq struct {
	Email string `json:"email"`
}

type UpdateConfigReq struct {
	IconId     *string `json:"avatar" validate:""`
	LegacyIcon *int8   `json:"pfp_data" validate:""`
	Color      *string `json:"avatar_color" validate:""`
	Quote      *string `json:"quote" validate:""`

	structs.V0UserSettings
}

type AccountVerificationReq struct {
	Password string `json:"password" validate:"required"`
}

type ChangePasswordReq struct {
	OldPassword string `json:"old" validate:"required"`
	NewPassword string `json:"new" validate:"required"`
}

type ChangeEmailBody struct {
	AccountVerificationReq

	NewEmail string `json:"email" validate:"required,min=1,max=255"`
	Captcha  string `json:"captcha" validate:"max=5000"`
}

type AddAuthenticatorReq struct {
	AccountVerificationReq

	Type     string `json:"type" validate:"required"`
	Nickname string `json:"nickname" validate:"max=32"`

	TotpSecret string `json:"totp_secret" validate:"max=64"`
	TotpCode   string `json:"totp_code" validate:"min=6,max=6"`
}

type UpdateAuthenticatorReq struct {
	Nickname string `json:"nickname" validate:"max=32"`
}

type UpdateRelationshipReq struct {
	State *int8 `json:"state" validate:"required"`
}

type CreateGroupChatReq struct {
	Nickname string `json:"nickname" validate:"required,min=1,max=32"`
}

type CreateChatEmoteReq struct {
	Name string `json:"name" validate:"required,min=1,max=32"`
}

type CreatePostReq struct {
	Content       string   `json:"content" validate:"max=4000"`
	StickerIds    []string `json:"stickers"`
	AttachmentIds []string `json:"attachments"`

	ReplyToPostIds []string `json:"reply_to"`

	Nonce string `json:"nonce" validate:"max=64"`
}

type CreateReportReq struct {
	Reason  string `json:"reason" validate:"max=2000"`
	Comment string `json:"comment" validate:"max=2000"`
}
