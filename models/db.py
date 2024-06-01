from typing import TypedDict, Optional, Literal


class User(TypedDict):
    _id: int
    username: str
    email: Optional[str]
    password: Optional[str]
    flags: Optional[int]
    permissions: Optional[int]
    ban: Optional["UserBan"]
    avatar: Optional[str]
    legacy_avatar: Optional[int]
    color: Optional[str]
    quote: Optional[str]
    settings: "UserSettings"  # global (NOT client) settings
    last_seen: Optional[int]
    delete_after: Optional[int]

class MinUser(TypedDict):
    _id: int
    username: str
    flags: int
    avatar: Optional[str]
    legacy_avatar: Optional[int]
    color: Optional[str]

class UserBan(TypedDict):
    state: Optional[Literal[
        "none",
        "temp_restriction",
        "perm_restriction",
        "temp_ban",
        "perm_ban"
    ]]
    restrictions: Optional[int]
    expires: Optional[int]
    reason: Optional[str]

class UserSettings(TypedDict):
    hide_blocked_users: Optional[bool]

class Session(TypedDict):
    _id: int
    token: str
    user_id: int
    ip_address: str
    user_agent: str
    client: str
    created_at: int
    mfa_verified: bool
    revoked: bool

class Chat(TypedDict):
    _id: int
    type: Literal[0, 1]
    nickname: Optional[str]
    icon: Optional[str]
    icon_color: Optional[str]
    owner_id: Optional[int]
    allow_pinning: Optional[bool]
    last_post_id: Optional[int]

class ChatMember(TypedDict):
    _id: "ChatMemberComposite"
    admin: Optional[bool]
    last_read_post_id: Optional[int]
    mention_post_ids: Optional[list[int]]
    sharing_read_receipts: Optional[bool]
    closed: Optional[bool]
    joined_at: int

class ChatMemberComposite(TypedDict):
    chat_id: int
    user_id: int

class Post(TypedDict):
    _id: int
    author_id: int
    origin: str|int  # can be home, inbox, or a chat ID
    content: str
    attachments: list["Attachment"]
    created_at: int
    edited_at: Optional[int]
    pinned: Optional[bool]
    censored: Optional[bool]

class Attachment(TypedDict):
    id: str
    mime: str
    filename: str
    size: int
    width: int
    height: int

class Report(TypedDict):
    _id: int
    type: Literal["user", "chat", "post"]
    content_id: int
    snapshot: "ReportSnapshot"
    status: Literal["pending"]
    escalated: bool
    reports: list["UserReport"]

class ReportSnapshot(TypedDict):
    # user: The user that was reported.
    # chat: The owner of the chat.
    # post: The author of the post.
    user: User

    # user: None
    # chat: The chat that was reported.
    # post: The chat that the reported post was posted in (or None if it was home).
    chat: Optional[Chat]

    # user: The last 50 posts authored by the user.
    # chat: The last 50 posts in the chat.
    # post: The post that was reported and 50 posts around the reported post.
    posts: list[Post]

class UserReport(TypedDict):
    user_id: int
    reason: str
    comment: str
    time: int
