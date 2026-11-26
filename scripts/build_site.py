#!/usr/bin/env python3
"""Static site generator for Daily Book Ideas (The Economist style).

Reads posts.json from the repository root and generates:
  - docs/index.html            (full reading log with search, tag filters, dark mode)
  - docs/entries/<id>.html     (standalone permalink page for each post)
  - docs/.nojekyll             (disable Jekyll on GitHub Pages)
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
POSTS_JSON = ROOT / "posts.json"
DOCS_DIR = ROOT / "docs"
ENTRIES_DIR = DOCS_DIR / "entries"

FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 100 100%27%3E"
    "%3Ctext y=%27.9em%27 font-size=%2790%27%3E%F0%9F%93%9A%3C/text%3E%3C/svg%3E"
)

CSS = """\
    .container { max-width: 960px; margin: 0 auto; }

    :root {
      color-scheme: light;
      --econ-red: #e3120b;
      --econ-red-soft: rgba(227, 18, 11, 0.08);
      --econ-blue: #1d4f73;
      --bg-color: #f8f6f1;
      --text-color: #141414;
      --muted-color: #5c5852;
      --card-bg: #ffffff;
      --border-color: #ddd8ce;
      --header-bg: #f1ede4;
      --details-bg: #faf8f4;
      --input-bg: #ffffff;
      --input-border: #c9c3b8;
      --link-color: #1d4f73;
      --code-bg: #efeae0;
      --highlight-ring: #e3120b;
      --highlight-bg: #fffaf9;
      --verified-bg: #ebf5ee;
      --verified-fg: #1b5e34;
      --chart-grid: #e3ded4;
      --chart-bench: #8a949e;
      --serif-font: Georgia, "Iowan Old Style", "Palatino Linotype", "Times New Roman", serif;
      --sans-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    html[data-theme="dark"] {
      color-scheme: dark;
      --econ-red: #f03a33;
      --econ-red-soft: rgba(240, 58, 51, 0.14);
      --econ-blue: #6aa7cf;
      --bg-color: #121316;
      --text-color: #ece9e2;
      --muted-color: #a39f97;
      --card-bg: #191b1f;
      --border-color: #2b2e35;
      --header-bg: #21242b;
      --details-bg: #16181c;
      --input-bg: #15171b;
      --input-border: #3a3e48;
      --link-color: #6aa7cf;
      --code-bg: #23262e;
      --highlight-ring: #f03a33;
      --highlight-bg: rgba(240, 58, 51, 0.07);
      --verified-bg: rgba(46, 160, 67, 0.18);
      --verified-fg: #85e0a3;
      --chart-grid: #2c3038;
      --chart-bench: #6e7781;
    }

    /* Financial Times (FT) Editorial Theme — Light (Iconic Salmon Paper & Claret) */
    html[data-style="ft"] {
      --econ-red: #990f3d;
      --econ-red-soft: rgba(153, 15, 61, 0.10);
      --econ-blue: #0d7680;
      --bg-color: #fff1e5;
      --text-color: #1a1816;
      --muted-color: #66605c;
      --card-bg: #fff7f0;
      --border-color: #e6d0bd;
      --header-bg: #f2dfce;
      --details-bg: #fceee1;
      --input-bg: #fffaf5;
      --input-border: #d9bfa9;
      --link-color: #0d7680;
      --code-bg: #f2dfce;
      --highlight-ring: #990f3d;
      --highlight-bg: #ffece0;
      --verified-bg: #e3f0ea;
      --verified-fg: #0b5d4b;
      --chart-grid: #e3ccb8;
      --chart-bench: #9e8f84;
      --serif-font: "Playfair Display", Georgia, "Times New Roman", serif;
      --sans-font: "DM Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --body-serif-font: "Source Serif 4", Georgia, "Times New Roman", serif;
    }

    html[data-style="ft"] .masthead-title {
      font-weight: 800;
      letter-spacing: -0.015em;
    }
    html[data-style="ft"] .post-title {
      font-weight: 700;
      font-size: 19px;
      letter-spacing: -0.01em;
    }
    html[data-style="ft"] .markdown-body .md-p {
      font-family: var(--body-serif-font);
      font-size: 15px;
      line-height: 1.68;
    }
    html[data-style="ft"] .quote-block {
      font-family: var(--serif-font);
      font-size: 15.5px;
    }

    /* Financial Times (FT) Editorial Theme — Dark (Deep Espresso & Claret) */
    html[data-style="ft"][data-theme="dark"] {
      --econ-red: #e05a84;
      --econ-red-soft: rgba(224, 90, 132, 0.16);
      --econ-blue: #4db6c0;
      --bg-color: #181311;
      --text-color: #f3e8df;
      --muted-color: #b5a497;
      --card-bg: #221b18;
      --border-color: #3a2f2a;
      --header-bg: #2c231f;
      --details-bg: #1d1714;
      --input-bg: #1b1513;
      --input-border: #4a3c36;
      --link-color: #4db6c0;
      --code-bg: #2e2420;
      --highlight-ring: #e05a84;
      --highlight-bg: rgba(224, 90, 132, 0.08);
      --verified-bg: rgba(77, 182, 192, 0.18);
      --verified-fg: #8ce0e8;
      --chart-grid: #3b302b;
      --chart-bench: #8a7b72;
    }

    .style-switch {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--border-color);
      border-radius: 2px;
      overflow: hidden;
      background-color: var(--header-bg);
    }
    .style-switch-btn {
      padding: 5px 9px;
      border: 0;
      background: transparent;
      color: var(--muted-color);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
    .style-switch-btn:hover {
      color: var(--text-color);
    }
    .style-switch-btn.active {
      background-color: var(--econ-red);
      color: #ffffff;
    }

    *, *::before, *::after { box-sizing: border-box; }

    html, body {
      font-family: var(--sans-font);
      background-color: var(--bg-color);
      color: var(--text-color);
      margin: 0;
      padding: 0;
      font-size: 14px;
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }

    body {
      border-top: 4px solid var(--econ-red);
      padding: 20px 22px 48px;
      min-height: 100vh;
    }

    h1, h2, h3, h4, h5, p { margin: 0; }
    .hidden { display: none !important; }
    .flex { display: flex; }
    .flex-wrap { flex-wrap: wrap; }
    .flex-1 { flex: 1 1 0%; }
    .items-center { align-items: center; }
    .items-start { align-items: flex-start; }
    .justify-between { justify-content: space-between; }
    .justify-end { justify-content: flex-end; }
    .gap-1 { gap: 0.25rem; }
    .gap-1-5 { gap: 0.375rem; }
    .gap-2 { gap: 0.5rem; }
    .gap-3 { gap: 0.75rem; }
    .min-w-0 { min-width: 0; }
    .shrink-0 { flex-shrink: 0; }
    .font-mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    .muted-text { color: var(--muted-color); }
    .grid-1 { display: grid; grid-template-columns: 1fr; gap: 0.85rem; }

    a { color: var(--link-color); text-decoration: none; }
    a:hover { text-decoration: underline; }

    :focus-visible {
      outline: 2px solid var(--econ-red);
      outline-offset: 2px;
    }

    code {
      background-color: var(--code-bg);
      color: var(--text-color);
      padding: 1px 5px;
      border-radius: 2px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.86em;
    }

    .masthead {
      padding-bottom: 12px;
      border-bottom: 2px solid var(--text-color);
      margin-bottom: 14px;
    }
    .econ-brand-pill {
      display: inline-block;
      background-color: var(--econ-red);
      color: #ffffff;
      font-family: var(--serif-font);
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      padding: 3px 8px;
      border-radius: 2px;
    }
    .masthead-title {
      font-family: var(--serif-font);
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
      line-height: 1.15;
    }

    .stat-strip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 3px 9px;
      border-radius: 2px;
      background-color: var(--card-bg);
      border: 1px solid var(--border-color);
      font-size: 12px;
    }
    .stat-item strong { font-weight: 700; }

    .toolbar {
      background-color: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 2px;
      padding: 9px 12px;
      margin-bottom: 10px;
    }

    input[type="text"] {
      padding: 6px 10px;
      border: 1px solid var(--input-border);
      border-radius: 2px;
      font-size: 13px;
      background-color: var(--input-bg);
      color: var(--text-color);
    }
    input[type="text"]:focus {
      border-color: var(--econ-red);
      outline: none;
    }

    .action-btn {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 5px 10px;
      border-radius: 2px;
      font-size: 12px;
      font-weight: 600;
      background-color: var(--header-bg);
      border: 1px solid var(--border-color);
      color: var(--text-color);
      cursor: pointer;
    }
    .action-btn:hover {
      border-color: var(--econ-red);
      color: var(--econ-red);
      text-decoration: none;
    }

    .hash-badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 2px;
      font-size: 11.5px;
      font-weight: 600;
      background-color: var(--header-bg);
      border: 1px solid var(--border-color);
      color: var(--econ-red);
    }

    .toast-pill {
      padding: 3px 8px;
      border-radius: 2px;
      font-size: 11.5px;
      font-weight: 600;
      background-color: var(--verified-bg);
      color: var(--verified-fg);
    }

    .tag-filter-section {
      margin-bottom: 14px;
    }

    .tag-toggle-btn {
      display: none;
      width: 100%;
      align-items: center;
      justify-content: space-between;
      padding: 7px 12px;
      border-radius: 2px;
      font-size: 12.5px;
      font-weight: 600;
      background-color: var(--card-bg);
      border: 1px solid var(--border-color);
      color: var(--text-color);
      cursor: pointer;
    }
    .tag-toggle-btn:hover {
      border-color: var(--econ-red);
    }
    .tag-toggle-active {
      color: var(--econ-red);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
    }
    .tag-toggle-chevron {
      display: inline-block;
      color: var(--muted-color);
      transition: transform 0.15s ease;
    }
    .tag-filter-section.open .tag-toggle-chevron {
      transform: rotate(180deg);
    }

    .tag-filter-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
    }

    @media (max-width: 640px) {
      body {
        padding: 14px 14px 40px;
      }
      .tag-toggle-btn {
        display: flex;
      }
      .tag-filter-section:not(.open) .tag-filter-bar {
        display: none;
      }
      .tag-filter-section.open .tag-filter-bar {
        margin-top: 8px;
      }
    }

    .tag-pill {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 10px;
      border-radius: 2px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      color: var(--muted-color);
      background-color: var(--card-bg);
      border: 1px solid var(--border-color);
    }
    .tag-pill:hover {
      border-color: var(--econ-red);
      color: var(--text-color);
    }
    .tag-pill.active {
      background-color: var(--econ-red-soft);
      color: var(--econ-red);
      border-color: var(--econ-red);
    }
    .pill-count {
      font-size: 11px;
      padding: 0 5px;
      border-radius: 2px;
      background-color: var(--header-bg);
      color: var(--muted-color);
    }
    .tag-pill.active .pill-count {
      color: var(--econ-red);
      font-weight: 700;
    }

    .wiki-card {
      background-color: var(--card-bg);
      border: 1px solid var(--border-color);
      border-top: 2px solid var(--text-color);
      border-radius: 2px;
      padding: 15px 18px;
    }
    .wiki-card.row-highlight {
      background-color: var(--highlight-bg);
      border-top-color: var(--econ-red);
      outline: 2px solid var(--econ-red);
      outline-offset: -2px;
    }

    .post-header { cursor: pointer; }
    .post-header.static-header { cursor: default; }
    .kicker-line {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--econ-red);
      margin-bottom: 4px;
      padding-left: 22px;
    }
    .static-header .kicker-line,
    .static-header .post-subline,
    .static-header .post-tags-row {
      padding-left: 0;
    }
    .post-title {
      font-family: var(--serif-font);
      font-weight: 700;
      font-size: 18px;
      line-height: 1.25;
      letter-spacing: -0.01em;
    }
    .post-subline {
      font-size: 13px;
      margin-top: 4px;
      padding-left: 22px;
    }
    .post-tags-row {
      margin-top: 8px;
      padding-left: 22px;
    }
    .post-meta-right {
      font-size: 11.5px;
      line-height: 1.4;
      text-align: right;
    }
    .post-word-count {
      font-size: 11px;
      opacity: 0.8;
      margin-top: 2px;
    }

    .chevron-wrap {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 14px;
      height: 14px;
      color: var(--econ-red);
      transition: transform 0.15s ease;
      flex-shrink: 0;
    }
    .chevron-wrap.open { transform: rotate(90deg); }
    .chevron-svg { width: 14px; height: 14px; }

    .category-tag {
      font-size: 11px;
      padding: 1px 7px;
      border-radius: 2px;
      background-color: var(--header-bg);
      color: var(--muted-color);
      border: 1px solid var(--border-color);
      font-weight: 600;
      cursor: pointer;
    }
    .category-tag:hover {
      border-color: var(--econ-red);
      color: var(--econ-red);
      text-decoration: none;
    }

    .verified-chip {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 7px;
      border-radius: 2px;
      background-color: var(--verified-bg);
      color: var(--verified-fg);
    }

    .more-pill {
      display: inline-block;
      padding: 1px 6px;
      border-radius: 2px;
      font-size: 11px;
      color: var(--muted-color);
      background-color: var(--header-bg);
      border: 1px solid var(--border-color);
      cursor: pointer;
    }
    .more-pill:hover {
      border-color: var(--econ-red);
      color: var(--econ-red);
      text-decoration: none;
    }

    .post-body {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--border-color);
    }

    .markdown-body {
      font-size: 14px;
      line-height: 1.6;
      color: var(--text-color);
    }
    .markdown-body .md-h2, .md-h2 {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--econ-red);
      margin: 0 0 5px 0;
    }
    .markdown-body .md-p { margin: 0; }
    .markdown-body .md-p + .md-p, .md-p + .md-p { margin-top: 9px; }
    .idea-section { margin-bottom: 14px; }

    .idea-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
      margin-bottom: 14px;
    }
    @media (min-width: 720px) {
      .idea-grid { grid-template-columns: 1fr 1fr; }
    }
    .idea-box {
      padding: 12px 14px;
      border-radius: 2px;
      background-color: var(--details-bg);
      border: 1px solid var(--border-color);
      border-top-width: 2.5px;
    }
    .idea-box-for { border-top-color: var(--econ-blue); }
    .idea-box-for .md-h2 { color: var(--econ-blue); }
    .idea-box-against { border-top-color: var(--econ-red); }

    .quote-block {
      margin: 0 0 12px 0;
      padding: 12px 16px;
      border-left: 3px solid var(--econ-red);
      background-color: var(--details-bg);
      font-family: var(--serif-font);
      font-size: 15px;
      line-height: 1.5;
      font-style: italic;
    }
    .quote-block footer {
      margin-top: 6px;
      font-family: var(--sans-font);
      font-style: normal;
      font-size: 12px;
      font-weight: 600;
      color: var(--muted-color);
    }

    /* Economist Graphic Detail Chart */
    .econ-chart-box {
      margin: 0 0 16px 0;
      padding: 14px 16px 12px;
      background-color: var(--details-bg);
      border: 1px solid var(--border-color);
      border-top: 2px solid var(--text-color);
    }
    .econ-chart-bar {
      width: 28px;
      height: 4px;
      background-color: var(--econ-red);
      margin-bottom: 8px;
    }
    .chart-title {
      font-family: var(--sans-font);
      font-size: 14.5px;
      font-weight: 700;
      color: var(--text-color);
      line-height: 1.25;
    }
    .chart-subtitle {
      font-size: 12px;
      color: var(--muted-color);
      margin-top: 2px;
      margin-bottom: 10px;
    }
    .chart-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-bottom: 8px;
      font-size: 11.5px;
      color: var(--muted-color);
    }
    .chart-legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .chart-legend-swatch {
      width: 14px;
      height: 3px;
      display: inline-block;
    }
    .chart-svg-wrap {
      width: 100%;
      overflow-x: auto;
    }
    .econ-svg {
      width: 100%;
      height: auto;
      display: block;
    }
    .chart-grid {
      stroke: var(--chart-grid);
      stroke-width: 1;
      stroke-dasharray: 2 2;
    }
    .chart-axis {
      stroke: var(--muted-color);
      stroke-width: 1;
    }
    .chart-tick {
      fill: var(--muted-color);
      font-size: 10.5px;
      font-family: var(--sans-font);
    }
    .chart-label {
      fill: var(--text-color);
      font-size: 11.5px;
      font-weight: 500;
      font-family: var(--sans-font);
    }
    .chart-val {
      fill: var(--text-color);
      font-size: 11.5px;
      font-weight: 700;
      font-family: var(--sans-font);
    }
    .chart-bar-primary { fill: var(--econ-red); }
    .chart-bar-bench { fill: var(--chart-bench); }
    .chart-line-primary { stroke: var(--econ-red); stroke-width: 2.5; fill: none; }
    .chart-line-secondary { stroke: var(--econ-blue); stroke-width: 2; fill: none; }
    .chart-dot-primary { fill: var(--econ-red); }
    .chart-dot-secondary { fill: var(--econ-blue); }
    .chart-source {
      margin-top: 6px;
      font-size: 11px;
      color: var(--muted-color);
    }

    .post-footer { padding-top: 6px; }
    .empty-state {
      padding: 28px 16px;
      text-align: center;
      background-color: var(--card-bg);
      border: 1px solid var(--border-color);
      color: var(--muted-color);
    }
"""

INDEX_SCRIPT = """\
    var activeTag = 'all';

    function getCookie(name) {
      try {
        var prefix = encodeURIComponent(name) + '=';
        var parts = document.cookie ? document.cookie.split(';') : [];
        for (var i = 0; i < parts.length; i++) {
          var c = parts[i].trim();
          if (c.indexOf(prefix) === 0) {
            return decodeURIComponent(c.slice(prefix.length));
          }
        }
      } catch (e) {}
      return null;
    }
    function setCookie(name, value) {
      try {
        document.cookie =
          encodeURIComponent(name) + '=' + encodeURIComponent(value) +
          '; max-age=31536000; path=/; SameSite=Lax';
      } catch (e) {}
    }
    function getPref(k) {
      var fromCookie = getCookie(k);
      if (fromCookie !== null) return fromCookie;
      try { return window.localStorage.getItem(k); } catch (e) { return null; }
    }
    function setPref(k, v) {
      setCookie(k, v);
      try { window.localStorage.setItem(k, v); } catch (e) {}
    }

    function applyTheme(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      var btn = document.getElementById('themeToggleBtn');
      if (btn) btn.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
    }
    function toggleTheme() {
      var cur = document.documentElement.getAttribute('data-theme') || 'light';
      var next = cur === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      setPref('book_ideas_theme', next);
    }

    function applyStyle(style) {
      var normalized = style === 'ft' ? 'ft' : 'economist';
      document.documentElement.setAttribute('data-style', normalized);
      var econBtn = document.getElementById('styleBtnEconomist');
      var ftBtn = document.getElementById('styleBtnFt');
      if (econBtn) {
        econBtn.classList.toggle('active', normalized === 'economist');
        econBtn.setAttribute('aria-pressed', normalized === 'economist' ? 'true' : 'false');
      }
      if (ftBtn) {
        ftBtn.classList.toggle('active', normalized === 'ft');
        ftBtn.setAttribute('aria-pressed', normalized === 'ft' ? 'true' : 'false');
      }
    }
    function setStyle(style) {
      applyStyle(style);
      setPref('book_ideas_style', style === 'ft' ? 'ft' : 'economist');
    }

    function togglePost(postId, forceOpen) {
      var body = document.getElementById('body-' + postId);
      var arrow = document.getElementById('arrow-' + postId);
      var card = document.getElementById('post-' + postId);
      if (!body || !arrow || !card) return;
      var header = card.querySelector('.post-header');
      var shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : body.classList.contains('hidden');
      body.classList.toggle('hidden', !shouldOpen);
      arrow.classList.toggle('open', shouldOpen);
      if (header) header.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
    }

    function handlePostKeydown(event, postId) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        togglePost(postId);
      }
    }

    function expandCollapseAll(open) {
      var cards = document.querySelectorAll('.post-card');
      cards.forEach(function(card) {
        if (!card.classList.contains('hidden')) {
          togglePost(card.getAttribute('data-post-id'), open);
        }
      });
    }

    function toggleTagBar(forceOpen) {
      var section = document.getElementById('tagFilterSection');
      var btn = document.getElementById('tagToggleBtn');
      if (!section || !btn) return;
      var shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : !section.classList.contains('open');
      section.classList.toggle('open', shouldOpen);
      btn.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
    }

    function setTagFilter(tag, skipHash) {
      activeTag = tag || 'all';
      document.querySelectorAll('.tag-pill').forEach(function(btn) {
        btn.classList.toggle('active', btn.getAttribute('data-tag') === activeTag);
      });
      var activeLabel = document.getElementById('tagToggleActive');
      if (activeLabel) activeLabel.textContent = activeTag === 'all' ? '#all' : activeTag;
      if (!skipHash && window.innerWidth <= 640) {
        toggleTagBar(false);
      }
      applyFilters(!skipHash);
    }

    function filterByTag(tag, event) {
      if (event) event.stopPropagation();
      setTagFilter(activeTag === tag ? 'all' : tag);
    }

    function resetFilters() {
      var input = document.getElementById('searchInput');
      if (input) input.value = '';
      activeTag = 'all';
      document.querySelectorAll('.post-card.row-highlight').forEach(function(el) {
        el.classList.remove('row-highlight');
      });
      setTagFilter('all');
    }

    function buildHashString() {
      var parts = [];
      if (activeTag && activeTag !== 'all') {
        parts.push('tag=' + encodeURIComponent(activeTag.replace(/^#/, '')));
      }
      var input = document.getElementById('searchInput');
      var q = input ? (input.value || '').trim() : '';
      if (q) parts.push('q=' + encodeURIComponent(q));
      return parts.length ? '#' + parts.join('&') : '#all';
    }

    function updateHashBadge(hashVal) {
      var badge = document.getElementById('currentHashBadge');
      if (badge) badge.textContent = hashVal || '#all';
    }

    function applyFilters(syncHash) {
      var input = document.getElementById('searchInput');
      var q = input ? (input.value || '').trim().toLowerCase() : '';
      var cards = document.querySelectorAll('.post-card');
      var shown = 0;
      cards.forEach(function(card) {
        var tags = (card.getAttribute('data-tags') || '').split(',');
        var hay = card.getAttribute('data-search') || '';
        var tagMatch = activeTag === 'all' || tags.indexOf(activeTag) !== -1;
        var qMatch = !q || hay.indexOf(q) !== -1;
        var visible = tagMatch && qMatch;
        card.classList.toggle('hidden', !visible);
        if (visible) shown += 1;
      });
      var label = document.getElementById('visibleCountLabel');
      if (label) label.textContent = 'Showing ' + shown + ' of ' + cards.length;
      var empty = document.getElementById('emptyBanner');
      if (empty) empty.classList.toggle('hidden', shown > 0 || cards.length === 0);
      if (syncHash) {
        var h = buildHashString();
        updateHashBadge(h);
        try { history.replaceState(null, '', h); } catch (e) {}
      }
    }

    function showCopiedToast() {
      var toast = document.getElementById('copyToast');
      if (!toast) return;
      toast.classList.remove('hidden');
      setTimeout(function() { toast.classList.add('hidden'); }, 1600);
    }

    function copyText(txt) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(showCopiedToast).catch(function() {});
      }
    }

    function copyShareLink() {
      copyText(window.location.href);
    }

    function copyPostHashLink(postId, event) {
      if (event) event.stopPropagation();
      var h = '#post=' + encodeURIComponent(postId);
      updateHashBadge(h);
      try { history.replaceState(null, '', h); } catch (e) {}
      copyText(window.location.href.split('#')[0] + h);
    }

    function applyHashFromLocation() {
      var raw = (window.location.hash || '').replace(/^#/, '');
      if (!raw || raw === 'all') {
        setTagFilter('all', true);
        updateHashBadge('#all');
        return;
      }
      var params = {};
      raw.split('&').forEach(function(pair) {
        var idx = pair.indexOf('=');
        if (idx > 0) {
          params[decodeURIComponent(pair.slice(0, idx))] = decodeURIComponent(pair.slice(idx + 1));
        } else {
          params[decodeURIComponent(pair)] = '';
        }
      });
      if (params.q) {
        var input = document.getElementById('searchInput');
        if (input) input.value = params.q;
      }
      if (params.tag) {
        var normalized = '#' + params.tag.replace(/^#/, '').toLowerCase();
        setTagFilter(normalized, true);
      } else {
        applyFilters(false);
      }
      if (params.post) {
        var target = document.getElementById('post-' + params.post);
        if (target) {
          target.classList.remove('hidden');
          togglePost(params.post, true);
          target.classList.add('row-highlight');
          setTimeout(function() { target.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 60);
        }
      }
      updateHashBadge('#' + raw);
    }

    (function init() {
      var savedTheme = getPref('book_ideas_theme');
      if (savedTheme === 'dark' || savedTheme === 'light') applyTheme(savedTheme);
      var savedStyle = getPref('book_ideas_style');
      applyStyle(savedStyle === 'ft' ? 'ft' : 'economist');
      applyHashFromLocation();
      window.addEventListener('hashchange', applyHashFromLocation);
    })();
"""

ENTRY_SCRIPT = """\
    function getCookie(name) {
      try {
        var prefix = encodeURIComponent(name) + '=';
        var parts = document.cookie ? document.cookie.split(';') : [];
        for (var i = 0; i < parts.length; i++) {
          var c = parts[i].trim();
          if (c.indexOf(prefix) === 0) {
            return decodeURIComponent(c.slice(prefix.length));
          }
        }
      } catch (e) {}
      return null;
    }
    function setCookie(name, value) {
      try {
        document.cookie =
          encodeURIComponent(name) + '=' + encodeURIComponent(value) +
          '; max-age=31536000; path=/; SameSite=Lax';
      } catch (e) {}
    }
    function getPref(k) {
      var fromCookie = getCookie(k);
      if (fromCookie !== null) return fromCookie;
      try { return window.localStorage.getItem(k); } catch (e) { return null; }
    }
    function setPref(k, v) {
      setCookie(k, v);
      try { window.localStorage.setItem(k, v); } catch (e) {}
    }
    function applyTheme(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      var btn = document.getElementById('themeToggleBtn');
      if (btn) btn.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
    }
    function toggleTheme() {
      var cur = document.documentElement.getAttribute('data-theme') || 'light';
      var next = cur === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      setPref('book_ideas_theme', next);
    }
    function applyStyle(style) {
      var normalized = style === 'ft' ? 'ft' : 'economist';
      document.documentElement.setAttribute('data-style', normalized);
      var econBtn = document.getElementById('styleBtnEconomist');
      var ftBtn = document.getElementById('styleBtnFt');
      if (econBtn) {
        econBtn.classList.toggle('active', normalized === 'economist');
        econBtn.setAttribute('aria-pressed', normalized === 'economist' ? 'true' : 'false');
      }
      if (ftBtn) {
        ftBtn.classList.toggle('active', normalized === 'ft');
        ftBtn.setAttribute('aria-pressed', normalized === 'ft' ? 'true' : 'false');
      }
    }
    function setStyle(style) {
      applyStyle(style);
      setPref('book_ideas_style', style === 'ft' ? 'ft' : 'economist');
    }
    function copyShareLink() {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(window.location.href).then(function() {
          var toast = document.getElementById('copyToast');
          if (!toast) return;
          toast.classList.remove('hidden');
          setTimeout(function() { toast.classList.add('hidden'); }, 1600);
        }).catch(function() {});
      }
    }
    (function init() {
      var savedTheme = getPref('book_ideas_theme');
      if (savedTheme === 'dark' || savedTheme === 'light') applyTheme(savedTheme);
      var savedStyle = getPref('book_ideas_style');
      applyStyle(savedStyle === 'ft' ? 'ft' : 'economist');
    })();
"""


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def render_paragraphs(text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", (text or "").strip()) if b.strip()]
    if not blocks:
        return ""
    return "\n".join(f'<p class="md-p">{esc(block)}</p>' for block in blocks)


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


def count_words(post: dict[str, Any]) -> int:
    fields = [
        post.get("core_idea", ""),
        post.get("example", ""),
        post.get("argument_for", ""),
        post.get("argument_against", ""),
        post.get("quote", ""),
    ]
    return len(" ".join(fields).split())


def render_hbar_chart(chart: dict[str, Any]) -> str:
    bars = chart.get("bars") or []
    if not bars:
        return ""
    unit = str(chart.get("unit") or "")
    max_val = float(chart.get("max") or max((float(b.get("value", 0)) for b in bars), default=100))
    if max_val <= 0:
        max_val = 100.0
    ticks = chart.get("ticks")
    if not ticks:
        step = max_val / 4.0
        ticks = [round(step * i, 2) for i in range(5)]

    width = 680
    left_pad = 260.0
    right_pad = 54.0
    plot_w = width - left_pad - right_pad
    top_pad = 14.0
    row_h = 34.0
    bar_h = 18.0
    height = int(top_pad + len(bars) * row_h + 22)
    grid_bottom = height - 10

    lines: list[str] = []
    for tick in ticks:
        t_val = float(tick)
        x = left_pad + (t_val / max_val) * plot_w
        lines.append(
            f'<line x1="{x:.1f}" y1="{top_pad:.0f}" x2="{x:.1f}" y2="{grid_bottom}" class="chart-grid"></line>'
        )
        lines.append(
            f'<text x="{x:.1f}" y="11" text-anchor="middle" class="chart-tick">{esc(format_num(tick, unit))}</text>'
        )

    for idx, bar in enumerate(bars):
        val = float(bar.get("value", 0))
        y_top = top_pad + 16.0 + idx * row_h
        y_text = y_top + 13.3
        bar_w = max(2.0, (val / max_val) * plot_w) if val > 0 else 0.0
        bar_cls = "chart-bar-bench" if bar.get("benchmark") else "chart-bar-primary"
        label = str(bar.get("label") or "")
        lines.append(
            f'<text x="{left_pad - 12:.0f}" y="{y_text:.1f}" text-anchor="end" class="chart-label">{esc(label)}</text>'
        )
        lines.append(
            f'<rect x="{left_pad:.0f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{bar_h:.0f}" rx="1.5" class="{bar_cls}"></rect>'
        )
        lines.append(
            f'<text x="{left_pad + bar_w + 6.0:.1f}" y="{y_text:.1f}" class="chart-val">{esc(format_num(bar.get("value", 0), unit))}</text>'
        )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="econ-svg" role="img" '
        f'aria-label="{esc(chart.get("title", "Chart"))}">\n'
        + "\n".join(lines)
        + "\n</svg>"
    )
    return wrap_chart_box(chart, svg)


def render_line_chart(chart: dict[str, Any]) -> str:
    series_list = chart.get("series") or []
    x_labels = chart.get("x_labels") or []
    if not series_list or not x_labels:
        return ""

    unit = str(chart.get("unit") or "")
    all_vals = [
        float(v)
        for s in series_list
        for v in (s.get("values") or [])
        if v is not None
    ]
    if not all_vals:
        return ""

    y_min = float(chart.get("y_min", min(0.0, min(all_vals))))
    y_max = float(chart.get("y_max", max(all_vals)))
    if y_max <= y_min:
        y_max = y_min + 1.0
    y_ticks = chart.get("y_ticks")
    if not y_ticks:
        step = (y_max - y_min) / 4.0
        y_ticks = [round(y_min + step * i, 2) for i in range(5)]

    width = 680
    height = 230
    left_pad = 54.0
    right_pad = 24.0
    top_pad = 16.0
    bottom_pad = 32.0
    plot_w = width - left_pad - right_pad
    plot_h = height - top_pad - bottom_pad

    def x_pos(i: int) -> float:
        if len(x_labels) == 1:
            return left_pad + plot_w / 2.0
        return left_pad + (i / (len(x_labels) - 1)) * plot_w

    def y_pos(v: float) -> float:
        return top_pad + (1.0 - (v - y_min) / (y_max - y_min)) * plot_h

    lines: list[str] = []
    for tick in y_ticks:
        y = y_pos(float(tick))
        lines.append(
            f'<line x1="{left_pad:.1f}" y1="{y:.1f}" x2="{width - right_pad:.1f}" y2="{y:.1f}" class="chart-grid"></line>'
        )
        lines.append(
            f'<text x="{left_pad - 8:.1f}" y="{y + 3.5:.1f}" text-anchor="end" class="chart-tick">{esc(format_num(tick, unit))}</text>'
        )

    # Bottom axis line
    axis_y = top_pad + plot_h
    lines.append(
        f'<line x1="{left_pad:.1f}" y1="{axis_y:.1f}" x2="{width - right_pad:.1f}" y2="{axis_y:.1f}" class="chart-axis"></line>'
    )

    # X-axis labels
    step_x = max(1, len(x_labels) // 8)
    for idx, lbl in enumerate(x_labels):
        if idx % step_x == 0 or idx == len(x_labels) - 1:
            x = x_pos(idx)
            lines.append(
                f'<text x="{x:.1f}" y="{axis_y + 18:.1f}" text-anchor="middle" class="chart-tick">{esc(lbl)}</text>'
            )

    legend_items: list[str] = []
    for s_idx, s in enumerate(series_list):
        vals = s.get("values") or []
        is_primary = s_idx == 0
        line_cls = "chart-line-primary" if is_primary else "chart-line-secondary"
        dot_cls = "chart-dot-primary" if is_primary else "chart-dot-secondary"
        swatch_color = "var(--econ-red)" if is_primary else "var(--econ-blue)"
        if s.get("label"):
            legend_items.append(
                f'<span class="chart-legend-item">'
                f'<span class="chart-legend-swatch" style="background:{swatch_color};"></span>'
                f'{esc(s["label"])}</span>'
            )

        pts: list[str] = []
        dots: list[str] = []
        for idx, raw_v in enumerate(vals):
            if raw_v is None or idx >= len(x_labels):
                continue
            x = x_pos(idx)
            y = y_pos(float(raw_v))
            pts.append(f"{x:.1f},{y:.1f}")
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" class="{dot_cls}"></circle>')
        if pts:
            lines.append(f'<polyline points="{" ".join(pts)}" class="{line_cls}"></polyline>')
            lines.extend(dots)

    legend_html = (
        f'<div class="chart-legend">{"".join(legend_items)}</div>'
        if len(legend_items) > 1
        else ""
    )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="econ-svg" role="img" '
        f'aria-label="{esc(chart.get("title", "Chart"))}">\n'
        + "\n".join(lines)
        + "\n</svg>"
    )
    return wrap_chart_box(chart, svg, legend_html=legend_html)


def wrap_chart_box(chart: dict[str, Any], svg: str, legend_html: str = "") -> str:
    title = esc(chart.get("title", ""))
    subtitle = esc(chart.get("subtitle", ""))
    source = esc(chart.get("source", ""))
    source_html = f'<div class="chart-source">Source: {source}</div>' if source else ""
    subtitle_html = f'<p class="chart-subtitle">{subtitle}</p>' if subtitle else ""
    return (
        '          <figure class="econ-chart-box">\n'
        '            <div class="econ-chart-bar"></div>\n'
        f'            <h5 class="chart-title">{title}</h5>\n'
        f"            {subtitle_html}\n"
        f"            {legend_html}\n"
        '            <div class="chart-svg-wrap">\n'
        f"              {svg}\n"
        "            </div>\n"
        f"            {source_html}\n"
        "          </figure>"
    )


def render_chart(chart: dict[str, Any] | None) -> str:
    if not chart or not isinstance(chart, dict):
        return ""
    chart_type = str(chart.get("type") or "").lower()
    if chart_type == "hbar":
        return render_hbar_chart(chart)
    if chart_type == "line":
        return render_line_chart(chart)
    return ""


def normalize_tag(tag: str) -> str:
    t = tag.strip().lower()
    if not t.startswith("#"):
        t = "#" + t
    return t


def build_kicker(post: dict[str, Any]) -> str:
    tags = [normalize_tag(t) for t in (post.get("tags") or []) if str(t).strip()]
    parts: list[str] = []
    if tags:
        parts.append(tags[0].lstrip("#").replace("-", " ").upper())
    award = str(post.get("award") or "").strip()
    if award:
        parts.append(award.upper())
    return " · ".join(parts) if parts else "READING BRIEF"


def render_post_body(post: dict[str, Any], body_id: str, hidden: bool) -> str:
    post_id = str(post.get("id") or "")
    chart_html = render_chart(post.get("chart"))
    quote = str(post.get("quote") or "").strip()
    quote_source = str(post.get("quote_source") or "").strip()
    quote_html = ""
    if quote:
        footer = f"<footer>— {esc(quote_source)}</footer>" if quote_source else ""
        quote_html = (
            '          <blockquote class="quote-block">\n'
            f"            <p>“{esc(quote)}”</p>\n"
            f"            {footer}\n"
            "          </blockquote>"
        )
    hidden_cls = "hidden " if hidden else ""
    return (
        f'        <div id="{esc(body_id)}" class="{hidden_cls}markdown-body post-body">\n'
        '          <div class="idea-section">\n'
        '            <h4 class="md-h2">Core Idea</h4>\n'
        f'            {render_paragraphs(post.get("core_idea", ""))}\n'
        "          </div>\n"
        f"{chart_html}\n"
        '          <div class="idea-section">\n'
        '            <h4 class="md-h2">Example from the Book</h4>\n'
        f'            {render_paragraphs(post.get("example", ""))}\n'
        "          </div>\n"
        '          <div class="idea-grid">\n'
        '            <div class="idea-box idea-box-for">\n'
        '              <h4 class="md-h2">Argue For</h4>\n'
        f'              {render_paragraphs(post.get("argument_for", ""))}\n'
        "            </div>\n"
        '            <div class="idea-box idea-box-against">\n'
        '              <h4 class="md-h2">Argue Against</h4>\n'
        f'              {render_paragraphs(post.get("argument_against", ""))}\n'
        "            </div>\n"
        "          </div>\n"
        f"{quote_html}\n"
        '          <div class="post-footer flex items-center justify-end gap-2 muted-text">\n'
        f'            <span class="font-mono" style="font-size: 11px;">#{esc(post_id)}</span>\n'
        "          </div>\n"
        "        </div>"
    )


def render_post_card(post: dict[str, Any], expanded: bool) -> str:
    post_id = str(post.get("id") or "")
    date = str(post.get("date") or "")
    title = str(post.get("title") or "")
    book = str(post.get("book") or "")
    author = str(post.get("author") or "")
    award = str(post.get("award") or "")
    tags = [normalize_tag(t) for t in (post.get("tags") or []) if str(t).strip()]
    words = count_words(post)

    search_blob = " ".join(
        [
            date,
            title,
            book,
            author,
            award,
            " ".join(tags),
            str(post.get("core_idea") or ""),
            str(post.get("example") or ""),
            str(post.get("argument_for") or ""),
            str(post.get("argument_against") or ""),
            str(post.get("quote") or ""),
        ]
    ).lower()

    tag_buttons = " ".join(
        f'<button type="button" class="category-tag" data-tag="{esc(t)}" '
        f"onclick=\"filterByTag(this.getAttribute('data-tag'), event)\" "
        f'title="Filter {esc(t)}">{esc(t)}</button>'
        for t in tags
    )

    open_cls = " open" if expanded else ""
    aria_exp = "true" if expanded else "false"
    kicker = build_kicker(post)
    body_html = render_post_body(post, f"body-{post_id}", hidden=not expanded)

    return (
        f'      <article id="post-{esc(post_id)}" class="wiki-card post-card" '
        f'data-post-id="{esc(post_id)}" data-tags="{esc(",".join(tags))}" '
        f'data-book="{esc(book)}" data-search="{esc(search_blob)}">\n'
        f'        <div class="flex items-start justify-between gap-3 post-header" tabindex="0" role="button" '
        f'aria-expanded="{aria_exp}" aria-controls="body-{esc(post_id)}" '
        f"onclick=\"togglePost(this.closest('.post-card').getAttribute('data-post-id'))\" "
        f"onkeydown=\"handlePostKeydown(event, this.closest('.post-card').getAttribute('data-post-id'))\">\n"
        '          <div class="min-w-0 flex-1">\n'
        f'            <div class="kicker-line">{esc(kicker)}</div>\n'
        '            <div class="flex items-center gap-2">\n'
        f'              <span id="arrow-{esc(post_id)}" class="chevron-wrap{open_cls}">\n'
        '                <svg class="chevron-svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">\n'
        '                  <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd"></path>\n'
        "                </svg>\n"
        "              </span>\n"
        f'              <h2 class="post-title">{esc(title)}</h2>\n'
        "            </div>\n"
        '            <div class="post-subline muted-text">\n'
        f"              <span><strong>{esc(book)}</strong> · {esc(author)}</span>\n"
        "            </div>\n"
        '            <div class="flex items-center gap-1-5 flex-wrap post-tags-row" onclick="event.stopPropagation()">\n'
        f"              {tag_buttons}\n"
        "            </div>\n"
        "          </div>\n"
        '          <div class="muted-text shrink-0 post-meta-right" onclick="event.stopPropagation()">\n'
        '            <div class="flex items-center justify-end gap-1">\n'
        f'              <span class="font-mono">{esc(date)}</span>\n'
        f'              <a class="more-pill" href="entries/{esc(post_id)}.html" title="Open standalone entry page">Entry ↗</a>\n'
        f'              <button type="button" class="more-pill" onclick="copyPostHashLink(this.closest(\'.post-card\').getAttribute(\'data-post-id\'), event)" title="Copy deep link (#post={esc(post_id)})">#</button>\n'
        "            </div>\n"
        f'            <div class="post-word-count">{words} words</div>\n'
        "          </div>\n"
        "        </div>\n"
        f"{body_html}\n"
        "      </article>"
    )


def render_standalone_entry(post: dict[str, Any]) -> str:
    post_id = str(post.get("id") or "")
    date = str(post.get("date") or "")
    title = str(post.get("title") or "")
    book = str(post.get("book") or "")
    author = str(post.get("author") or "")
    tags = [normalize_tag(t) for t in (post.get("tags") or []) if str(t).strip()]
    words = count_words(post)
    kicker = build_kicker(post)
    tag_links = " ".join(
        f'<a class="category-tag" href="../index.html#tag={esc(t.lstrip("#"))}">{esc(t)}</a>'
        for t in tags
    )
    body_html = render_post_body(post, f"body-{post_id}", hidden=False)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light" data-style="economist">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} — Daily Book Ideas</title>
  <link rel="icon" type="image/svg+xml" href="{FAVICON}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,400&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
  <style>
{CSS}
  </style>
</head>
<body>
  <div class="container">
    <header class="masthead flex flex-wrap justify-between items-center gap-3">
      <div>
        <div class="flex items-center gap-2 flex-wrap" style="margin-bottom: 5px;">
          <span class="econ-brand-pill">Reading Brief</span>
          <a href="../index.html" class="action-btn">← All Daily Book Ideas</a>
        </div>
        <h1 class="masthead-title">Daily Book Ideas</h1>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <div class="style-switch" role="group" aria-label="Editorial theme">
          <button type="button" id="styleBtnEconomist" class="style-switch-btn active" aria-pressed="true" onclick="setStyle('economist')">Economist</button>
          <button type="button" id="styleBtnFt" class="style-switch-btn" aria-pressed="false" onclick="setStyle('ft')">FT</button>
        </div>
        <button type="button" class="action-btn" onclick="copyShareLink()" title="Copy entry link">Copy Link</button>
        <div id="copyToast" class="hidden toast-pill" role="status" aria-live="polite">Copied!</div>
        <button type="button" id="themeToggleBtn" class="action-btn" onclick="toggleTheme()">Dark Mode</button>
      </div>
    </header>

    <main class="grid-1">
      <article class="wiki-card">
        <div class="flex items-start justify-between gap-3 post-header static-header">
          <div class="min-w-0 flex-1">
            <div class="kicker-line">{esc(kicker)}</div>
            <h2 class="post-title">{esc(title)}</h2>
            <div class="post-subline muted-text">
              <span><strong>{esc(book)}</strong> · {esc(author)}</span>
            </div>
            <div class="flex items-center gap-1-5 flex-wrap post-tags-row">
              {tag_links}
            </div>
          </div>
          <div class="muted-text shrink-0 post-meta-right">
            <div class="font-mono">{esc(date)}</div>
            <div class="post-word-count">{words} words</div>
          </div>
        </div>
{body_html}
      </article>
    </main>
  </div>
  <script>
{ENTRY_SCRIPT}
  </script>
</body>
</html>
"""


def render_index(data: dict[str, Any]) -> str:
    raw_posts = data.get("posts") or []
    queue = data.get("queue") or []
    updated_at = str(data.get("updated_at") or "").strip()

    # Sort newest first (preserve order for same-day entries by reversing index)
    indexed_posts = list(enumerate(raw_posts))
    indexed_posts.sort(key=lambda item: (str(item[1].get("date") or ""), item[0]), reverse=True)
    posts = [p for _, p in indexed_posts]

    books_count = len({str(p.get("book") or "").strip().lower() for p in posts if p.get("book")})
    tag_counts: Counter[str] = Counter()
    for p in posts:
        for t in p.get("tags") or []:
            if str(t).strip():
                tag_counts[normalize_tag(str(t))] += 1

    sorted_tags = sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    tag_pills = "\n".join(
        f'      <button type="button" class="tag-pill" data-tag="{esc(tag)}" '
        f"onclick=\"setTagFilter(this.getAttribute('data-tag'))\">{esc(tag)} "
        f'<span class="pill-count">{count}</span></button>'
        for tag, count in sorted_tags
    )

    queue_stat = (
        f'            <span class="muted-text">·</span>\n'
        f'            <span class="stat-item">Queued <strong>{len(queue)}</strong></span>'
        if queue
        else ""
    )

    updated_label = (
        f" · updated <code>{esc(updated_at)}</code>"
        if updated_at
        else " · awaiting first digest"
    )

    if posts:
        cards_html = "\n".join(
            render_post_card(post, expanded=(idx == 0))
            for idx, post in enumerate(posts)
        )
        initial_empty_html = ""
    else:
        cards_html = ""
        initial_empty_html = (
            '    <div class="empty-state">'
            "No digests published yet. Trigger the <strong>Daily Book Ideas</strong> workflow in GitHub Actions (or wait for the next weekday at 06:30 Munich time) to publish the first entry."
            "</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light" data-style="economist">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Book Ideas — Reading Log</title>
  <link rel="icon" type="image/svg+xml" href="{FAVICON}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,400&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
  <style>
{CSS}
  </style>
</head>
<body>
  <div class="container">
    <!-- Masthead -->
    <header class="masthead flex flex-wrap justify-between items-center gap-3">
      <div>
        <div class="flex items-center gap-2 flex-wrap" style="margin-bottom: 5px;">
          <span class="econ-brand-pill">Reading Brief</span>
          <div class="stat-strip" aria-label="Reading log counts">
            <span class="stat-item">Posts <strong id="hdrPostsCount">{len(posts)}</strong></span>
            <span class="muted-text">·</span>
            <span class="stat-item">Books <strong>{books_count}</strong></span>
            <span class="muted-text">·</span>
            <span class="stat-item">Tags <strong>{len(tag_counts)}</strong></span>
{queue_stat}
          </div>
        </div>
        <h1 class="masthead-title">Daily Book Ideas</h1>
        <div style="font-size: 12.5px; margin-top: 3px;" class="muted-text">
          One distilled, fact-checked idea per weekday{updated_label}
        </div>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <div class="style-switch" role="group" aria-label="Editorial theme">
          <button type="button" id="styleBtnEconomist" class="style-switch-btn active" aria-pressed="true" onclick="setStyle('economist')">Economist</button>
          <button type="button" id="styleBtnFt" class="style-switch-btn" aria-pressed="false" onclick="setStyle('ft')">FT</button>
        </div>
        <code id="currentHashBadge" class="hash-badge font-mono" title="Current URL hash">#all</code>
        <button type="button" class="action-btn" onclick="copyShareLink()" title="Copy current filtered link">Copy Link</button>
        <div id="copyToast" class="hidden toast-pill" role="status" aria-live="polite">Copied!</div>
        <button type="button" id="themeToggleBtn" class="action-btn" onclick="toggleTheme()">Dark Mode</button>
      </div>
    </header>

    <!-- Search & Controls -->
    <div class="toolbar flex flex-wrap items-center justify-between gap-2">
      <div class="flex flex-wrap items-center gap-2 flex-1">
        <input type="text" id="searchInput" style="width: 300px; max-width: 100%;" aria-label="Filter posts" placeholder="Filter by book, author, idea, or #tag..." oninput="applyFilters(true)">
        <button type="button" class="action-btn" onclick="expandCollapseAll(true)">Expand All</button>
        <button type="button" class="action-btn" onclick="expandCollapseAll(false)">Collapse All</button>
        <button type="button" class="action-btn" onclick="resetFilters()">Reset</button>
      </div>
      <div id="visibleCountLabel" class="muted-text" style="font-size: 12px;">Showing {len(posts)} of {len(posts)}</div>
    </div>

    <!-- Hashtag Filter Bar (collapsible on mobile) -->
    <div id="tagFilterSection" class="tag-filter-section">
      <button type="button" id="tagToggleBtn" class="tag-toggle-btn" aria-expanded="false" aria-controls="tagFilterBar" onclick="toggleTagBar()">
        <span class="flex items-center gap-2">
          <span>Filter by tag</span>
          <span id="tagToggleActive" class="tag-toggle-active">#all</span>
          <span class="pill-count">{len(tag_counts)}</span>
        </span>
        <span class="tag-toggle-chevron" aria-hidden="true">▾</span>
      </button>
      <div id="tagFilterBar" class="tag-filter-bar" role="group" aria-label="Filter by hashtag">
        <button type="button" class="tag-pill active" data-tag="all" onclick="setTagFilter('all')">
          #all <span class="pill-count">{len(posts)}</span>
        </button>
{tag_pills}
      </div>
    </div>

    <!-- Posts Feed -->
    <main id="postsContainer" class="grid-1">
{cards_html}
    </main>
{initial_empty_html}
    <div id="emptyBanner" class="empty-state hidden">No posts match this filter. <a href="#all" onclick="resetFilters(); return false;">Show all posts</a>.</div>
  </div>

  <script>
{INDEX_SCRIPT}
  </script>
</body>
</html>
"""


def main() -> None:
    if not POSTS_JSON.exists():
        raise FileNotFoundError(f"Missing {POSTS_JSON}")

    data = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Rebuild entries directory cleanly
    if ENTRIES_DIR.exists():
        shutil.rmtree(ENTRIES_DIR)
    ENTRIES_DIR.mkdir(parents=True, exist_ok=True)

    # Write index.html
    (DOCS_DIR / "index.html").write_text(render_index(data), encoding="utf-8")

    # Write standalone entry pages
    for post in data.get("posts") or []:
        post_id = str(post.get("id") or "").strip()
        if not post_id:
            continue
        safe_id = re.sub(r"[^a-zA-Z0-9._-]", "-", post_id)
        (ENTRIES_DIR / f"{safe_id}.html").write_text(
            render_standalone_entry(post), encoding="utf-8"
        )

    # Add .nojekyll for GitHub Pages
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(
        f"Built site in {DOCS_DIR} with {len(data.get('posts') or [])} posts "
        f"and {len(data.get('queue') or [])} queued items."
    )


if __name__ == "__main__":
    main()
