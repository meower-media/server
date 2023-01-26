from sanic.exceptions import SanicException

class ok(SanicException):
    error = False
    code = 1000
    http_status = 200
    message = "OK"

class invalidSyntax(SanicException):
    error = True
    code = 1001
    http_status = 400
    message = "Invalid syntax"

class invalidDatatype(SanicException):
    error = True
    code = 1002
    http_status = 400
    message = "Invalid datatype"

class notFound(SanicException):
    error = True
    code = 1003
    http_status = 404
    message = "Resource not found"

class alreadyExists(SanicException):
    error = True
    code = 1004
    http_status = 409
    message = "Resource already exists"

class repairMode(SanicException):
    error = True
    code = 1005
    http_status = 503
    message = "Server is currently in repair mode"

class internal(SanicException):
    error = True
    code = 1006
    http_status = 500
    message = "Internal server error"

class notAuthenticated(SanicException):
    error = True
    code = 1007
    http_status = 401
    message = "Not authenticated"

class invalidCredentials(SanicException):
    error = True
    code = 1008
    http_status = 401
    message = "Invalid credentials"

class invalidTOTP(SanicException):
    error = True
    code = 1009
    http_status = 401
    message = "Invalid TOTP/recovery code"

class totpNotEnabled(SanicException):
    error = True
    code = 1010
    http_status = 403
    message = "TOTP not enabled"

class totpAlreadyEnabled(SanicException):
    error = True
    code = 1011
    http_status = 403
    message = "TOTP already enabled"

class alreadyLiked(SanicException):
    error = True
    code = 1012
    http_status = 403
    message = "Post already liked"

class notLiked(SanicException):
    error = True
    code = 1013
    http_status = 403
    message = "Post not liked"

class alreadyMeowed(SanicException):
    error = True
    code = 1014
    http_status = 403
    message = "Post already meowed"

class notMeowed(SanicException):
    error = True
    code = 1015
    http_status = 403
    message = "Post not meowed"

class alreadyDeleted(SanicException):
    error = True
    code = 1016
    http_status = 403
    message = "Resource already deleted"

class notDeleted(SanicException):
    error = True
    code = 1017
    http_status = 403
    message = "Resource not deleted"

class parentNotLinked(SanicException):
    error = True
    code = 1018
    http_status = 403
    message = "Parent not linked"

class childNotLinked(SanicException):
    error = True
    code = 1019
    http_status = 403
    message = "Child not linked"

class permissionLevelOutOfRange(SanicException):
    error = True
    code = 1020
    http_status = 400
    message = "Permission level out of range"

class chatHasVanityInviteCode(SanicException):
    error = True
    code = 1021
    http_status = 403
    message = "Chat has vanity invite code"

class invalidCaptcha(SanicException):
    error = True
    code = 1022
    http_status = 403
    message = "Invalid captcha"

class accountLocked(SanicException):
    error = True
    code = 1023
    http_status = 403
    message = "Account locked"

class networkBlocked(SanicException):
    error = True
    code = 1024
    http_status = 403
    message = "Your IP address is blocked"

class invalidTicket(SanicException):
    error = True
    code = 1025
    http_status = 401
    message = "Invalid ticket"

class missingPermissions(SanicException):
    error = True
    code = 1026
    http_status = 403
    message = "Missing permissions"

class memberNotFound(SanicException):
    error = True
    code = 1027
    http_status = 404
    message = "Member not found"

class memberAlreadyExists(SanicException):
    error = True
    code = 1028
    http_status = 409
    message = "Member already exists"

class userSuspended(SanicException):
    error = True
    code = 1029
    http_status = 403
    message = "User is currently in read-only mode"

class userBanned(SanicException):
    error = True
    code = 1030
    http_status = 403
    message = "User is currently banned"

class ratelimited(SanicException):
    error = True
    code = 1031
    http_status = 429
    message = "You are being ratelimited"
