# Meower-server
Official source code of the Meower server, written in Python. Powered by CloudLink. 

## NOTICE OF END-OF-LIFE
This is the APIv0 Branch of Code! This API code will no longer be maintained as it has been deprecated in favor of APIv1.
Use this code to develop forks of Meower for Scratch clients.

APIv0 will be upgraded automatically to APIv1 when New Meower is released. The API can be found at https://api.meower.org/

## Dependencies
* Run "pip install -r requirements.txt" in the downloaded and unzipped directory

## Running the server
Simply download and run main.py to start the server. Files and directories will be created to store posts, logs, and userdata.

To connect to the server, change the IP settings of your client to connect to ws://127.0.0.1:3000/.

### Rest API

This rest api is configured to use CF Argo Tunnels for getting client IPs, but otherwise everything will function.

Currently supported functions of the API:

/home - Gets the current homepage index.
* /home?page=# - Lets you get a certain page # of the homepage.
* /home?autoget - Automatically fetches all posts currently present on the page.

/ip - Gets the client's IP address and returns with plaintext. Only works if the server is communicating with a client over CF Argo Tunnels.

/posts?id=(Post ID) - Gets a Post ID, use /home to get an index of posts. 

### Trust keys and access control

In development, Meower is configured to use "meower" as a CloudLink Trust key. If you notice a forked server using this key, please request for it to be removed. This key is intended for development purposes only.

Meower is configured to use CloudLink's Trusted Access feature, which implements the following security features:
1. IP blocker feature
2. Client kicking
3. Trust keys
4. Protection from maliciously modified clients

## Contributing to the source

1. Make a fork of the repo.
2. Modify your source.
3. Make a PR request.
