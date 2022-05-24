# General errors
class IllegalChars: pass
class TooShort: pass
class TooLong: pass
class MissingPermissions: pass

# File errors
class ItemDoesNotExist: pass
class ItemAlreadyExists: pass
class ReadError: pass
class WriteError: pass

# Account errors
class InvalidPassword: pass
class InvalidToken: pass
class TokenExpired: pass
class AccDormant: pass
class AccTempLocked: pass
class AccPermLocked: pass
class AccBanned: pass
class AccDeleted: pass