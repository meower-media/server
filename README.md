# Meower-server
Official source code of the Meower server, written in Python. Powered by CloudLink.

## Dependencies
* Run "pip install -r requirements.txt" in the downloaded and unzipped directory

## Running the server
Simply download and run meower.py to start a localhost server.

By default, the server will have debugging info enabled for CloudLink and have 2FA enabled, which requires a valid Scratch account.

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

Meower server v 1.2 i guess
