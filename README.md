# Meower Server
This is the backend source code for the Meower social media platform powered by Python, Sanic, MongoDB, Redis, Better Profanity, and CloudLink 4.

This server software is licensed under the MIT license. See `LICENSE` for details.

> **Warning**
>
> This branch is for the Meower Server's port to CL4, a complete rewrite that will break all existing code. Please use the main branch for the time being. 

## Configuring Meower Server
### Docker (recomended)
To run Meower Server in a Docker container, you will need Docker, Docker Compose, and git installed. Running the following will create and run a working instance of Meower Server that you can then configure later:

```sh
git clone https://github.com/meower-media-co/meower-server
git checkout main-cl4-branch
git pull
docker-compose build
docker-compose up -d
```
### Proxmox  (recomended)
Here's a small guide on how to use [Proxmox VE](https://www.proxmox.com/en/proxmox-ve) to run your server and databases.

1. Create a Debian/Ubuntu container
2. Install `git` and `python3`
3. Checkout the `main-cl4-branch` of the `https://github.com/meower-media-co/meower-server` repository
4. Create a MongoDB instance using the Turnkey-MongoDB container template
5. Create a Redis instance using the Turnkey-Redis container template
6. Update the MongoDB and Redis containers to version 6 or higher and version 7 or higher respectively
7. Install Python dependencies using `pip3 install -r requirements.txt`
8. Configure your instance (see below)
9. Run `startServer.sh`

### Run locally (development use)
**DO NOT RUN A PRODUCTION SERVER USING THIS METHOD**

To run Meower Server locally, you'll need to have Python 3 and Git installed and an instance of MongoDB 6 or higher and Redis 7 or higher to have your server to connect to.

Follow the Git commands in the Docker guide to clone the Git repo then do the following:
1. Install dependencies using `pip3 install -r requirements.txt`
2. Configure your instance (see below)
3. Run `startServer.sh`

## Configuring your instance
### MongoDB & Redis
By default, Meower Server tries to connect to an instance of Mongo and Redis running on `127.0.0.1`. You can change this and set up authentication by setting the corresponding env vars which are listed in `.env.example`.

### Extended functionality
Meower Server is able to send emails and allow for IP blocking if you configure certain env vars. These are listed in `.env.example` alongside comments explaining them. If you don't set these up, email sending and IP blocking won't work, which may lead to ban evasion.

### Security hardening
For a development environment, most of the defaults should work fine, but in a production envirement you should consider the following:
1. Containerize as much as you can.
2. Firewalling as much as possible.
3. Never running the server (or any part of your server) as an administrator/root user.
4. Enforcing authentication and access control on your databases.
5. Using zero-trust policies when providing external access.

# API endpoints

> **Note**
>
> Documentation has yet to be completed for this branch. Please check back later.

## CloudLink API
This server utilizes CloudLink 4. Documentation can be found [here](https://github.com/MikeDev101/cloudlink/wiki).

This server also utilizes a custom CloudLink 3 implementation to retain backwards compatibility with older Meower Clients. This legacy websocket endpoint will be retired in the near future, so documentation will not be provided.

### Notes
All websocket requests and responses are JSON-encoded text frames.

Certain commands are disabled in this server, such as:
* `setid`
* `gmsg` and `gvar`
* `pvar`
* `link` and `unlink`

These commands have modified behavior:
* `direct`
* `handshake`

### Meower-Specific commands

#### `handshake`
This is a standard command used in a vanilla CL4 server. This has been modified for authentication purposes.
You can connect to the server and specify your session token in this command, or omit the val key if you
provide the session token using a Authorization header upon connection to the websocket server.

*Request*
```js
{
  "cmd": "handshake",
  "val": String // Session token, required for browsers, optional if Authorization header is provided
}
```

*Response*
```js
{
  "cmd": "statuscode",
  "code": "I:100 | OK",
  "code_id": 100
}
```

#### `subscribe`

#### `unsubscribe`

#### `direct`

### Meower-Specific Error Codes

*Invalid token*
```js
{
  "cmd": "statuscode",
  "code": "E:200 | Invalid token",
  "code_id": 200
}
```

*Invalid subscription*
```js
{
  "cmd": "statuscode",
  "code": "E:201 | Invalid subscription type",
  "code_id": 201
}
```
