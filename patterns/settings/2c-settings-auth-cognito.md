---
title: "Auth settings for AWS Cognito"
category: auth-security
tags: [settings, authentication, cognito, jwt]
status: draft
related: ["[[2c-settings-auth]]"]
---

# Auth settings for AWS Cognito

Configure Cognito through the general `AuthSettings` ([[2c-settings-auth]]), not special code: the audience is read from `client_id`, and `token_use: access` is a required claim.

## Fits when
- Users sign in through a Cognito user pool and the API verifies Cognito access tokens itself.

Not when:
- API Gateway with a Cognito authorizer already verifies them.

## Signals
- **Feature:** "Cognito", "user pool".
- **Code:** `verify_aud=False` for Cognito tokens; no `token_use` check; a Cognito-specific verifier next to a generic one.

## Pattern
```bash
AUTH__ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbC123xyz
AUTH__AUDIENCES='["1example23456789"]'
AUTH__AUDIENCE_CLAIM=client_id
AUTH__REQUIRED_CLAIMS='{"token_use": "access"}'
```

## Rules
- **`audience_claim=client_id`:** Cognito access tokens have no `aud` by default. `audiences` lists only the app clients allowed to call this API.
- **`token_use: access`** rejects ID tokens from the same client.
- **With resource indicators** (clients send `resource`), Cognito sets `aud`: drop `AUTH__AUDIENCE_CLAIM` and list the API's identifier. Switch only once every client sends it.
- JWKS at the default `{issuer}/.well-known/jwks.json`; algorithm `RS256`, the default.

## Anti-patterns
- **Checking `aud` without resource indicators.** Every token fails, so someone disables the check.
- **Listing every app client in the pool.** Only API callers belong in `audiences`.

## Related
- [[2c-settings-auth]]
