import time

from src.cl4.cloudlink import cloudlink
from src.util import events
from src.entities import sessions, chats, infractions

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

        # Check whether the client is already authenticated
        if client.user_id is not None:
            return await self.cl.send_code(client, "IDSet", listener=listener)

        # Start session start timer
        timer_start = time.time()

        # Validate token and get session info
        session = sessions.get_session_by_token(payload["token"])
        if (not isinstance(session, sessions.UserSession)):
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
        await self.cl.send_packet_unicast(
            client,
            "ready",
            {
                "session_id": session.id,
                "user": session.user.client,
                "chats": [chat.public for chat in chats.get_active_chats(session.user)],
                "following": session.user.get_following_ids(),
                "blocked": session.user.get_blocked_ids(),
                "infractions": [infraction.client for infraction in infractions.get_user_infractions(session.user)],
                "time_taken": int((time.time()-timer_start)*1000)
            },
            listener=listener,
            quirk=self.cl.supporter.quirk_update_msg
        )

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

        # Check whether the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "IDRequired", listener=listener)

        # Add client to subscription
        if payload["type"] == "new_posts":
            self.cl._subscriptions["new_posts"].add(client)
        elif payload["type"] in ["users", "posts", "comments"]:
            if payload["id"] in self.cl._subscriptions[payload["type"]]:
                self.cl._subscriptions[payload["type"]][payload["id"]].add(client)
            else:
                self.cl._subscriptions[payload["type"]][payload["id"]] = set([client])
        else:
            return await self.cl.send_code(client, "InvalidSubscriptionType", listener=listener)

        return await self.cl.send_code(client, "OK", listener=listener)
    
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

        # Check whether the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "IDRequired", listener=listener)

        # Remove client from subscription
        if payload["type"] == "new_posts":
            if client in self.cl._subscriptions["new_posts"]:
                self.cl._subscriptions["new_posts"].remove(client)
        elif payload["type"] in ["users", "posts", "comments"]:
            if payload["id"] in self.cl._subscriptions[payload["type"]]:
                if client in self.cl._subscriptions[payload["type"]][payload["id"]]:
                    self.cl._subscriptions[payload["type"]][payload["id"]].remove(client)
                if len(self.cl._subscriptions[payload["type"]][payload["id"]]) == 0:
                    del self.cl._subscriptions[payload["type"]][payload["id"]]
        else:
            return await self.cl.send_code(client, "InvalidSubscriptionType", listener=listener)

        return await self.cl.send_code(client, "OK", listener=listener)

    async def direct(self, client, payload, listener):
        # Validate payload
        validation = self.cl.supporter.validate(
            keys={
                "val": str,
                "id": str
            },
            payload=payload,
            optional=[],
            sizes={
                "val": 1000,
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

        # Check whether the client is authenticated
        if not client.user_id:
            return await self.cl.send_code(client, "IDRequired", listener=listener)

        # Emit event
        events.emit_event("cl_direct", payload["id"], {
            "val": payload["val"],
            "origin": client.user_id
        })

        return await self.cl.send_code(client, "OK", listener=listener)
