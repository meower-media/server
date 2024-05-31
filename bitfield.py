class UserFlags:
    SYSTEM = 1 << 0
    DELETED = 1 << 1
    PROTECTED = 1 << 2

class UserAdminPermissions:
    SYSADMIN = 1 << 0

    VIEW_REPORTS = 1 << 1
    EDIT_REPORTS = 1 << 2

    VIEW_NOTES = 1 << 3
    EDIT_NOTES = 1 << 4

    VIEW_POSTS = 1 << 5
    DELETE_POSTS = 1 << 6

    VIEW_ALTS = 1 << 7
    SEND_ALERTS = 1 << 8
    KICK_USERS = 1 << 9
    CLEAR_PROFILE_DETAILS = 1 << 10
    VIEW_BAN_STATES = 1 << 11
    EDIT_BAN_STATES = 1 << 12
    DELETE_USERS = 1 << 13

    VIEW_IPS = 1 << 14
    BLOCK_IPS = 1 << 15

    VIEW_CHATS = 1 << 16
    EDIT_CHATS = 1 << 17

    SEND_ANNOUNCEMENTS = 1 << 18

class UserBanRestrictions:
    HOME_POSTS = 1 << 0
    CHAT_POSTS = 1 << 1
    NEW_CHATS = 1 << 2
    EDITING_CHAT_DETAILS = 1 << 3
    EDITING_PROFILE = 1 << 4
