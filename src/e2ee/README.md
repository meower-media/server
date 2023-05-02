# E2EE Backend
E2EE chats backend for Meower, powered by CloudLink 4.

# Supported clients
* meower-niotron

# Supported cipher types
* RSA/ECB/PKCS1Padding 2048-Bit

# How it (should) work
Under the hood, this is a standard CL4 server with token-based authentication.
Each client will have their own public/private key pair within (some form of) secure storage.

Upon connection:
* The client will authenticate with the server using a Meower session token.
* Upon succcessful authentication, the client will send it's public key to the server.
* The client is now ready to send/receive E2EE chats. 

When a client wants to start a E2EE chat:
* The client will ask the server if the recipient(s) support E2EE.
* If supported, the client will ask the server for a copy of the recipient(s) public key(s).
* Using the retrieved public key(s), the client will create a chat request to the recipient(s).
* The chat request(s) will be sent to the server, and the server will relay the request(s) to the recipient(s).
* The recipient(s) can either accept or deny the request. If accepted, the server will return with a copy of the sender's public key.
* Both sender and recipient(s) will briefly exchange encrypted handshake commands to initialize a E2EE chat.
* The E2EE chat is now operational. Commands will remain the same, but messages between the sender and recipient(s) are encrypted.
