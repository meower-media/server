from typing import TypedDict, Optional, Literal


class User(TypedDict):
    _id: str  # actually their username for some reason
    uuid: str  # NOT a uuid4 anymore
    lower_username: str
    email: Optional[str]  # private
    flags: int
    permissions: int
    lvl: Literal[0]  # deprecated
    ban: "UserBan"  # private
    banned: bool
    avatar: Optional[str]
    avatar_color: str  # their profile colour
    pfp_data: int  # their legacy avatar
    quote: str
    created: int
    last_seen: Optional[int]
    delete_after: Optional[int]  # private

class MinUser(TypedDict):
    _id: str  # actually their username for some reason
    uuid: str  # NOT a uuid4 anymore
    flags: int
    avatar: Optional[str]
    avatar_color: str  # their profile colour
    pfp_data: int  # their legacy avatar

class UserBan(TypedDict):
    state: Literal[
        "none",
        "temp_restriction",
        "perm_restriction",
        "temp_ban",
        "perm_ban"
    ]
    restrictions: int
    expires: int
    reason: str

class Session(TypedDict):
    _id: str
    ip_address: str
    user_agent: str
    client: str
    created_at: int
    mfa_verified: bool
    revoked: bool

class Chat(TypedDict):
    _id: str
    type: Literal[0, 1]
    nickname: str
    icon: str
    icon_color: str
    owner: str
    owner_id: str
    members: list[str]
    allow_pinning: bool
    created: int
    last_post_id: int
    last_active: int

class ChatMember(TypedDict):
    user: MinUser
    admin: bool
    last_read_post_id: Optional[str]
    mention_count: Optional[int]
    sharing_read_receipts: bool
    joined_at: int

class Post(TypedDict):
    _id: str
    post_id: str
    author: MinUser
    u: str  # author's username
    post_origin: str  # can be home, inbox, or a chat ID
    p: str  # content
    attachments: list["Attachment"]
    t: "ExtendedTimestamp"
    edited_at: Optional[int]
    pinned: bool
    isDeleted: bool

class Attachment(TypedDict):
    id: str
    mime: str
    filename: str
    size: int
    width: int
    height: int

class ExtendedTimestamp(TypedDict):
    d: str
    mo: str
    y: str
    h: str
    mi: str
    s: str
    e: int

class Report(TypedDict):
    _id: str
    type: Literal["user", "chat", "post"]
    content_id: str
    snapshot: "ReportSnapshot"
    status: Literal["pending"]
    escalated: bool
    reports: list["UserReport"]

class ReportSnapshot(TypedDict):
    user: User
    chat: Optional[Chat]
    posts: list[Post]

class UserReport(TypedDict):
    user: MinUser
    reason: str
    comment: str
    time: int
