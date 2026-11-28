# Daily Book Ideas

One distilled, fact-checked book idea every morning at **06:30 Europe/Berlin**, with toggleable **Economist** and **FT** editorial themes, published to GitHub Pages and emailed to subscribers.

## How It Works
- **External Scheduled Runner (Daily at 06:30 Europe/Berlin)** — Managed outside GitHub Actions. Each run pulls `main`, invokes Antigravity CLI (`agy`) in headless mode with [`prompts/daily-digest.md`](prompts/daily-digest.md) to draft and fact-check a new entry, validates `posts.json`, rebuilds `docs/` via `scripts/build_site.py`, commits and pushes to `main`, and sends the digest via `scripts/send_email.py`.
- **`posts.json`** — Source of truth for all published digests (`posts`) and upcoming book requests (`queue`).
- **`prompts/daily-digest.md`** — Prompt and editorial/fact-checking instructions used to generate each entry.
- **`scripts/build_site.py`** — Deterministically builds the static site (`docs/index.html` and `docs/entries/<id>.html`) from `posts.json`, including SVG `hbar` and `line` charts and Economist / FT + Dark Mode toggles.
- **`scripts/send_email.py`** — Renders a post (latest by default, or selected via `--post-id` / `--date`) as an editorial HTML + plain-text email and delivers it via SMTP using environment variables (`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `DIGEST_RECIPIENTS`).
- **GitHub Pages** — Automatically deploys static files from `main` (`/docs`) on every push. Daily publishing does not use GitHub Actions; [`.github/workflows/send-test-email.yml`](.github/workflows/send-test-email.yml) is retained only for manual test emails (`workflow_dispatch`).

## Maintenance Notes
- Whenever `posts.json` is edited (including queue updates or post fixes), validate it and rebuild the static site before committing:
  ```bash
  python3 -m json.tool posts.json > /dev/null
  python3 scripts/build_site.py
  ```
- GitHub Pages serves directly from `main` → `/docs`.

## Queueing Books
Add entries to the `"queue"` array in `posts.json`:
```json
{
  "updated_at": "2026-11-26",
  "queue": [
    "Good Strategy Bad Strategy by Richard Rumelt",
    { "date": "2026-12-01", "book": "The Outsiders", "topic": "Capital allocation" }
  ],
  "posts": []
}
```
