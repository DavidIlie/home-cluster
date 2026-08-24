---
name: bostan-meme
description: Generate, critique, correct, and send original absurd Bostan mindset posters for David, including replies to previously delivered Seedyn images.
---

# Bostan meme

Use this only in David's `friends-david` profile.

## New poster

Run the reviewed author-render-upload pipeline with the terminal tool:

`/opt/data/profiles/friends-david/workspace/meme-engine/.venv/bin/python /opt/data/profiles/friends-david/workspace/meme-engine/cron_hourly.py`

It asks GPT-5.6 Sol at medium reasoning to author six coherent candidates from a
10,000-premise guide, validates novelty and geometry, renders the strongest,
uploads through the bounded Seedyn broker, verifies the returned image, and
records the exact spec behind its URL. Return only the HTTPS URL.

## Feedback on a delivered poster

When David replies to a Seedyn poster URL or writes in a thread created from
that delivery, extract the exact `https://i.gurt.ing/...` URL from the replied
message or reply-context block. Never guess which image he means.

Write David's feedback verbatim to `/tmp/bostan-feedback.txt` with the file
tool. If it is praise or a preference with no requested correction, record it:

`/opt/data/profiles/friends-david/workspace/meme-engine/.venv/bin/python /opt/data/profiles/friends-david/workspace/meme-engine/feedback.py record --url URL --text-file /tmp/bostan-feedback.txt --disposition positive`

If the feedback identifies anything wrong, requests a change, or says to try
again, immediately generate a corrected version:

`/opt/data/profiles/friends-david/workspace/meme-engine/.venv/bin/python /opt/data/profiles/friends-david/workspace/meme-engine/cron_hourly.py --feedback-url URL --feedback-file /tmp/bostan-feedback.txt`

The correction pipeline loads the exact prior spec and all earlier feedback,
keeps uncriticized parts, authors and validates the correction, records the
replacement relationship, uploads it, and prints the new URL. Return only that
URL. Do not call image generation, reproduce secret values, add status prose,
or end with "how can I help".
