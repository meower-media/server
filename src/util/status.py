from sanic.exceptions import SanicException


### 10000-10999 -- General ###
class ok(SanicException):
    code = 10000
    http_status = 200
    message = "OK"

class internalServerError(SanicException):
    code = 10001
    http_status = 500
    message = "Internal server error"

class endpointNotFound(SanicException):
    code = 10002
    http_status = 404
    message = "Endpoint not found"

class resourceNotFound(SanicException):
    code = 10003
    http_status = 404
    message = "Resource not found"

class featureDiscontinued(SanicException):
    code = 10004
    http_status = 503
    message = "Feature is discontinued"


### 11000-11999 -- Invalid ###
class invalidSyntax(SanicException):
    code = 11000
    http_status = 400
    message = "Invalid syntax"

class invalidDatatype(SanicException):
    code = 11001
    http_status = 400
    message = "Invalid datatype"

class invalidType(SanicException):
    code = 11002
    http_status = 403
    message = "Invalid type"

class invalidCredentials(SanicException):
    code = 11003
    http_status = 401
    message = "Invalid credentials"

class invalidCaptcha(SanicException):
    code = 11004
    http_status = 403
    message = "Invalid captcha"

class nonSanePost(SanicException):
    code = 11005
    http_status = 403
    message = "Post is not sane"


### 12000-12999 -- Resource conflict ###
class usernameAlreadyTaken(SanicException):
    code = 12000
    http_status = 409
    message = "Username already taken"

class emailAlreadyTaken(SanicException):
    code = 12001
    http_status = 409
    message = "Email already taken"

class chatMemberAlreadyExists(SanicException):
    code = 12002
    http_status = 409
    message = "Chat member already exists"

class applicationMaintainerAlreadyExists(SanicException):
    code = 12003
    http_status = 409
    message = "Application maintainer already exists"

class botAlreadyExists(SanicException):
    code = 12004
    http_status = 409
    message = "Bot already exists"


### 13000-13999 -- Permissions error ###
class repairModeEnabled(SanicException):
    code = 13000
    http_status = 503
    message = "Repair mode is currently enabled"

class ratelimited(SanicException):
    code = 13001
    http_status = 429
    message = "Too many requests"

class notAuthenticated(SanicException):
    code = 13002
    http_status = 401
    message = "Not authenticated"

class missingScope(SanicException):
    code = 13003
    http_status = 403
    message = "Missing scope"

class missingPermissions(SanicException):
    code = 13003
    http_status = 403
    message = "Missing permissions"

class networkBlocked(SanicException):
    code = 13004
    http_status = 403
    message = "Network is currently blocked"

class userRestricted(SanicException):
    code = 13005
    http_status = 403
    message = "User is currently restricted"

class accountLocked(SanicException):
    code = 13006
    http_status = 403
    message = "Account is currently locked"

class fileTooLarge(SanicException):
    code = 13007
    http_status = 413
    message = "File too large"
