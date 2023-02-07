from datetime import datetime
import secrets

from src.util import uid, status, events, bitfield, flags
from src.entities import users, accounts, infractions, sessions
from src.database import db

class Application:
    def __init__(
        self,
        _id: str,
        name: str,
        description: str = "",
        flags: int = 0,
        owner_id: str = None,
        maintainers: list = [],
        oauth_secret: str = None,
        created: datetime = None
    ):
        self.id = _id
        self.name = name
        self.description = description
        self.flags = flags
        self.owner_id = owner_id
        self.maintainers = [users.get_user(maintainer_id) for maintainer_id in maintainers]
        self.oauth_secret = oauth_secret
        self.created = created

    @property
    def client(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "flags": self.flags,
            "owner_id": self.owner_id,
            "maintainers": [maintainer.partial for maintainer in self.maintainers],
            "created": int(self.created.timestamp())
        }

    @property
    def bot(self):
        try:
            return users.get_user(self.id, return_deleted=False)
        except:
            raise status.missingPermissions # placeholder

    def edit(self, name: str = None, description: str = None):
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        db.applications.update_one({"_id": self.id}, {"$set": {"name": self.name, "description": self.description}})

    def has_maintainer(self, user: users.User):
        for maintainer in self.maintainers:
            if maintainer.id == user.id:
                return True
        return False

    def add_maintainer(self, user: users.User):
        # Check whether user is already a maintainer
        if self.has_maintainer(user):
            raise status.missingPermissions # placeholder

        # Add maintainer
        self.maintainers.append(user)
        db.applications.update_one({"_id": self.id}, {"$addToSet": {"maintainers": user.id}})

    def remove_maintainer(self, user: users.User):
        # Check whether user is a maintainer
        if not self.has_maintainer(user):
            raise status.missingPermissions # placeholder

        # Check whether user is owner
        if user.id == self.owner_id:
            raise status.missingPermissions # placeholder

        # Remove maintainer
        self.maintainers.remove(user)
        db.applications.update_one({"_id": self.id}, {"$pull": {"maintainers": user.id}})

    def transfer_ownership(self, user: users.User):
        # Check whether user is a maintainer
        if user.id not in self.maintainers:
            raise status.missingPermissions # placeholder

        # Check whether user is owner
        if user.id == self.owner_id:
            raise status.missingPermissions # placeholder

        # Set new owner
        self.owner_id = user.id
        db.applications.update_one({"_id": self.id}, {"$set": {"owner_id": self.owner_id}})

    def create_bot(self, username: str):
        # Check if application already has a bot
        if bitfield.has(self.flags, flags.application.hasBot):
            raise status.missingPermissions # placeholder

        # Create new user for bot
        bot = users.create_user(username, user_id=self.id, flags=bitfield.create([flags.user.bot]))

        # Add hasBot flag to application
        self.flags = bitfield.add(self.flags, flags.application.hasBot)
        db.applications.update_one({"_id": self.id}, {"$set": {"flags": self.flags}})

        # Return bot
        return bot

    def refresh_oauth_secret(self):
        self.oauth_secret = secrets.token_hex(16)
        db.applications.update_one({"_id": self.id}, {"$set": {"oauth_secret": self.oauth_secret}})

    def delete(self):
        db.applications.delete_one({"_id": self.id})

def create_application(name: str, owner: users.User):    
    application = {
        "_id": uid.snowflake(),
        "name": name,
        "owner_id": owner.id,
        "maintainers": [owner.id],
        "created": uid.timestamp()
    }
    db.applications.insert_one(application)
    return Application(**application)

def get_application(application_id: str):
    application = db.applications.find_one({"_id": application_id})

    if application is None:
        raise status.notFound
    else:
        return Application(**application)

def get_user_applications(user: users.User):
    return [Application(**application) for application in db.applications.find({"maintainers": {"$all": [user.id]}})]

def migrate_user_to_bot(user: users.User, owner: users.User):    
    # Check migration eligibility
    try:
        account = accounts.get_account(user.id)
    except status.notFound:
        raise status.missingPermissions  # placeholder
    else:
        if account.mfa_enabled:
            raise status.missingPermissions  # placeholder
        
        moderation_status = infractions.user_status(user)
        if moderation_status["suspended"] or moderation_status["banned"]:
            raise status.missingPermissions  # placeholder

    # Create application
    application = {
        "_id": user.id,
        "name": user.username,
        "description": "Migrated from standard user account.",
        "flags": bitfield.create([flags.application.hasBot]),
        "owner_id": owner.id,
        "maintainers": [owner.id],
        "created": uid.timestamp()
    }
    db.applications.insert_one(application)

    # Update user
    for flag in [
        flags.user.child,
        flags.user.ageNotConfirmed,
        flags.user.requireEmail,
        flags.user.requireMFA
    ]:
        user.flags = bitfield.remove(user.flags, flag)
    user.flags = bitfield.add(user.flags, flags.user.bot)
    user.admin = 0
    user.badges = []
    db.users.update_one({"_id": user.id}, {"$set": {
        "flags": user.flags,
        "admin": user.admin,
        "badges": user.badges
    }})
    events.emit_event("user_updated", user.id, {
        "id": user.id,
        "flags": user.flags,
        "admin": user.admin,
        "badges": user.badges
    })

    # Delete all items that are not needed as a bot
    db.followed_users.delete_many({"from": user.id})
    db.blocked_users.delete_many({"from": user.id})
    db.post_likes.delete_many({"user_id": user.id})
    db.post_meows.delete_many({"user_id": user.id})
    db.user_sync.delete_one({"_id": user.id})
    db.accounts.delete_one({"_id": user.id})

    # Update user stats
    user.update_stats()

    # Revoke all sessions
    sessions.revoke_all_user_sessions(user)

    # Return application
    return Application(**application)
