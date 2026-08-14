# DavidApps regional checker readiness

This Kustomization is intentionally not ready to deploy as committed.

Before merging it into the live branch:

1. Replace the gate image placeholder with the digest produced by the current
   `davidapps-auth` release.
2. Replace every value in `secret.sops.yaml` with real encrypted material. The
   database URL must use the dedicated read-only gate role. The shared keys
   must match the identity platform, while the gate seed must be unique to
   `gate-home`.
3. Put the CA that signed the database server certificate in the same Secret.
   The URL already requires `sslmode=verify-full` and points pgx at the mounted
   CA file.
4. Verify that `identity-db.davidapps.dev` resolves to the private central
   database load balancer and is reachable from the home node
   (`192.168.100.180`) on TCP 5432. The central load balancer/firewall must
   restrict that listener to the expected regional source addresses.
5. Prove `/healthz`, `/readyz`, public JWKS retrieval, revocation polling, and
   one complete login round trip before adding nginx auth annotations to apps.

The local Dragonfly is deliberately ephemeral and reachable only by the gate
pod. It stores replay state, not identity data.
