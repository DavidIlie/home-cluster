# Bostan Motivational Meme Engine

Creates a unique absurd motivational poster each run. The engine combines ten
joke families, 100 title directions, 10,000 guided premise combinations, ten
layouts, a small reviewed fallback corpus, and the approved people pool. GPT-5.6
Sol authors six coherent candidates at execution time; validators reject bad
shape contracts and near-duplicates before the renderer sees them.

`STYLE_GUIDE.md` records the visual and joke grammar learned from David's saved
references. `premises.py` supplies structured starting points, `corpus.py` is
the reviewed offline fallback, and `authoring.py` owns the runtime contract.

## Add people

Drop portrait PNG/JPG/WebP files into `assets/people/`. `prepare_assets.py`
creates transparent PNGs atomically, so an interrupted conversion cannot leave
a corrupt portrait in rotation. Use images you own or have permission to reuse.

`import_thread_people.py` imports only the seven portrait attachments David
explicitly supplied for this generator. It deliberately ignores meme
screenshots and generated outputs in the same thread.

## Generate

```bash
./.venv/bin/python prepare_assets.py
./.venv/bin/python meme_engine.py
./.venv/bin/python test_engine.py
```

The PNG appears in `output/`. Recent layouts are tracked in `state.json`,
accepted model specs in `author-history.json`, deliveries in `deliveries.jsonl`,
and reply feedback in `feedback.jsonl`.

## Schedule

Hermes cron schedule (Europe/Bucharest):

```cron
0 0,9-23 * * *
```

The no-agent cron job runs `bostan_meme_hourly.py`, which is paused unless
`BOSTAN_AUTOMATIC_ENABLED=true`. Its generator asks GPT-5.6 Sol at medium
reasoning for a validated runtime spec, renders it, uploads through the bounded
Seedyn broker, verifies the media response, stores the URL-to-spec record, and
prints only the HTTPS URL. Hermes delivers it to Discord channel
`1540773014717726771` (`images`). Replies and threads there route through the
`bostan-meme` skill, which can recover the exact spec and apply feedback.
