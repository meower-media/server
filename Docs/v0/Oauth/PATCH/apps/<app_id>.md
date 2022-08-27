# PATCH v0/oauth/apps/\<app_id>

## required auth

- required auth level 5
- scopes
  - foundation:oauth:apps

## args

- json
  - owner: optional[string] 
  - name: optional[string]
  - description: optional[string]
  - add_bans: optional[list[v0User._Id]]
  - remove_bans: optional[list[v0User._Id]]
  - add_redirects: optional[list[string]]
  - remove_redirects: optional[list[string]]
  - refresh_secret: optional[bool]
  
## Returns

- Status
- V0App

  
