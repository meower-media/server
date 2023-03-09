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
    def public(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "flags": self.flags,
            "created": int(self.created.timestamp())
        }

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
        return users.get_user(self.id, return_deleted=False)

    def edit(self, name: str = None, description: str = None):
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        db.applications.update_one({"_id": self.id}, {"$set": {"name": self.name, "description": self.description}})

    def has_maintainer(self, user: any):
        for maintainer in self.maintainers:
            if maintainer.id == user.id:
                return True
        return False

    def add_maintainer(self, user: any):
        # Check whether user is already a maintainer
        if self.has_maintainer(user):
            raise status.applicationMaintainerAlreadyExists

        # Add maintainer
        self.maintainers.append(user)
        db.applications.update_one({"_id": self.id}, {"$addToSet": {"maintainers": user.id}})

    def remove_maintainer(self, user: any):
        # Check whether user is a maintainer
        if not self.has_maintainer(user):
            raise status.resourceNotFound

        # Check whether user is owner
        if user.id == self.owner_id:
            raise status.missingPermissions

        # Remove maintainer
        self.maintainers.remove(user)
        db.applications.update_one({"_id": self.id}, {"$pull": {"maintainers": user.id}})

    def transfer_ownership(self, user: any):
        # Check whether user is a maintainer
        if user.id not in self.maintainers:
            raise status.resourceNotFound

        # Check whether user is owner
        if user.id == self.owner_id:
            raise status.missingPermissions

        # Set new owner
        self.owner_id = user.id
        db.applications.update_one({"_id": self.id}, {"$set": {"owner_id": self.owner_id}})

    def create_bot(self, username: str):
        # Check if application already has a bot
        if bitfield.has(self.flags, flags.applications.hasBot):
            raise status.botAlreadyExists

        # Create new user for bot
        bot = users.create_user(username, user_id=self.id, flags=bitfield.create([flags.users.bot]))

        # Add hasBot flag to application
        self.flags = bitfield.add(self.flags, flags.applications.hasBot)
        db.applications.update_one({"_id": self.id}, {"$set": {"flags": self.flags}})

        # Return bot
        return bot

    def refresh_oauth_secret(self):
        self.oauth_secret = secrets.token_hex(16)
        db.applications.update_one({"_id": self.id}, {"$set": {"oauth_secret": self.oauth_secret}})

    def delete(self):
        for session in [sessions.OAuthSession(**session) for session in db.oauth_sessions.find({"application_id": self.id})]:
            session.revoke()
        db.applications.delete_one({"_id": self.id})

def create_application(name: str, owner: any):    
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
    # Get application from database
    application = db.applications.find_one({"_id": application_id})

    # Return application object
    if application:
        return Application(**application)
    else:
        raise status.resourceNotFound

def get_user_applications(user: any):
    return [Application(**application) for application in db.applications.find({"maintainers": {"$all": [user.id]}})]

def migrate_user_to_bot(user: any, owner: any):    
    # Check migration eligibility
    try:
        account = accounts.get_account(user.id)
    except:
        raise status.missingPermissions
    else:
        if account.email or account.mfa_enabled:
            raise status.missingPermissions
        
        moderation_status = infractions.user_status(user)
        if moderation_status["suspended"] or moderation_status["banned"]:
            raise status.missingPermissions

    # Create application
    application = {
        "_id": user.id,
        "name": user.username,
        "description": "Migrated from standard user account.",
        "flags": bitfield.create([flags.applications.hasBot]),
        "owner_id": owner.id,
        "maintainers": [owner.id],
        "created": uid.timestamp()
    }
    db.applications.insert_one(application)

    # Update user
    for flag in [
        flags.users.child,
        flags.users.ageNotConfirmed,
        flags.users.requireEmail,
        flags.users.requireMFA
    ]:
        user.flags = bitfield.remove(user.flags, flag)
    user.flags = bitfield.add(user.flags, flags.users.bot)
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
    db.followed_users.delete_many({"_id.from": user.id})
    db.blocked_users.delete_many({"_id.from": user.id})
    db.post_likes.delete_many({"_id.user_id": user.id})
    db.post_meows.delete_many({"_id.user_id": user.id})
    #db.user_sync.delete_one({"_id": user.id})
    db.accounts.delete_one({"_id": user.id})

    # Update user stats
    user.update_stats()

    # Revoke all sessions
    sessions.revoke_all_user_sessions(user)

    # Return application
    return Application(**application)
