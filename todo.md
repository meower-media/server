# CURRENT ISSUES
- Followers/following counts in /v1/users/<id> not matching up with /v1/users/<id>/follows or /v1/users/<id>/following
- Implement a sane version system (startup version text)
- Fix cyclic import error for src/entities/notifications.py when importing from src/entities/users.py

# BEFORE RELEASE
- Account to bot migration (should be easy) (half done, need to do API endpoint)
- Uploads (mostly done)
- Post/comment/message masquerading (easy, just waiting on image uploads)
- Background worker thing to manage and cleanup stuff
- Account exports and deletions
- Fix up ratelimits and placeholder status codes
- Fix follow notifications

# DURING RELEASE
- OAuth2
- Administration and moderation API
- MFA with already logged in clients
- Verifying a parent email
- Parental controls
- CL3 server
