from sanic.exceptions import SanicException

class ok(SanicException):
    error = False
    code = 0
    http_status = 200
    message = "OK"

class invalidSyntax(SanicException):
    error = True
    code = 1
    http_status = 400
    message = "Invalid syntax"

class invalidDatatype(SanicException):
    error = True
    code = 2
    http_status = 400
    message = "Invalid datatype"

class notFound(SanicException):
    error = True
    code = 3
    http_status = 404
    message = "Resource not found"

class alreadyExists(SanicException):
    error = True
    code = 4
    http_status = 409
    message = "Resource already exists"

class repairMode(SanicException):
    error = True
    code = 5
    http_status = 503
    message = "Server is currently in repair mode"

class internal(SanicException):
    error = True
    code = 6
    http_status = 500
    message = "Internal server error"

class notAuthenticated(SanicException):
    error = True
    code = 7
    http_status = 401
    message = "Not authenticated"

class invalidCredentials(SanicException):
    error = True
    code = 8
    http_status = 401
    message = "Invalid credentials"

class invalidTOTP(SanicException):
    error = True
    code = 9
    http_status = 401
    message = "Invalid TOTP/recovery code"

class totpNotEnabled(SanicException):
    error = True
    code = 10
    http_status = 403
    message = "TOTP not enabled"

class totpAlreadyEnabled(SanicException):
    error = True
    code = 11
    http_status = 403
    message = "TOTP already enabled"

class alreadyLiked(SanicException):
    error = True
    code = 12
    http_status = 403
    message = "Post already liked"

class notLiked(SanicException):
    error = True
    code = 13
    http_status = 403
    message = "Post not liked"

class alreadyMeowed(SanicException):
    error = True
    code = 14
    http_status = 403
    message = "Post already meowed"

class notMeowed(SanicException):
    error = True
    code = 15
    http_status = 403
    message = "Post not meowed"

class alreadyDeleted(SanicException):
    error = True
    code = 16
    http_status = 403
    message = "Resource already deleted"

class notDeleted(SanicException):
    error = True
    code = 17
    http_status = 403
    message = "Resource not deleted"

class parentNotLinked(SanicException):
    error = True
    code = 18
    http_status = 403
    message = "Parent not linked"

class childNotLinked(SanicException):
    error = True
    code = 19
    http_status = 403
    message = "Child not linked"

class permissionLevelOutOfRange(SanicException):
    error = True
    code = 20
    http_status = 400
    message = "Permission level out of range"

class chatHasVanityInviteCode(SanicException):
    error = True
    code = 21
    http_status = 403
    message = "Chat has vanity invite code"

class invalidCaptcha(SanicException):
    error = True
    code = 22
    http_status = 403
    message = "Invalid captcha"

class accountLocked(SanicException):
    error = True
    code = 23
    http_status = 403
    message = "Account locked"

class networkBlocked(SanicException):
    error = True
    code = 24
    http_status = 403
    message = "Your IP address is blocked"

class invalidTicket(SanicException):
    error = True
    code = 25
    http_status = 401
    message = "Invalid ticket"

class missingPermissions(SanicException):
    error = True
    code = 26
    http_status = 403
    message = "Missing permissions"

class memberNotFound(SanicException):
    error = True
    code = 27
    http_status = 404
    message = "Member not found"

class memberAlreadyExists(SanicException):
    error = True
    code = 28
    http_status = 409
    message = "Member already exists"

class userSuspended(SanicException):
    error = True
    code = 29
    http_status = 403
    message = "User is currently in read-only mode"

class userBanned(SanicException):
    error = True
    code = 30
    http_status = 403
    message = "User is currently banned"
