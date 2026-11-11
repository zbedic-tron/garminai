# Separate public architecture

```
ChatGPT (MCP client)
      | (future OAuth to GarminAI service)
GarminAI Public MCP Server  [v0.1: DEMO ONLY]
      | tools -> demo activity JSON + reviewed literature catalogue
      |
      +-- later: authenticated GarminAI user identity
      +-- later: official Garmin OAuth consent, encrypted per-user credentials
      +-- later: background sync, isolated per-user storage + deletion
```

Never identify users using an untrusted `user_id` tool parameter. Production server must derive identity from validated authorization tokens and enforce isolation. Garmin OAuth authorization and ChatGPT-to-GarminAI user login are **separate** trust boundaries.

Do not deploy demo server publicly without authentication. Github Pages remains static marketing website only.


> UPDATE v0.3: for current instructions see `DEPLOY_V03_SR.md` and `SECURITY_AND_OAUTH_SR.md`. Demo MCP now requires development Bearer token. No real-user OAuth yet.
