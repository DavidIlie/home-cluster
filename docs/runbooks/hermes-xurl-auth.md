# Herm xurl authentication

Herm includes the official `xdevplatform/xurl` CLI, pinned to v1.3.1. Its
`HOME` is the persistent `/opt/data/home` directory, so xurl stores
authentication under `/opt/data/home/.xurl`. The same persistent volume remains
mounted at `/data` for Herm's existing state. The GitOps configuration contains
no X credentials.

Do this interactively as David, outside an agent session. Do not paste secrets
into chat, logs, repository files, or shell commands retained in history. The X
developer app must allow this exact redirect URI:

```text
http://localhost:8080/callback
```

Open a shell in the Herm container with shell tracing disabled, then register a
clearly named app. Read the values interactively so they are not retained in
shell history (the secret prompt intentionally shows no input):

```sh
set +x
printf 'Client ID: '; IFS= read -r XURL_CLIENT_ID
printf 'Client secret: '; IFS= read -rs XURL_CLIENT_SECRET; printf '\n'
xurl auth apps add herm --client-id "$XURL_CLIENT_ID" --client-secret "$XURL_CLIENT_SECRET" --redirect-uri http://localhost:8080/callback
unset XURL_CLIENT_ID XURL_CLIENT_SECRET
xurl auth oauth2 --app herm --headless
```

Open the printed authorization URL in David's browser. After approval, paste
the resulting redirect URL (or its `code` value) into xurl. A browser error at
the localhost redirect is expected during the headless flow.

If X does not return the username reliably, repeat OAuth with David's X handle
as the explicit fallback (without the `@`):

```sh
xurl auth oauth2 --app herm --headless DAVID_X_USERNAME
```

Select the named app and account as defaults. The second form is preferred
when the username fallback was needed:

```sh
xurl auth default herm
xurl auth default herm DAVID_X_USERNAME
```

Verify without displaying or reading files below `$HOME/.xurl`:

```sh
xurl auth status
xurl whoami
xurl '/2/users/USER_ID/timelines/reverse_chronological?max_results=5&tweet.fields=created_at'
```

Replace `USER_ID` with the ID reported by `xurl whoami`. All three checks are
read-only. Do not configure autonomous X writes. Do not create the recurring
Hermes cron until these checks succeed against the live authenticated account.
