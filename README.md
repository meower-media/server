# Meower-Server
Official source code for the backend that powers the Meower social media platform. Powered by [Cloudlink 4.](https://github.com/MikeDev101/cloudlink/)

> **Warning**
>
> This branch is for finalizing the Meower Server's port to CL4. This is a complete codebase rewrite, and will completely break any existing code. Please use the main branch for the time being.

> **Warning**
>
> Any existing CL4 port branches should NOT be merged. This branch brings major security, performance, and stability enhancemements.

# Dependencies
Dependencies can be installed by running `pip3 install -r requirements.txt`.

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
First response, notifies the client that 
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

# Contributing

> **Note**
>
> Documentation PRs are permitted. 

> **Warning**
>
> Code changes are ONLY allowed for @tnix100 and @MikeDev101. Any PR requesting changes to code will NOT be permitted until this branch is finalized and the codebase in the main branch merged.
