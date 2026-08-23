---
name: seedyn-delivery
description: Generate, upload, verify, and deliver images or files through Seedyn and Discord.
---

# Seedyn delivery

Use this workflow whenever David asks you to create, upload, or send a file or
image.

1. If output format materially matters and David did not specify it, use
   `clarify` to ask for PNG, GIF, JPEG, WebP, or the original format. Do not ask
   when the request already determines the format.
2. Generate or create the file with the appropriate tool. For an image request,
   call `image_generate`; never replace that call with prose claiming it ran.
3. Confirm the returned absolute path exists and is a regular non-empty file.
4. Read current Seedyn usage docs with `seedyn_docs` when the contract is not
   already clear. Start with `/llms.txt`; use `/llms.mdx/docs/http-api` for the
   upload contract.
5. Upload through the bounded broker. Never call Seedyn's web login flow and
   never place a Seedyn API key in a command:

   `curl --fail-with-body --silent --show-error -H "Authorization: Bearer $SEEDYN_BROKER_TOKEN" -F "file=@/absolute/path" -F "kind=auto" http://hermes.default.svc.cluster.local:8080/seedyn/upload`

6. Parse the JSON response, require an HTTPS URL on Seedyn's configured media
   hosts (`i.dave.tips` or `i.gurt.ing`), and verify it with a bounded HTTP
   `HEAD` or `GET` request.
7. In the final Discord response, include the verified URL and put
   `MEDIA:/absolute/path` on its own line. Hermes consumes that directive and
   uploads the native attachment; do not wrap it in a code fence.

If Seedyn fails but the local file exists, say Seedyn failed and still use the
`MEDIA:` directive for direct Discord delivery. If generation failed or no file
exists, do not claim anything was uploaded or attached.
