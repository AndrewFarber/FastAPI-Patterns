---
title: "TLS to Amazon RDS"
category: persistence
tags: [settings, database, aws-rds, tls]
status: draft
related: ["[[2b-settings-db]]", "[[2b-settings-db-iam-auth]]", "[[2b-settings-db-rotated-password]]", "[[1e-settings-lambda]]"]
---

# TLS to Amazon RDS

## Problem
`sslmode=verify-full` ([[2b-settings-db]]) needs the CA that signed the server's certificate. Neither RDS's own CA nor the OS trust store can be relied on: the RDS CA isn't in any OS store, and `psycopg[binary]` ships its own OpenSSL, which looks for the OS store at a build path that doesn't exist (`sslrootcert=system` fails). The app needs a CA bundle file.

## Use when
- The app connects to Amazon RDS or Aurora PostgreSQL, directly or through RDS Proxy.

## Avoid when
- The database isn't on AWS: ship that provider's CA bundle the same way.

## Solution
AWS recommends `sslmode=verify-full` with a root CA bundle: it encrypts the connection *and* checks that the server is the one named in `host`. RDS for PostgreSQL 15+ also rejects non-TLS connections by default (`rds.force_ssl=1`).

The image ships two bundles (the full Dockerfile is in [[1e-settings-lambda]]):

```dockerfile
# Dockerfile (fragment)
# CA bundles for DB__SSLROOTCERT. Files added from a URL are mode 600, and Lambda
# runs the image as a non-root user, so make them readable.
# RDS instances: the RDS global bundle
ADD --chmod=644 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /etc/ssl/certs/rds-global-bundle.pem
# RDS Proxy: the Amazon Trust Services roots behind its ACM certificate, in one file
ADD --chmod=644 https://www.amazontrust.com/repository/AmazonRootCA1.pem \
    https://www.amazontrust.com/repository/AmazonRootCA2.pem \
    https://www.amazontrust.com/repository/AmazonRootCA3.pem \
    https://www.amazontrust.com/repository/AmazonRootCA4.pem /tmp/amazon-roots/
RUN cat /tmp/amazon-roots/*.pem > /etc/ssl/certs/amazon-root-cas.pem && rm -r /tmp/amazon-roots
```

### RDS instance
```bash
DB__HOST=orders.abc123.us-east-1.rds.amazonaws.com
DB__SSLMODE=verify-full
DB__SSLROOTCERT=/etc/ssl/certs/rds-global-bundle.pem
```

- Use the **global bundle**: it holds the root CAs for every commercial region. Trust only root CAs, never intermediates; RDS rotates server certificates automatically and intermediates break that.
- `verify-full` checks the hostname, so `host` must be the RDS endpoint.

### RDS Proxy
RDS Proxy pools connections in front of the database, absorbs connection surges, and speeds up failover. On Lambda, where every new execution environment opens its own connection, it's the recommended front ([[1e-settings-lambda]]). Its certificates come from ACM and chain to the Amazon Root CAs, not the RDS CA:

```bash
DB__HOST=orders-proxy.proxy-abc123.us-east-1.rds.amazonaws.com
DB__SSLMODE=verify-full
DB__SSLROOTCERT=/etc/ssl/certs/amazon-root-cas.pem
```

How the app authenticates to the proxy is a `DbAuth` choice ([[2b-settings-db]]):

| Client to proxy | `DB__AUTH__METHOD` | Proxy to database |
|---|---|---|
| IAM token for the proxy endpoint | `iam` ([[2b-settings-db-iam-auth]]) | The secret registered with the proxy, or end-to-end IAM |
| Database password, the same one as in the proxy's secret | `rotated_secret` ([[2b-settings-db-rotated-password]]) or `password` | The secret registered with the proxy |

- **`iam` is simplest on Lambda.** The function needs no access to the database secret; the proxy reads it, rotated or not.
- **The proxy reads the secret itself.** It doesn't support the alternating-users rotation strategy, so rotate the secrets it reads with single-user rotation ([[2b-settings-db-rotated-password]]).

### AWS Advanced Python Wrapper
AWS's driver wrapper for psycopg adds plugins for IAM auth, Secrets Manager, and fast failover (mainly for Aurora). It supports SQLAlchemy and can replace the hand-written `do_connect` hooks in [[2b-settings-db-iam-auth]] and [[2b-settings-db-rotated-password]].

## Pitfalls
- **`sslrootcert=system` with `psycopg[binary]`.** The bundled OpenSSL's default CA path points at a build directory, so verification fails on every host. `DbSettings` accepts only a file.
- **Custom DNS names for `host`.** `verify-full` checks the endpoint's hostname, so a Route 53 alias fails verification.
- **Trusting intermediate certificates.** Breaks when RDS rotates its server certificates; trust the root bundle only.
- **The RDS bundle for RDS Proxy.** The proxy's certificate isn't signed by the RDS CA; use the Amazon Root CA bundle.
- **`ADD` from a URL without `--chmod`.** The file is mode 600, owned by root; Lambda's non-root user can't read it and every connection fails.

## Related
- [[2b-settings-db]]
- [[2b-settings-db-iam-auth]]
- [[2b-settings-db-rotated-password]]
- [[1e-settings-lambda]]
