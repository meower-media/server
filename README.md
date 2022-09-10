# Meower-Server
Official source code of the Meower server, written in Python. Powered by Cloudlink 4.

***DO NOT USE THIS BRANCH!!!***
This is a separate branch for porting the current Meower 5.7 server to Cloudlink 4 and for major code restructuring/cleanup. This is highly experimental, and there will be bugs. Please use the main branch for now.

## Installing Dependencies
* Run `pip3 install -r requirements.txt` prior to starting the server. Cloudlink 4 is bundled with the server.

## Running the server
Simply download and run main.py to start the server. Files and directories will be created to store posts, logs, and userdata.
To connect to the server, change the IP settings of your client to connect to ws://127.0.0.1:3000/.

### Rest API

* /home - Gets the current homepage index.
* /home?page=# - Lets you get a certain page # of the homepage.
* /home?autoget - Automatically fetches all posts currently present on the page.
* /ip - Gets the client's IP address and returns with plaintext. Only works if the server is communicating with a client over CF Argo Tunnels.
* /posts?id=(Post ID) - Gets a Post ID, use /home to get an index of posts.
* /status - Status for the Meower Server.
* /posts/(Chat ID) - Gets the specified chat ID's index.
* /reports - Gets the reports index (only accessable if a moderator or higher.
* /inbox - Gets the specified user's inbox.
* /search/home?q=(Query) - Searches home.
* /search/users?q=(Query) - Searches users.
* /users/(Username) - Gets the specified user's info.
* /users/(Username)/posts - Gets the specified user's posts.
* /statistics - Shows Meower's statistics (users, posts, and chats)

## Contributing to the source

1. Make a fork of the repo
2. Modify your source
3. Open a PR
