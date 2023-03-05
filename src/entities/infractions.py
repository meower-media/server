from datetime import datetime

from src.util import status, uid, events, email, bitfield, flags
from src.entities import users, networks, security_cookies
from src.database import db

class Infraction:
    def __init__(self,
        _id: str,
        user_id: str = None,
        moderator_id: str = None,
        action: int = None,
        reason: str = None,
        offending_content: list = [],
        flags: int = 0,
        status: int = 0,
        exempt_alts: list = [],
        created: datetime = None,
        expires: datetime = None
    ):
        self.id = _id
        self.user = users.get_user(user_id)
        self.moderator = users.get_user(moderator_id)
        self.action = action  # 0: warning, 1: suspension, 2: ban
        self.reason = reason
        self.offending_content = offending_content
        self.flags = flags
        self.status = status  # 0: default, 1: appeal awaiting review,
                              # 2: waiting for more info, 3: upheld, 4: overturned
        self.exempt_alts = exempt_alts
        self.created = created
        self.expires = expires

    @property
    def client(self):
        return {
            "id": self.id,
            "user": self.user.partial,
            "action": self.action,
            "reason": self.reason,
            "offending_content": self.offending_content,
            "status": self.status,
            "created": int(self.created.timestamp()),
            "expires": (int(self.expires.timestamp()) if self.expires else None)
        }

    @property
    def admin(self):
        return {
            "id": self.id,
            "user": self.user.partial,
            "moderator": self.moderator.partial,
            "action": self.action,
            "reason": self.reason,
            "offending_content": self.offending_content,
            "flags": self.flags,
            "status": self.status,
            "exempt_alts": self.exempt_alts,
            "created": self.created,
            "expires": (int(self.expires.timestamp()) if self.expires else None)
        }

    @property
    def active(self):
        if self.status == 4:
            return False
        elif (not self.expires) or (self.expires.timestamp() > uid.timestamp().timestamp()):
            return True
        else:
            return False

    def edit(self,
        user: any = None,
        action: str = None,
        reason: str = None,
        offending_content: list = None,
        flags: int = None,
        status: int = None,
        exempt_alts: list = []
    ):
        updated_values = {}
        if user:
            updated_values["user"] = user
        if action:
            updated_values["action"] = action
        if reason:
            updated_values["reason"] = reason
        if offending_content:
            updated_values["offending_content"] = offending_content
        if flags:
            updated_values["flags"] = flags
        if status:
            updated_values["status"] = status
        if exempt_alts:
            updated_values["exempt_alts"] = exempt_alts

        for key, value in updated_values.items():
            setattr(self, key, value)

        db.infractions.update_one({"_id": self.id}, {"$set": updated_values})
        events.emit_event("infraction_updated", self.user.id, self.client)

    def update_expiration(self, expiration: datetime):
        self.expires = expiration
        db.infractions.update_one({"_id": self.id}, {"$set": {"expires": self.expires}})
        events.emit_event("infraction_updated", self.user.id, self.client)

    def delete(self):
        db.infractions.delete_one({"_id": self.id})
        events.emit_event("infraction_deleted", self.user.id, {
            "id": self.id
        })
        del self

def create_infraction(user: any, moderator: any, action: int, reason: str, offending_content: list = [], flags: int = 0, expires: datetime = None, send_email_alert: bool = True):
    # Create infraction data
    infraction = {
        "_id": uid.snowflake(),
        "user_id": user.id,
        "moderator_id": moderator.id,
        "action": action,
        "reason": reason,
        "offending_content": offending_content,
        "flags": flags,
        "created": uid.timestamp(),
        "expires": expires
    }

    # Insert infraction into database and convert into Infraction object
    db.infractions.insert_one(infraction)
    infraction = Infraction(**infraction)

    # Announce infraction creation
    events.emit_event("infraction_created", infraction.user.id, infraction.client)

    # Send email alert
    if send_email_alert:
        account = db.accounts.find_one({"_id": user.id}, projection={"email": 1})
        if isinstance(account, dict) and account.get("email"):
            email.send_email(account["email"], user.username, "tos_violation", {
                "username": user.username,
                "action": infraction.action,
                "reason": infraction.reason,
                "expires": (infraction.expires.strftime("%m/%d/%Y, %I:%M:%S %p").lower() if infraction.expires else None)
            })

    # Return infraction object
    return infraction

def get_infraction(infraction_id: str):
    # Get infraction from database
    infraction = db.infractions.find_one({"_id": infraction_id})

    # Return infraction object
    if infraction:
        return Infraction(**infraction)
    else:
        raise status.resourceNotFound

def get_latest_infractions(before: str = None, after: str = None, limit: int = 25):
    # Create ID range
    if before is not None:
        id_range = {"$lt": before}
    elif after is not None:
        id_range = {"$gt": after}
    else:
        id_range = {"$gt": "0"}

    # Fetch and return all infractions
    return [Infraction(**infraction) for infraction in db.infractions.find({"_id": id_range}, sort=[("time", -1)], limit=limit)]

def get_user_infractions(user: any, only_active: bool = False):
    query = {"user_id": user.id}
    if only_active:
        query["status"] = {"$ne": 4}
        query["$or"] = [{"expires": None}, {"expires": {"$gt": uid.timestamp()}}]
    return [Infraction(**infraction) for infraction in db.infractions.find(query)]

def user_status(user: any):
    status = {
        "suspended": False,
        "banned": False
    }

    for infraction in get_user_infractions(user):
        if not infraction.active:
            continue
        if infraction.action == 1:
            status["suspended"] = True
        elif infraction.action == 2:
            status["banned"] = True
    
    return status

def detect_ban_evasion(user, security_cookie, network):
    possible_alts = ([user] + security_cookie.users + network.users)
    for possible_alt in possible_alts:
        for infraction in get_user_infractions(possible_alt, only_active=True):
            if bitfield.has(infraction.flags, flags.infractions.detectAlts):
                pass  # will eventually add something to a report queue for admins to be notified
            if bitfield.has(infraction.flags, flags.infractions.poisonous):
                create_infraction(
                    user,
                    users.get_user("0"),
                    infraction.action,
                    f"Alternate account of @{infraction.user.username}",
                    flags=bitfield.create([
                        flags.infractions.automatic,
                        flags.infractions.blockAppeals
                    ]),
                    expires=infraction.expires,
                    send_email_alert=False
                )
