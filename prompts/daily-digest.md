Prepare today's weekday morning book-idea digest (< 1,000 words) and save it to `posts.json`.

1. **Book & Topic Selection**
   - Read `posts.json` first. If `queue` has an entry matching today (or an undated next request), prioritize that book/topic and remove the fulfilled item from `queue` when saving.
   - Never repeat an idea already in `posts`, and track progress through multi-idea books.
   - Otherwise, pick from **Financial Times Business Book of the Year** winners and shortlists, favoring topics pertinent to smart peer discussions: tech leadership, corporate strategy, leadership & org design, negotiation, capital allocation/finance, macroeconomics, global geopolitics, and behavioral economics, decision science, & cognitive/social psychology (research-backed frameworks on human judgment and behavior, not prescriptive self-help).

2. **Drafting the Summary (500–800 words; hard cap 1,000 words)**
   - Pick 1 compelling unseen idea for today.
   - Write with a **"cocktail-party / dinner-table" bar** in mind: give the reader enough focused, memorable, well-structured material to hold the floor for 60–90 seconds with smart peers — leading with a sharp hook/framing, anchoring it in ONE vivid, retellable concrete example (specific names, places, and 1–2 sticky numbers rather than dense data dumps), anticipating the obvious pushback so they sound nuanced rather than one-sided, and closing with a punchy line worth saying aloud.
   - Structure it into:
     - **Core idea**: sharp framing/hook + plain-English thesis someone can explain in 2–3 sentences.
     - **Concrete example**: ONE vivid, retellable example from the book that substantiates the idea.
     - **Argument for**: the strongest supporting case.
     - **Argument against**: the sharpest counterargument/limit to show nuance.
     - **Takeaway quote**: ONE verbatim quote from the book that is BOTH directly tied to the core idea AND genuinely quotable—punchy and memorable enough to say aloud to an audience.

3. **Optional Chart (Less Is More)**
   - Only include a chart when verified quantitative data from the book clearly strengthens the point; NEVER flowcharts.
   - Include a `"chart"` object using `"type": "hbar"` (`title`, `subtitle`, `unit`, `max`, `ticks`, `bars: [{label, value, benchmark?}]`, `source`) or `"type": "line"` (`title`, `subtitle`, `unit`, `y_min`, `y_max`, `y_ticks`, `x_labels`, `series: [{label?, values: [...]}]`, `source`). Always calibrate axes honestly (e.g., 0–100% for shares).

4. **Independent Fact-Check**
   - Spin up a subagent to critically fact-check every factual claim, date, figure (including chart numbers/sources), book attribution, and exact quote wording via web search. Fix any inaccuracies before saving.

5. **Save**
   - Update `posts.json`: set `updated_at` to today (`YYYY-MM-DD`), remove any fulfilled item from `queue`, and append the new post (`id`: `YYYY-MM-DD-<short-slug>`, `date`, `title`, `book`, `author`, `award` — FT award if applicable or `"Reader Pick · <Year>"` for queued non-FT books, `tags` as `#lowercase-slug`, `core_idea`, optional `chart`, `example`, `argument_for`, `argument_against`, `quote`, `quote_source`, `fact_checked: true`).
