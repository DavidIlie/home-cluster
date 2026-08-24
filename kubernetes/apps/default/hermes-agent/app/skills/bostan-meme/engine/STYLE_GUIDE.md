# Bostan poster grammar

The twelve saved references in `~/Downloads/mmemes`, the supplied Discord
thread images, and the Apple Photos `memes` album establish the house style.

- Black or near-black background, one dominant portrait, condensed all-caps type.
- A plausible self-help or money headline starts the bit.
- Four to six terse entries answer the headline directly. Except for a real
  timetable, each entry works alone and does not depend on the previous row.
- Most source posters are category jokes, not stories. A normal advice,
  ranking, comparison, sign, or routine title contains answers that are rude,
  literal, impossible, or oddly specific while remaining valid members of the
  title's category.
- Do not connect list rows into setup, escalation, consequence, climax, and
  payoff. That structure produced explainable mini-stories instead of the
  source format.
- One phrase per row carries a saturated accent color.
- Specific logistics beat random nouns: named documents, brokers, times, ports,
  invoices, relatives, permits, and commodities.
- Bureaucratic and corporate language is not a default joke engine. Managers,
  permits, committees, inspections, fees, policy, and briefings belong only in
  a premise whose ordinary setting already calls for them.
- A headline must be immediately understandable as a sentence. Reject invented
  concepts that need interpretation before they can be funny.
- The final row is often the shortest and most confidently wrong answer.
- Rotate composition, portrait, frame, and motif independently; do not repeat
  any of them in adjacent posts.

The generator does not reproduce captions from the references. It uses their
visual and comedic grammar to produce original posters. Avoid protected-class
slurs, sexual material, private information, and claims about real people.

## Bilingual anti-logic list

The supplied Steve Jobs reference adds one distinct format: a giant count word
with a deadpan parenthetical translation, followed by five numbered commands.
The parenthetical is only a surface gag. Every command must still be a warped
response to the exact situation in the title: a nap list concerns sleep, an
elevator list concerns the stopped lift, and a fire-drill list concerns the
drill. Use at most one parenthetical translation, make every line a visual
action, and reject any row that could move under an unrelated title unchanged.
Do not reuse the reference's rare-fish, evaporation, uncle, sand, or legal-name
lines. This grammar belongs mainly to `daily_list` / `right_cutout` and should
not leak into every other poster family.

## Portrait selection

The Discord thread contains 34 unique images. Nine are useful portrait
sources. The importer uses `friend-*` for supplied personal photos and
`thread-*` for reframed meme references. It does not guess names.

Ready without reframing:

- `friend-studio.jpg` is a clean studio half-body portrait.
- `friend-jacket.jpg` is a clean seated half-body portrait.
- `friend-closeup.jpg` is a clean face crop. Use it only in layouts that can
  tolerate a large head with little shoulder area.
- `thread-suit.png`, `thread-garage.png`, and `thread-formal.png` are reframed
  reference portraits. Their slugs describe the image, not the person.

Reframed during import:

- `david-car.png` removes the screenshot's black bars.
- `david-event.jpg` keeps David and removes the other event attendees.
- `friend-city.jpg` removes the person behind the main subject.
- `steve-jobs.jpg` is supplied reference art. Keep it on the private persistent
  asset volume; `prepare_assets.py` extracts the person and discards baked-in
  text instead of committing the source image to public GitOps.

The remaining thread files stay reference-only. They contain baked-in text,
multiple focal subjects, screenshots, composites, poor crops, or low-resolution
meme art. The twelve files in `~/Downloads/mmemes` are also reference-only.
They teach layout and joke rhythm, but their portraits and captions must not be
reused as source assets.

Before enabling a portrait, verify that it opens, has nonzero dimensions, and
produces a nonempty transparent cutout. Do not use a group photo unless an
explicit crop removes every other person first.

## Placement roster

These pairings passed a visual render at 1080 by 1350:

- `friend-city` with `left_editorial` gives the best tall, nearly full-body
  composition in the set.
- `friend-studio`, `david-event`, `friend-jacket`, `arnold-schwarzenegger`, and
  `jeff-bezos` all work with `left_editorial`.
- `barack-obama`, `cristiano-ronaldo`, `david-car`, and `friend-closeup` work
  with `cinematic_rows`.
- `donald-trump`, `elon-musk`, `mark-zuckerberg`, `nicusor-dan`, and
  `warren-buffett` work with `protocol_card`.
- `thread-suit` should enter the `left_editorial` pool after its cutout passes.
- `thread-garage` should enter `left_editorial` and other tall side-column
  layouts after its cutout passes.
- `thread-formal` should enter `closeup_ranked` and `protocol_card` after its
  cutout passes.

Do not treat every portrait as valid for every layout:

- `bill-gates` contains two people. Remove it from all automatic rotation.
- `friend-room` retained a large wall panel after background removal. Remove
  both its source and cutout from rotation.
- `friend-city` becomes a tiny figure in `cinematic_rows` and `protocol_card`.
  Keep it in tall side-column layouts.
- `friend-closeup` has no useful torso. Prefer `cinematic_rows`,
  `closeup_ranked`, and `quote_wall`.
- `david-event` loses too much face contrast in `protocol_card`. Prefer
  `left_editorial` or a larger side cutout.
- `friend-jacket` and `friend-studio` read too small in `cinematic_rows`.
  Prefer `left_editorial`, `right_cutout`, or `circle_manifesto`.
- `david-car` keeps a seat belt and a small green edge. It works in grayscale
  or faded layouts, but not as a clean color cutout over a flat background.
