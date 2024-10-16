class UsernameDisallowed(Exception): pass
class UsernameTaken(Exception): pass
class PasswordDisallowed(Exception): pass
class UserNotFound(Exception): pass
class AccountNotFound(Exception): pass

class InvalidTokenSignature(Exception): pass

class AccSessionTokenExpired(Exception): pass

class AccSessionNotFound(Exception): pass

class EmailTicketExpired(Exception): pass
