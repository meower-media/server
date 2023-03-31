import time

from src.util import events
from src.entities import sessions, accounts, applications, chats, infractions


class commands:
    def __init__(self, server, protocol):
    
        # Extend the clpv4 protocol's schemas
        protocol.schema.authenticate = {
            "cmd": {
                "type": "string",
                "required": True
            },
            "val": {
                "type": "string",
                "required": True
            }
        }
        
        protocol.schema.subscriptions = {
            "cmd": {
                "type": "string",
                "required": True
            },
            "type": {
                "type": "string",
                "required": True,
                "max_length": 10
            },
            "id": {
                "type": "string",
                "required": False,
                "max_length": 25
            }
        }
        
        @server.on_command(cmd="authenticate", schema=protocol.schema)
        async def authenticate(client, message):
            await protocol.automatic_notify_handshake(client)
            
            # Validate payload
            if not protocol.valid(client, message, protocol.schema.authenticate):
                return

            # Check whether the client is already authenticated
            if client.user_id:
                protocol.send_statuscode(
                    client=client,
                    code=protocol.statuscodes.id_already_set,
                    message=message
                )
                return

            # Start session start timer
            timer_start = time.time()

            # Get session info
            session = sessions.get_session_by_token(payload["val"])

            # Set session info
            client.user_id = session.user.id
            client.session_id = session.id
            if client.user_id in self.cl._users:
                self.cl._users[client.user_id].add(client)
            else:
                self.cl._users[client.user_id] = {client}

            # Subscribe to chats
            for chat_id in chats.get_all_chat_ids(client.user_id):
                if chat_id not in self.cl._subscriptions["chats"]:
                    self.cl._subscriptions["chats"][chat_id] = set()
                self.cl._subscriptions["chats"][chat_id].add(client)

            # Initialize WebSocket session (get user, chats, relationships, etc.)
            protocol.send_statuscode(
                client,
                protocol.schema.ok,
                message=message
            )
            
            protocol.send_message(
                client,
                {
                    "cmd": "ready",
                    "val": {
                        "session_id": client.session_id,
                        "bot_session": isinstance(session, sessions.BotSession),
                        "user": session.user.client,
                        "account": (accounts.get_account(session.user.id).client if isinstance(session, sessions.UserSession) else None),
                        "application": (applications.get_application(session.user.id).client if isinstance(session, sessions.BotSession) else None),
                        "chats": [chat.public for chat in chats.get_active_chats(session.user)],
                        "following": session.user.get_following_ids(),
                        "blocked": session.user.get_blocking_ids(),
                        "infractions": [infraction.client for infraction in infractions.get_user_infractions(session.user)],
                        "time_taken": int((time.time() - timer_start) * 1000)
                    }
                },
                message=message
            )
        
        @server.on_command(cmd="subscribe", schema=protocol.schema)
        async def subscribe(client, message):
            await protocol.automatic_notify_handshake(client)
            
            # Validate payload
            if not protocol.valid(client, message, protocol.schema.subscriptions):
                return

            # Add client to subscription
            if message["type"] == "new_posts":
                self.cl._subscriptions["new_posts"].add(client)
            elif message["type"] in ["users", "posts", "comments"]:
                if message["id"] in self.cl._subscriptions[message["type"]]:
                    self.cl._subscriptions[message["type"]][message["id"]].add(client)
                else:
                    self.cl._subscriptions[message["type"]][message["id"]] = {client}
            else:
                protocol.send_statuscode(
                    client,
                    protocol.schema.invalid_subscription_type,
                    message=message
                )
                return
            
            protocol.send_statuscode(
                client,
                protocol.schema.ok,
                message=message
            )
        
        @server.on_command(cmd="unsubscribe", schema=protocol.schema)
        async def unsubscribe(client, message):
            await protocol.automatic_notify_handshake(client)
            
            # Validate payload
            if not protocol.valid(client, message, protocol.schema.subscriptions):
                return

            # Remove client from subscription
            if message["type"] == "new_posts":
                if client in self.cl._subscriptions["new_posts"]:
                    self.cl._subscriptions["new_posts"].remove(client)
            elif message["type"] in ["users", "posts", "comments"]:
                if message["id"] in self.cl._subscriptions[message["type"]]:
                    if client in self.cl._subscriptions[message["type"]][message["id"]]:
                        self.cl._subscriptions[message["type"]][message["id"]].remove(client)
                    if len(self.cl._subscriptions[message["type"]][message["id"]]) == 0:
                        del self.cl._subscriptions[message["type"]][message["id"]]
            else:
                protocol.send_statuscode(
                    client,
                    protocol.schema.invalid_subscription_type,
                    message=message
                )
                return

            protocol.send_statuscode(
                client,
                protocol.schema.ok,
                message=message
            )
        
        # Monkey-patch the function
        async def direct(client, message):
            await protocol.automatic_notify_handshake(client)
            
            # Validate schema
            if not valid(client, message, cl4_protocol.direct):
                return
            
            # Emit event
            events.emit_event("cl_direct", message["id"], {
                "val": message["val"],
                "origin": client.user_id
            })
            
            # Return statuscode
            protocol.send_statuscode(
                client,
                protocol.schema.ok,
                message=message
            )
        
        # Patch the function
        protocol.on_direct = direct
