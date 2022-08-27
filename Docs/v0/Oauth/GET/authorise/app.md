# GET V0/Oauth/authorize/app 

## required Auth

- accesss level 3

## args

- json
  - scopes: string
  - app: string
  

## returns

- Code
-  Error (if there is one)
  -  type: str
- json
  - authorized: Bool
  - banned: Bool
  - Scopes: list or string
  - redirect_uri: string
  - redirect_allowed: Bool
  
 