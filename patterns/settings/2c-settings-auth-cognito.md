---
title: "Auth settings for AWS Cognito"
category: auth-security
tags: [settings, authentication, cognito, jwt]
status: draft
related: ["[[2c-settings-auth]]", "[[1e-settings-lambda]]"]
---

# Auth settings for AWS Cognito

## Problem
Cognito tokens don't follow the usual OIDC conventions for APIs: by default, access tokens have no `aud` claim, and access and ID tokens are told apart by a custom `token_use` claim. Configured like any other provider, every token either fails the audience check or the check gets disabled.

## Use when
- Users sign in through an AWS Cognito user pool and the API verifies Cognito access tokens with `AuthSettings` ([[2c-settings-auth]]).

## Avoid when
- The API sits behind API Gateway with a Cognito authorizer, which already verifies tokens. A Lambda Function URL has no Cognito authorizer, so behind a Function URL the app verifies tokens itself, as this note configures ([[1e-settings-lambda]]).

## Solution
No code changes: Cognito is configured through the general `AuthSettings` fields.

```bash
AUTH__ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbC123xyz
# JSON values are single-quoted for the shell
AUTH__AUDIENCES='["1example23456789"]'
AUTH__AUDIENCE_CLAIM=client_id
AUTH__REQUIRED_CLAIMS='{"token_use": "access"}'
```

- **Issuer:** `https://cognito-idp.<region>.amazonaws.com/<user pool ID>`. The JWKS is at the default `{issuer}/.well-known/jwks.json`, so `jwks_url` stays unset.
- **Audience:** access tokens carry the app client in `client_id`, so `audience_claim=client_id`. `audiences` lists the app clients allowed to call the API; tokens from other clients in the same pool are rejected.
- **Token type:** `token_use: access` rejects ID tokens. To accept ID tokens instead (rarely right for an API), use `audience_claim=aud` and `token_use: id`.
- **Algorithm:** Cognito signs with `RS256`, the default.

### With resource indicators
Since October 2025, a client can request an access token for one API by sending a `resource` parameter (authorization code and implicit grants, Essentials or Plus tier with managed login). Cognito then sets `aud` to that resource, and the API checks it like any other provider's:

```bash
AUTH__ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbC123xyz
AUTH__AUDIENCES='["https://orders.example.com"]'
AUTH__REQUIRED_CLAIMS='{"token_use": "access"}'
```

Use it when several APIs share one user pool: `client_id` says which app asked for the token, `aud` says which API it is for. Tokens requested without `resource` have no `aud` and are rejected, so switch only once every client sends it.

## Pitfalls
- **Checking `aud` on access tokens without resource indicators.** They don't have one; the check fails every token, or gets disabled. Use `audience_claim=client_id`.
- **Omitting `token_use`.** Without it, ID tokens from the same app client pass as access tokens.
- **Listing every app client in the pool.** Only clients that should call this API belong in `audiences`.

## Related
- [[2c-settings-auth]]
- [[1e-settings-lambda]]
