class Chats:
    def __init__(self, meower):
        self.cl = meower.cl
        self.log = meower.supporter.log
        self.errorhandler = meower.supporter.full_stack
        self.sendPacket = meower.supporter.sendPacket
        self.files = meower.files
        self.log("Chats initialized!")
    
    def has_permission(self, chatid, user):
        if (chatid == "home") or (chatid == "livechat"):
            return True
        FileRead, chatdata = self.files.load_item("chats", chatid)
        if not FileRead:
            return False
        return (user in chatdata["members"])

    def get_members_list(self, chatid):
        if (chatid == "home") or (chatid == "livechat"):
            return self.cl.getUsernames()
        FileRead, chatdata = self.files.load_item("chats", chatid)
        if not FileRead:
            return FileRead, None
        return FileRead, chatdata["members"]