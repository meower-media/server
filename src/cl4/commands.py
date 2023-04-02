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
                "required": False
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
        
        # Patched command
        @server.on_command(cmd="handshake", schema=protocol.schema)
        async def handshake(client, message):
            # Validate payload
            if not protocol.valid(client, message, protocol.schema.authenticate):
                return
            
            # Handshake responses
            if not client.handshake:
                client.handshake = True
                
                # Send client IP address
                server.send_packet(client, {
                    "cmd": "client_ip",
                    "val": protocol.get_client_ip(client)
                })

                # Send server version
                server.send_packet(client, {
                    "cmd": "server_version",
                    "val": server.version
                })

                # Send Message-Of-The-Day
                if protocol.enable_motd:
                    server.send_packet(client, {
                        "cmd": "motd",
                        "val": protocol.motd_message
                    })

                # Send client's Snowflake ID
                server.send_packet(client, {
                    "cmd": "client_obj",
                    "val": protocol.generate_user_object(client)
                })
            
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

            # Get session token
            token = client.request_headers.get("Authorization")
            if not token:
                if "val" not in message:
                    protocol.send_statuscode(
                        client=client,
                        code=protocol.statuscodes.session_token_missing,
                        message=message
                    )
                    return
                
                # Get session token
                token = message["val"]
            
            # Get session info
            session = sessions.get_session_by_token(token)
            
            # Exit command handler if the session is invalid
            if not session:
                protocol.send_statuscode(
                    client,
                    protocol.statuscodes.invalid_token,
                    message=message
                )
                return

            # Set session info
            client.user_id = session.user.id
            client.session_id = session.id
            if client.user_id in server._users:
                server._users[client.user_id].add(client)
            else:
                server._users[client.user_id] = {client}

            # Subscribe to chats
            for chat_id in chats.get_all_chat_ids(client.user_id):
                if chat_id not in server._subscriptions["chats"]:
                    server._subscriptions["chats"][chat_id] = set()
                server._subscriptions["chats"][chat_id].add(client)

            # Initialize WebSocket session (get user, chats, relationships, etc.)
            protocol.send_statuscode(
                client,
                protocol.statuscodes.ok,
                message=message
            )
        
        @server.on_command(cmd="subscribe", schema=protocol.schema)
        async def subscribe(client, message):
            # Validate payload
            if not protocol.valid(client, message, protocol.schema.subscriptions):
                return

            # Add client to subscription
            if message["type"] == "new_posts":
                server._subscriptions["new_posts"].add(client)
            elif message["type"] in ["users", "posts", "comments"]:
                if message["id"] in server._subscriptions[message["type"]]:
                    server._subscriptions[message["type"]][message["id"]].add(client)
                else:
                    server._subscriptions[message["type"]][message["id"]] = {client}
            else:
                protocol.send_statuscode(
                    client,
                    protocol.statuscodes.invalid_subscription_type,
                    message=message
                )
                return
            
            protocol.send_statuscode(
                client,
                protocol.statuscodes.ok,
                message=message
            )
        
        @server.on_command(cmd="unsubscribe", schema=protocol.schema)
        async def unsubscribe(client, message):
            # Validate payload
            if not protocol.valid(client, message, protocol.schema.subscriptions):
                return

            # Remove client from subscription
            if message["type"] == "new_posts":
                if client in server._subscriptions["new_posts"]:
                    server._subscriptions["new_posts"].remove(client)
            elif message["type"] in ["users", "posts", "comments"]:
                if message["id"] in server._subscriptions[message["type"]]:
                    if client in server._subscriptions[message["type"]][message["id"]]:
                        server._subscriptions[message["type"]][message["id"]].remove(client)
                    if len(server._subscriptions[message["type"]][message["id"]]) == 0:
                        del server._subscriptions[message["type"]][message["id"]]
            else:
                protocol.send_statuscode(
                    client,
                    protocol.statuscodes.invalid_subscription_type,
                    message=message
                )
                return

            protocol.send_statuscode(
                client,
                protocol.statuscodes.ok,
                message=message
            )
        
        # Patched command
        @server.on_command(cmd="direct", schema=protocol.schema)
        async def direct(client, message):
            # Validate schema
            if not protocol.valid(client, message, protocol.schema.direct):
                return
            
            # Check whether the client is already authenticated
            if not client.user_id:
                protocol.send_statuscode(
                    client=client,
                    code=protocol.statuscodes.id_required,
                    message=message
                )
                return
            
            # Emit event
            events.emit_event("cl_direct", message["id"], {
                "val": message["val"],
                "origin": client.user_id
            })
            
            # Return statuscode
            protocol.send_statuscode(
                client,
                protocol.statuscodes.ok,
                message=message
            )
