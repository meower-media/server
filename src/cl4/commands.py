from src.cl4.cloudlink import cloudlink
from src.util import bitfield, flags
from src.entities import users, sessions, infractions

class CL4Commands:
    def __init__(self, cl_server: cloudlink.server):
        self.cl = cl_server

    async def authenticate(self, client, payload, listener):
        # Validate payload
        validation = self.cl.supporter.validate(
            keys={
                "token": str
            },
            payload=payload,
            optional=[],
            sizes={
                "token": 1000
            }
        )
        match validation:
            case self.cl.supporter.invalid:
                return await self.cl.send_code(client, "DataType", listener=listener)
            case self.cl.supporter.missing_key:
                return await self.cl.send_code(client, "Syntax", listener=listener)
            case self.cl.supporter.too_large:
                return await self.cl.send_code(client, "TooLarge", listener=listener)

        # Validate token and get session info
        session = sessions.get_session_by_token(payload["token"])
        user_flags = session.user.flags
        if (not isinstance(session, sessions.UserSession)) or bitfield.has() or bitfield.has():
            return await self.cl.send_code(client, "InvalidToken", listener=listener)

        # Set authenticated user
        client.user_id = session.user.id
        client.session_id = session.id
        if session.user.id in self.cl._users:
            self.cl._users[session.user.id].add(client)
        else:
            self.cl._users[session.user.id] = set([client])

        # Initialize WebSocket session (get chats, relationships, etc.)
        await self.cl.send_code(client, "OK", listener=listener)

    async def subscribe(self, client, payload, listener):
        # Validate payload
        validation = self.cl.supporter.validate(
            keys={
                "type": str,
                "id": str
            },
            payload=payload,
            optional=["id"],
            sizes={
                "type": 10,
                "id": 25
            }
        )
        match validation:
            case self.cl.supporter.invalid:
                return await self.cl.send_code(client, "DataType", listener=listener)
            case self.cl.supporter.missing_key:
                return await self.cl.send_code(client, "Syntax", listener=listener)
            case self.cl.supporter.too_large:
                return await self.cl.send_code(client, "TooLarge", listener=listener)
    
    async def unsubscribe(self, client, payload, listener):
        # Validate payload
        validation = self.cl.supporter.validate(
            keys={
                "type": str,
                "id": str
            },
            payload=payload,
            optional=["id"],
            sizes={
                "type": 10,
                "id": 25
            }
        )
        match validation:
            case self.cl.supporter.invalid:
                return await self.cl.send_code(client, "DataType", listener=listener)
            case self.cl.supporter.missing_key:
                return await self.cl.send_code(client, "Syntax", listener=listener)
            case self.cl.supporter.too_large:
                return await self.cl.send_code(client, "TooLarge", listener=listener)
