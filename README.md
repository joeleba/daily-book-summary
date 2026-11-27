# Daily Book Ideas

One distilled book idea every morning at **06:30 Munich time (Europe/Berlin)**, with toggleable **Economist** and **FT** editorial themes, published automatically to GitHub Pages and emailed to subscribers.

## How It Works
- **Antigravity Automation (Daily at 06:30 Europe/Berlin)** — Reads [`prompts/daily-digest.md`](prompts/daily-digest.md), picks the next book from `queue` (or an FT Business Book of the Year winner/shortlist), drafts and fact-checks the entry, updates `posts.json`, rebuilds `docs/`, and pushes to `main`.
- **`posts.json`** — Source of truth for all published digests (`posts`) and upcoming reader requests (`queue`).
- **`scripts/build_site.py`** — Deterministically builds the static site (`docs/index.html` and `docs/entries/<id>.html`) from `posts.json`, including SVG `hbar` and `line` charts and Economist / FT + Dark Mode toggles.
- **`scripts/send_email.py`** — Renders a post as an editorial HTML + plain-text email and delivers it via Gmail SMTP.
- **`.github/workflows/daily-digest.yml`** — Triggers automatically on `push` to `posts.json` on `main`, ensures `docs/` is up to date for GitHub Pages, and emails any newly added post(s) to `DIGEST_RECIPIENTS`.
- **`.github/workflows/send-test-email.yml`** — Manual `workflow_dispatch` job to send a test email for an existing post.

## Setup Checklist
1. **Enable GitHub Pages:** Go to **Settings → Pages**, set **Source** to `Deploy from a branch`, select **`main`** and folder **`/docs`**, and click **Save**.
2. **Add email secrets:** Go to **Settings → Secrets and variables → Actions**, and add `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, and `DIGEST_RECIPIENTS`.
3. **Configure Antigravity Automation:** Create a daily Automation at `06:30 Europe/Berlin` attached to this repository.

## Queueing Books
Add entries to the `"queue"` array in `posts.json` (editing `queue` alone updates the site without triggering an email):
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
