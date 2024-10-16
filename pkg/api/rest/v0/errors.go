package v0_rest

import "errors"

var (
	ErrBadRequest         = errors.New("badRequest")         // 400
	ErrUnauthorized       = errors.New("Unauthorized")       // 401
	ErrAccountDeleted     = errors.New("accountDeleted")     // 401
	ErrAccountLocked      = errors.New("accountLocked")      // 401
	ErrInvalidTOTPCode    = errors.New("invalidTOTPCode")    // 401
	ErrMFARequired        = errors.New("mfaRequired")        // 403
	ErrIPBlocked          = errors.New("ipBlocked")          // 403
	ErrInvalidCaptcha     = errors.New("invalidCaptcha")     // 403
	ErrMissingPermissions = errors.New("missingPermissions") // 403
	ErrNotFound           = errors.New("notFound")           // 404
	ErrUsernameExists     = errors.New("usernameExists")     // 409
	ErrRatelimited        = errors.New("tooManyRequests")    // 429
	ErrInternal           = errors.New("Internal")           // 500
)
