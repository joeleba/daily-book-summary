#!/usr/bin/env python3
"""Send a Daily Book Ideas digest entry via Gmail SMTP.

Reads posts.json from the repository root, renders the selected (or latest)
post as an editorial HTML + plain-text email, and sends it using Gmail SMTP
with an App Password.

Environment variables:
  GMAIL_ADDRESS       Sender Gmail address (required unless --dry-run)
  GMAIL_APP_PASSWORD  16-character Google App Password (required unless --dry-run)
  DIGEST_RECIPIENTS   Comma- or newline-separated recipient emails
                      (optional; falls back to GMAIL_ADDRESS)
  SITE_BASE_URL       Public site base URL for "Read on web" links
                      (default: https://joeleba.github.io/daily-book-summary)
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
POSTS_JSON = ROOT / "posts.json"
DEFAULT_SITE_URL = "https://joeleba.github.io/daily-book-summary"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def split_paragraphs(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", (text or "").strip()) if b.strip()]


def strip_inline_markdown(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")


def render_inline_html(text: str) -> str:
    escaped = esc(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def count_words(post: dict[str, Any]) -> int:
    fields = [
        post.get("core_idea", ""),
        post.get("example", ""),
        post.get("argument_for", ""),
        post.get("argument_against", ""),
        post.get("quote", ""),
    ]
    cleaned = re.sub(r"(?m)^\s*[-*•]\s+", "", "\n".join(fields))
    cleaned = strip_inline_markdown(cleaned)
    return len(cleaned.split())


def format_num(value: float | int, unit: str = "") -> str:
    if isinstance(value, float) and value.is_integer():
        num_str = str(int(value))
    elif isinstance(value, float):
        num_str = f"{value:g}"
    else:
        num_str = str(value)
    if not unit:
        return num_str
    if unit in ("%", "x", "×", "bn", "m", "k", "B", "M", "K"):
        return f"{num_str}{unit}"
    if unit in ("$", "€", "£"):
        return f"{unit}{num_str}"
    return f"{num_str} {unit}"


def build_kicker(post: dict[str, Any]) -> str:
    tags = [str(t).strip().lower() for t in (post.get("tags") or []) if str(t).strip()]
    parts: list[str] = []
    if tags:
        parts.append(tags[0].lstrip("#").replace("-", " ").upper())
    award = str(post.get("award") or "").strip()
    if award:
        parts.append(award.upper())
    return " · ".join(parts) if parts else "READING BRIEF"


def select_post(
    posts: list[dict[str, Any]],
    post_id: str | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    if not posts:
        raise ValueError("posts.json contains no posts.")
    if post_id:
        for p in posts:
            if str(p.get("id") or "") == post_id:
                return p
        raise ValueError(f"Post id not found in posts.json: {post_id}")
    if date:
        matching = [p for p in posts if str(p.get("date") or "") == date]
        if matching:
            return matching[-1]
    # Default: newest by (date, index)
    indexed = list(enumerate(posts))
    indexed.sort(key=lambda item: (str(item[1].get("date") or ""), item[0]), reverse=True)
    return indexed[0][1]


def render_email_chart_html(chart: dict[str, Any] | None, entry_url: str) -> str:
    """Render an email-safe HTML summary for hbar/line charts (Gmail strips SVG)."""
    if not chart or not isinstance(chart, dict):
        return ""
    chart_type = str(chart.get("type") or "").lower()
    title = esc(chart.get("title", ""))
    subtitle = esc(chart.get("subtitle", ""))
    source = esc(chart.get("source", ""))
    unit = str(chart.get("unit") or "")

    rows_html = ""
    if chart_type == "hbar":
        bars = chart.get("bars") or []
        max_val = float(
            chart.get("max") or max((float(b.get("value", 0)) for b in bars), default=100)
        )
        if max_val <= 0:
            max_val = 100.0
        for b in bars:
            val = float(b.get("value", 0))
            pct = max(2, min(100, int(round((val / max_val) * 100)))) if val > 0 else 0
            bar_color = "#8a949e" if b.get("benchmark") else "#990f3d"
            label = esc(b.get("label", ""))
            val_txt = esc(format_num(b.get("value", 0), unit))
            rows_html += f"""
              <tr>
                <td style="padding:5px 0 2px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:12.5px;color:#1a1816;">
                  {label}
                </td>
                <td align="right" style="padding:5px 0 2px 10px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:12.5px;font-weight:700;color:#1a1816;white-space:nowrap;">
                  {val_txt}
                </td>
              </tr>
              <tr>
                <td colspan="2" style="padding:0 0 6px 0;">
                  <div style="background-color:#ead9c9;height:8px;width:100%;border-radius:1px;">
                    <div style="background-color:{bar_color};height:8px;width:{pct}%;border-radius:1px;"></div>
                  </div>
                </td>
              </tr>"""
    elif chart_type == "line":
        x_labels = chart.get("x_labels") or []
        series = chart.get("series") or []
        if x_labels and series:
            first_lbl = esc(x_labels[0])
            last_lbl = esc(x_labels[-1])
            for s in series:
                vals = [v for v in (s.get("values") or []) if v is not None]
                if not vals:
                    continue
                s_lbl = esc(s.get("label") or "Series")
                rows_html += f"""
                  <tr>
                    <td style="padding:4px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:12.5px;color:#1a1816;">{s_lbl}</td>
                    <td align="right" style="padding:4px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:12.5px;font-weight:700;color:#1a1816;">
                      {first_lbl}: {esc(format_num(vals[0], unit))} → {last_lbl}: {esc(format_num(vals[-1], unit))}
                    </td>
                  </tr>"""

    if not rows_html:
        return ""

    subtitle_html = (
        f'<div style="font-size:12px;color:#66605c;margin-top:2px;margin-bottom:10px;">{subtitle}</div>'
        if subtitle
        else ""
    )
    source_html = (
        f'<div style="font-size:11px;color:#66605c;margin-top:8px;">Source: {source} · '
        f'<a href="{esc(entry_url)}" style="color:#0d7680;text-decoration:none;">View full chart ↗</a></div>'
        if source
        else ""
    )

    return f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px 0;background-color:#fceee1;border:1px solid #e6d0bd;border-top:2px solid #1a1816;">
        <tr>
          <td style="padding:14px 16px;">
            <div style="width:28px;height:4px;background-color:#990f3d;margin-bottom:8px;"></div>
            <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:14px;font-weight:700;color:#1a1816;line-height:1.3;">{title}</div>
            {subtitle_html}
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              {rows_html}
            </table>
            {source_html}
          </td>
        </tr>
      </table>"""


def render_paragraphs_html(text: str) -> str:
    blocks = split_paragraphs(text)
    if not blocks:
        return ""
    out: list[str] = []
    elem_idx = 0
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        buf_p: list[str] = []
        buf_li: list[str] = []

        def flush_p() -> None:
            nonlocal elem_idx
            if not buf_p:
                return
            margin_top = "10px" if elem_idx > 0 else "0"
            out.append(
                f'<p style="margin:{margin_top} 0 0 0;font-family:Georgia,\'Times New Roman\',serif;'
                f'font-size:15.5px;line-height:1.65;color:#1a1816;">{render_inline_html(" ".join(buf_p))}</p>'
            )
            buf_p.clear()
            elem_idx += 1

        def flush_li() -> None:
            nonlocal elem_idx
            if not buf_li:
                return
            margin_top = "10px" if elem_idx > 0 else "0"
            items_html = []
            for li_idx, item in enumerate(buf_li):
                li_mt = "6px" if li_idx > 0 else "0"
                items_html.append(
                    f'<li style="margin:{li_mt} 0 0 0;font-family:Georgia,\'Times New Roman\',serif;'
                    f'font-size:15.5px;line-height:1.65;color:#1a1816;">{render_inline_html(item)}</li>'
                )
            out.append(
                f'<ul style="margin:{margin_top} 0 0 0;padding-left:20px;color:#990f3d;">'
                + "".join(items_html)
                + "</ul>"
            )
            buf_li.clear()
            elem_idx += 1

        for ln in lines:
            m = re.match(r"^[-*•]\s+(.*)$", ln)
            if m:
                flush_p()
                buf_li.append(m.group(1).strip())
            else:
                flush_li()
                buf_p.append(ln)
        flush_p()
        flush_li()
    return "\n".join(out)


def render_email_html(post: dict[str, Any], site_base_url: str) -> str:
    post_id = str(post.get("id") or "")
    safe_id = re.sub(r"[^a-zA-Z0-9._-]", "-", post_id)
    base = site_base_url.rstrip("/")
    entry_url = f"{base}/entries/{safe_id}.html"
    kicker = build_kicker(post)
    title = str(post.get("title") or "")
    book = str(post.get("book") or "")
    author = str(post.get("author") or "")
    date = str(post.get("date") or "")
    words = count_words(post)
    tags = [str(t).strip().lower() for t in (post.get("tags") or []) if str(t).strip()]
    preheader = strip_inline_markdown(" ".join(split_paragraphs(str(post.get("core_idea") or ""))))[:160]

    chart_html = render_email_chart_html(post.get("chart"), entry_url)

    quote = str(post.get("quote") or "").strip()
    quote_source = str(post.get("quote_source") or "").strip()
    quote_html = ""
    if quote:
        footer_html = (
            f'<div style="margin-top:8px;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;'
            f'font-size:12px;font-style:normal;font-weight:600;color:#66605c;">— {esc(quote_source)}</div>'
            if quote_source
            else ""
        )
        quote_html = f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px 0;background-color:#fceee1;border-left:3px solid #990f3d;">
        <tr>
          <td style="padding:14px 16px;font-family:Georgia,'Times New Roman',serif;font-size:15.5px;line-height:1.55;font-style:italic;color:#1a1816;">
            “{esc(quote)}”
            {footer_html}
          </td>
        </tr>
      </table>"""

    tags_html = " ".join(
        f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 7px;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;'
        f'font-size:11px;font-weight:600;color:#66605c;background-color:#f2dfce;border:1px solid #e6d0bd;border-radius:2px;">{esc(t)}</span>'
        for t in tags
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} — Daily Book Ideas</title>
</head>
<body style="margin:0;padding:0;background-color:#fff1e5;color:#1a1816;-webkit-font-smoothing:antialiased;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{esc(preheader)}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#fff1e5;border-top:4px solid #990f3d;">
    <tr>
      <td align="center" style="padding:20px 12px 36px 12px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;">
          <!-- Masthead -->
          <tr>
            <td style="padding-bottom:12px;border-bottom:2px solid #1a1816;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="display:inline-block;background-color:#990f3d;color:#ffffff;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:11px;letter-spacing:0.05em;text-transform:uppercase;padding:3px 8px;border-radius:2px;">Reading Brief</span>
                    <div style="font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:700;color:#1a1816;margin-top:6px;letter-spacing:-0.015em;">Daily Book Ideas</div>
                  </td>
                  <td align="right" valign="bottom" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:12px;color:#66605c;white-space:nowrap;">
                    <div>{esc(date)}</div>
                    <div style="margin-top:3px;"><a href="{esc(entry_url)}" style="color:#0d7680;font-weight:600;text-decoration:none;">Read on web ↗</a></div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Card -->
          <tr>
            <td style="padding-top:16px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#fff7f0;border:1px solid #e6d0bd;border-top:2px solid #1a1816;border-radius:2px;">
                <tr>
                  <td style="padding:20px 20px 16px 20px;">
                    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#990f3d;margin-bottom:6px;">
                      {esc(kicker)}
                    </div>
                    <h1 style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:700;line-height:1.25;color:#1a1816;letter-spacing:-0.01em;">
                      {esc(title)}
                    </h1>
                    <div style="margin-top:6px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:13.5px;color:#66605c;line-height:1.45;">
                      <strong style="color:#1a1816;">{esc(book)}</strong> · {esc(author)}
                    </div>
                    <div style="margin-top:10px;">
                      {tags_html}
                    </div>

                    <hr style="border:0;border-top:1px solid #e6d0bd;margin:16px 0;">

                    <!-- Core Idea -->
                    <div style="margin-bottom:18px;">
                      <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#990f3d;margin-bottom:6px;">Core Idea</div>
                      {render_paragraphs_html(str(post.get("core_idea") or ""))}
                    </div>

                    {chart_html}

                    <!-- Example -->
                    <div style="margin-bottom:18px;">
                      <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#990f3d;margin-bottom:6px;">Example from the Book</div>
                      {render_paragraphs_html(str(post.get("example") or ""))}
                    </div>

                    <!-- Argue For -->
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px 0;background-color:#fceee1;border:1px solid #e6d0bd;border-top:2.5px solid #0d7680;">
                      <tr>
                        <td style="padding:14px 16px;">
                          <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#0d7680;margin-bottom:6px;">Argue For</div>
                          {render_paragraphs_html(str(post.get("argument_for") or ""))}
                        </td>
                      </tr>
                    </table>

                    <!-- Argue Against -->
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px 0;background-color:#fceee1;border:1px solid #e6d0bd;border-top:2.5px solid #990f3d;">
                      <tr>
                        <td style="padding:14px 16px;">
                          <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#990f3d;margin-bottom:6px;">Argue Against</div>
                          {render_paragraphs_html(str(post.get("argument_against") or ""))}
                        </td>
                      </tr>
                    </table>

                    {quote_html}

                    <!-- Footer Row -->
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding-top:4px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:12px;color:#66605c;">
                      <tr>
                        <td><span>{words} words</span></td>
                        <td align="right"><a href="{esc(base)}/" style="color:#0d7680;text-decoration:none;font-weight:600;">Browse full archive →</a></td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def render_email_text(post: dict[str, Any], site_base_url: str) -> str:
    post_id = str(post.get("id") or "")
    safe_id = re.sub(r"[^a-zA-Z0-9._-]", "-", post_id)
    base = site_base_url.rstrip("/")
    entry_url = f"{base}/entries/{safe_id}.html"
    lines = [
        f"{build_kicker(post)} ({post.get('date', '')})",
        f"{post.get('title', '')}",
        f"{post.get('book', '')} — {post.get('author', '')}",
        "",
        "CORE IDEA",
        strip_inline_markdown(str(post.get("core_idea") or "").strip()),
        "",
        "EXAMPLE FROM THE BOOK",
        strip_inline_markdown(str(post.get("example") or "").strip()),
        "",
        "ARGUE FOR",
        strip_inline_markdown(str(post.get("argument_for") or "").strip()),
        "",
        "ARGUE AGAINST",
        strip_inline_markdown(str(post.get("argument_against") or "").strip()),
    ]
    quote = str(post.get("quote") or "").strip()
    if quote:
        quote_source = str(post.get("quote_source") or "").strip()
        lines.extend(["", f'"{quote}"', f"— {quote_source}" if quote_source else ""])
    lines.extend(["", f"Read on web: {entry_url}", f"Archive: {base}/"])
    return "\n".join(lines).strip() + "\n"


def parse_recipients(raw: str) -> list[str]:
    parts = re.split(r"[,;\n]+", raw or "")
    return [p.strip() for p in parts if p.strip() and "@" in p]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a Daily Book Ideas email via Gmail SMTP.")
    parser.add_argument("--post-id", help="Specific post id from posts.json (defaults to latest).")
    parser.add_argument("--date", help="Prefer a post matching YYYY-MM-DD (falls back to latest).")
    parser.add_argument("--to", help="Override recipient email(s), comma-separated.")
    parser.add_argument("--subject-prefix", default="", help="Optional prefix for the email subject.")
    parser.add_argument("--dry-run", action="store_true", help="Render email and print summary without sending.")
    parser.add_argument("--out-html", help="Optional path to write rendered HTML when testing.")
    args = parser.parse_args()

    if not POSTS_JSON.exists():
        print(f"Error: {POSTS_JSON} not found.", file=sys.stderr)
        return 1

    data = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
    post = select_post(data.get("posts") or [], post_id=args.post_id, date=args.date)
    site_url = os.environ.get("SITE_BASE_URL", DEFAULT_SITE_URL).strip() or DEFAULT_SITE_URL

    book_short = str(post.get("book") or "").split(":")[0].strip()
    subject = f"{args.subject_prefix}Daily Book Idea: {post.get('title', '')}"
    if book_short:
        subject += f" ({book_short})"

    html_body = render_email_html(post, site_url)
    text_body = render_email_text(post, site_url)

    if args.out_html:
        Path(args.out_html).write_text(html_body, encoding="utf-8")

    if args.dry_run:
        print(f"[dry-run] Selected post: {post.get('id')}")
        print(f"[dry-run] Subject: {subject}")
        print(f"[dry-run] HTML bytes: {len(html_body)}, text bytes: {len(text_body)}")
        return 0

    gmail_user = os.environ.get("GMAIL_ADDRESS", "").strip()
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not gmail_user or not gmail_pass:
        print("GMAIL_ADDRESS or GMAIL_APP_PASSWORD is not set; skipping email send.")
        return 0

    raw_recipients = args.to or os.environ.get("DIGEST_RECIPIENTS", "").strip() or gmail_user
    recipients = parse_recipients(raw_recipients)
    if not recipients:
        print("No valid recipient email addresses found; skipping email send.")
        return 0

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Daily Book Ideas <{gmail_user}>"
    if len(recipients) == 1:
        msg["To"] = recipients[0]
    else:
        msg["To"] = gmail_user
        msg["Bcc"] = ", ".join(recipients)

    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
        server.login(gmail_user, gmail_pass)
        server.send_message(msg)

    print(f"Sent '{post.get('id')}' to {len(recipients)} recipient(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
