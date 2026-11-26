# Daily Book Ideas

One distilled, fact-checked book idea every weekday morning at **06:30 Munich time (Europe/Berlin)**, with toggleable **Economist** and **FT** editorial themes, published automatically to GitHub Pages.

## How It Works
- **`posts.json`** — Source of truth for all published digests (`posts`) and upcoming reader requests (`queue`).
- **`prompts/daily-digest.md`** — The daily prompt executed by Antigravity CLI (`agy`) in headless mode, including subagent fact-checking.
- **`scripts/build_site.py`** — Deterministically builds the static site (`docs/index.html` and `docs/entries/<id>.html`) from `posts.json`, including SVG `hbar` and `line` charts and Economist / FT + Dark Mode toggles.
- **`.github/workflows/daily-digest.yml`** — Runs Monday–Friday at 06:30 Europe/Berlin (handling CET/CEST daylight saving automatically), updates `posts.json`, rebuilds `docs/`, and commits & pushes to `main`.

## Setup Checklist
1. **Add API key secret:** Go to **Settings → Secrets and variables → Actions → New repository secret**, and add `GEMINI_API_KEY`.
2. **Enable GitHub Pages:** Go to **Settings → Pages**, set **Source** to `Deploy from a branch`, select **`main`** and folder **`/docs`**, and click **Save**.
3. **Test it:** Go to **Actions → Daily Book Ideas → Run workflow**.

## Queueing Books
Add entries to the `"queue"` array in `posts.json` (or ask Antigravity to add them for you), for example:
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
