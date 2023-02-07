# Meower Server
This is the backend source code for the Meower social media platform. Built upon Python. Powered by Sanic, MongoDB, Redis, Better Profanity, and Cloudlink 4.

This server software is licensed under the MIT license. See `LICENSE` for details.

> **Warning**
>
> This branch is for finalizing the Meower Server's port to CL4. This is a complete codebase rewrite, and will completely break any existing code. Please use the main branch for the time being.

> **Warning**
>
> Any existing CL4 port branches should NOT be merged. This branch brings major security, performance, and stability enhancemements.

> **Note**
>
> Documentation PRs are permitted. 

> **Warning**
>
> Code changes are ONLY allowed for @tnix100 and @MikeDev101. Any PR requesting changes to code will NOT be permitted until this branch is finalized and the codebase in the main branch merged.

# Dependencies and configuration
### Python
Python dependencies can be installed by running `pip3 install -r requirements.txt`.

### Other server dependencies
These are required for the server to function.
1. MongoDB Community Server >=6.0
2. Redis Server >=7.0

### Extended functionality
This functionality is not required for the server to work, but it is suggested in a production environment.
1. Cloudflare email worker
2. IPHub API key

## Redis `.env` configuration
By default, Meower-Server utilizes a Redis connection on the localhost with no authentication. This is not suggested for a production environment. It is advised to change the server's `.env` file.

* `REDIS_DB` specifies the Redis DB to use. This defaults to `0`.
* `REDIS_HOST` will require an IP address to connect to. This defaults to the localhost, `127.0.0.1`.
* `REDIS_PORT` specifies which port to connect to your Redis server. This defaults to `6379`.
* `REDIS_PASSWORD` is needed if your Redis server requires authentication.

## MongoDB `.env` configuration
By default, Meower-Server utilizes a MongoDB connection on the localhost with no authentication. This is not suggested for a production environment. It is advised to change the server's `.env` file.

* `MONGO_DB` specifies the MongoDB collection to use for storage. This defaults to `meowercl4`.
* `DB_URI` specifies the MongoDB server to connect to. This defaults to `mongodb://127.0.0.1:27017/`.

## Email worker
* `EMAIL_PROVIDER` specifies the email service to use. Defaults to `worker`.
* `EMAIL_WORKER_URI` specifies the server to use for communicating with your email worker.
* `EMAIL_WORKER_TOKEN` is required for authentication.

## IPHub
If the `IPHUB_KEY` argument is left blank, the server will not check client IP addresses. This can lead to ban evasion.
You will need to set up a IPHub account and provide an IPHub API key to enable IP lookup.

## Template `.env`
Below is a template for creating a `.env` file.

```
IPHUB_KEY=
MONGO_DB=meowercl4
IP_HEADER=X-Forwarded-For
DEVELOPMENT=true
EMAIL_PROVIDER=worker
EMAIL_WORKER_URI=
EMAIL_WORKER_TOKEN=
HOST=127.0.0.1
REST_PORT=3000
CL4_PORT=3001
DB_URI=mongodb://127.0.0.1:27017
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

# Security hardening
For a development environment, using the localhost without authentication is acceptable. However, when deploying the server in a production environment, you will need to take the following security considerations:

1. Containerize as much as you can.
2. Firewall as much as possible.
3. Never run the server (or any part of your server) as an administrator/root user.
4. Enforce authentication and access control on your databases.
5. Utilize a zero-trust policy when providing external access.

## Recommendations from the Meower Backend Team
The Meower Backend Team recommends using [Proxmox VE](https://www.proxmox.com/en/proxmox-ve) to run your server and databases.

1. Run the Python server in an up-to-date Ubuntu or Debian container.
2. Utilize the Turnkey-MongoDB container template.
3. Utilize the Turnkey-Redis container template.

*Before launching the server, make sure to update all dependencies to their latest versions. The MongoDB container template is known to use an out-of-date version.*

# API endpoints

> **Note**
>
> Documentation has yet to be completed for this branch. Please check back later.

## CL4 API
This server is CLPv4 and UPLv2.1 compliant. [Visit this page for documentation on the Cloudlink protocol.](https://hackmd.io/@MikeDEV/HJiNYwOfo)

### Notes
All websocket requests and responses are JSON-encoded text frames. 

### All CL4 custom methods

#### `authenticate`
*Request*
```js
{
  "cmd": "authenticate",
  "token": String, // Authentication token
  "listener": String
}
```

*Responses*
```js
{
  "cmd": "statuscode",
  "code": "I:100 | OK",
  "code_id": 100
}
```

```js
{
  "cmd": "ready",
  "session_id": String, // Session ID
  "user": { // User metatdata, such as ID and flags
    // TODO: Doc this
  }, 
  "chats": Array, // Array of string chat IDs
  "following": Array, // Array of string User IDs being followed
  "blocked": Array, // Array of string User IDs being blocked
  "infractions": Array, // TODO: Doc this
  "time_taken": Integer // Epoch?
}
```

#### `subscribe`

#### `unsubscribe`

#### `direct`

### CL4 Error responses

*Invalid datatype(s)*
```js
{
  "cmd": "statuscode",
  "code": "E:109 | Invalid command",
  "code_id": 109
}
```

*Missing arguments / invalid syntax*
```js
{
  "cmd": "statuscode",
  "code": "E:101 | Syntax",
  "code_id": 101
}
```

*Too large argument(s)*
```js
{
  "cmd": "statuscode",
  "code": "E:113 | Too large",
  "code_id": 113
}
```