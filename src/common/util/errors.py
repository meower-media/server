class InvalidSyntax(Exception):
	cl_code = "Syntax"

class InvalidDatatype(Exception):
	cl_code = "Datatype"

class IllegalCharacters(Exception):
	cl_code = "IllegalChars"

class TooShort(Exception):
	cl_code = "Syntax"

class TooLarge(Exception):
	cl_code = "TooLarge"

class NotFound(Exception):
	cl_code = "IDNotFound"

class AlreadyExists(Exception):
	cl_code = "IDExists"

class NotAuthenticated(Exception):
	cl_code = "IDRequired"

class MissingPermissions(Exception):
	cl_code = "MissingPermissions"

class UsernameInvalid(Exception):
	cl_code = "IDNotFound"

class InvalidPassword(Exception):
	cl_code = "InvalidPassword"

class Ratelimited(Exception):
	cl_code = "Ratelimited"

class UserBanned(Exception):
	cl_code = "Banned"

class IPBanned(Exception):
	cl_code = "IPBanned"
