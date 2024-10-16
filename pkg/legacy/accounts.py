from typing import Optional, TypedDict, Literal
from base64 import urlsafe_b64encode
from hashlib import sha256
from threading import Thread
import time, bcrypt, secrets, re, pyotp, qrcode, qrcode.image.svg, os, msgpack

from database import db, rdb
from meowid import gen_id
from sessions import create_token
import errors, security


# I hate this. But, thanks https://stackoverflow.com/a/201378
EMAIL_REGEX = r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""
BCRYPT_SALT_ROUNDS = 14
TOTP_REGEX = "[0-9]{6}"


class AccountDB(TypedDict):
    _id: int

    email: Optional[str]
    normalized_email_hash: Optional[str]

    password_type: Literal["bcrypt"]
    password_hash: bytes

    recovery_code: str
    
    authenticators: list["AuthenticatorDB"]

    last_auth_at: int


class AuthenticatorDB(TypedDict):
    id: int
    type: Literal["totp"]
    nickname: str
    totp_secret: Optional[str]
    registered_at: int


class Account:
    def __init__(self, data: AccountDB):
        self.id = data["_id"]
        self.email = data.get("email")
        self.normalized_email_hash = data.get("normalized_email_hash")
        self.password_type = data["password_type"]
        self.password_hash = data["password_hash"]
        self.recovery_code = data["recovery_code"]
        self.authenticators = data.get("authenticators", [])
        self.last_auth_at = data["last_auth_at"]

    @classmethod
    def create(cls: "Account", user_id: int, password: str) -> "Account":
        data: AccountDB = {
            "_id": user_id,
            "password_type": "bcrypt",
            "password_hash": cls.hash_password_bcrypt(password),
            "recovery_code": cls.gen_recovery_code(),
            "last_auth_at": int(time.time())
        }
        db.accounts.insert_one(data)
        return cls(data)

    @classmethod
    def get_by_id(cls: "Account", account_id: str) -> "Account":
        data: Optional[AccountDB] = db.accounts.find_one({"_id": account_id})
        if not data:
            raise errors.AccountNotFound
        return cls(data)

    @classmethod
    def get_by_email(cls: "Account", email: str) -> "Account":
        data: Optional[AccountDB] = db.accounts.find_one({
            "normalized_email_hash": cls.get_normalized_email_hash(email)
        })
        if not data:
            raise errors.AccountNotFound
        return cls(data)

    @staticmethod
    def get_normalized_email_hash(address: str) -> str:
        """
        Get a hash of an email address with aliases and dots stripped.
        This is to allow using address aliases, but to still detect ban evasion.
        Also, Gmail ignores dots in addresses. Thanks Google.
        """

        identifier, domain = address.split("@")
        identifier = re.split(r'\+|\%', identifier)[0]
        identifier = identifier.replace(".", "")

        return urlsafe_b64encode(sha256(f"{identifier}@{domain}".encode()).digest()).decode()

    @staticmethod
    def hash_password_bcrypt(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_SALT_ROUNDS))

    @staticmethod
    def gen_recovery_code() -> str:
        return secrets.token_hex(5)

    @staticmethod
    def gen_totp_secret() -> str:
        return pyotp.random_base32()
    
    @staticmethod
    def get_totp_provisioning_uri(secret: str, username: str) -> str:
        return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="Meower")

    @staticmethod
    def get_totp_qrcode(provisioning_uri: str) -> str:
        return qrcode.make(
            provisioning_uri,
            image_factory=qrcode.image.svg.SvgImage
        ).to_string(encoding="unicode").replace("svg:rect", "rect")

    @property
    def mfa_methods(self) -> list[str]:
        methods = set()
        for authenticator in self.authenticators:
            methods.add(authenticator["type"])
        return list(methods)

    async def log_security_action(self, action_type: str, data: dict):
        db.security_log.insert_one({
            "_id": await gen_id(),
            "type": action_type,
            "user": self.id,
            "time": int(time.time()),
            "data": data
        })

        if action_type in {
            "email_changed",
            "password_changed",
            "mfa_added",
            "mfa_removed",
            "mfa_recovery_reset",
            "mfa_recovery_used",
            "locked"
        }:
            tmpl_name = "locked" if action_type == "locked" else "security_alert"
            platform_name = os.environ["EMAIL_PLATFORM_NAME"]
            platform_brand = os.environ["EMAIL_PLATFORM_BRAND"]

            txt_tmpl, html_tmpl = security.render_email_tmpl(tmpl_name, self.id, self.email, {
                "msg": {
                    "email_changed": f"The email address on your {platform_name} account has been changed.",
                    "password_changed": f"The password on your {platform_name} account has been changed.",
                    "mfa_added": f"A multi-factor authenticator has been added to your {platform_name} account.",
                    "mfa_removed": f"A multi-factor authenticator has been removed from your {platform_name} account.",
                    "mfa_recovery_reset": f"The multi-factor authentication recovery code on your {platform_name} account has been reset.",
                    "mfa_recovery_used": f"Your multi-factor authentication recovery code has been used to reset multi-factor authentication on your {platform_name} account."
                }[action_type] if action_type != "locked" else None,
                "token": create_token("email", [  # this doesn't use EmailTicket in sessions.py because it'd be a recursive import
                    self.email,
                    self.id,
                    "lockdown",
                    int(time.time())+86400
                ]) if self.email and action_type != "locked" else None
            })
        
            # Email
            if self.email:
                Thread(
                    target=security.send_email,
                    args=[security.EMAIL_SUBJECTS[tmpl_name], self.id, self.email, txt_tmpl, html_tmpl]
                ).start()

            # Inbox
            rdb.publish("admin", msgpack.packb({
                "op": "alert_user",
                "user": self.id,
                "content": txt_tmpl.replace(f"- {platform_brand}", f"""\- {platform_brand}""")
            }))

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash)

    def check_totp_code(self, code: str) -> bool:
        for authenticator in self.authenticators:
            if authenticator["type"] != "totp":
                continue
            if pyotp.TOTP(authenticator["totp_secret"]).verify(code, valid_window=1):
                return True
        return False

    def reset_mfa(self):
        self.recovery_code = secrets.token_hex(5)
        self.authenticators = []
        db.accounts.update_one({"_id": self.id}, {"$set": {
            "recovery_code": self.recovery_code,
            "authenticators": self.authenticators
        }})
