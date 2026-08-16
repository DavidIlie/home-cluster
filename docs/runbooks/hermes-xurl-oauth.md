# Herm xurl OAuth setup

Herm receives the official `xdevplatform/xurl` v1.3.1 Linux x86_64 binary at
pod startup. The deployment verifies the release archive checksum before making
the binary available to subprocesses on `PATH`. xurl stores its state only in
the persistent `/opt/data/home/.xurl` directory because its deployment wrapper
runs xurl with `HOME=/opt/data/home` without changing Herm's general home.

Do not put X client credentials, tokens, authorization codes, or the contents of
`.xurl` in Git, shell transcripts, tickets, or logs. This runbook is an
interactive operator procedure. It does not authorize X writes or automation.

## Authenticate interactively

1. Configure the X developer app's callback URL exactly as:

   `http://localhost:8080/callback`

2. Open an interactive shell in the Herm pod:

   ```sh
   kubectl -n default exec -it deploy/hermes-agent -- sh
   ```

3. Confirm the expected binary is active, then register a named app. Read the
   values into temporary shell variables so they are not written into shell
   history; the secret input is hidden. Clear both variables immediately after
   xurl stores the app in `/opt/data/home/.xurl/auth.yml`.

   ```sh
   xurl version
   read -r -p 'X client ID: ' X_CLIENT_ID
   read -r -s -p 'X client secret: ' X_CLIENT_SECRET; printf '\n'
   xurl auth apps add david-x \
     --client-id "$X_CLIENT_ID" \
     --client-secret "$X_CLIENT_SECRET" \
     --redirect-uri http://localhost:8080/callback
   unset X_CLIENT_ID X_CLIENT_SECRET
   ```

4. Start the headless OAuth flow bound explicitly to that app. Open the printed
   authorization URL locally, approve it, and paste the resulting redirect URL
   or code back into the prompt. The `--headless` flow is required because the
   pod cannot receive a callback sent to the operator workstation's localhost.

   ```sh
   xurl auth oauth2 --app david-x --headless
   ```

   If account discovery cannot select the intended account, supply the X
   username explicitly (without `@`):

   ```sh
   xurl auth oauth2 USERNAME --app david-x --headless
   ```

5. Select the named app as the default. Add the username when the app has more
   than one authenticated user or default-user selection is ambiguous.

   ```sh
   xurl auth default david-x
   xurl auth default david-x USERNAME
   ```

## Verify read access

Run only these non-mutating checks. Use the explicit app binding for the first
pass so a stale default cannot mask a setup problem.

```sh
xurl auth status --app david-x
xurl whoami --app david-x
xurl timeline --app david-x --max-results 5
```

Do not create the daily cron until all three commands succeed with the intended
account and the small home-timeline read returns successfully. Do not test with
`post`, `like`, `repost`, `follow`, or any other X write command.
