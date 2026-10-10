import requests
import json
import os
import hashlib
from datetime import date
from bs4 import BeautifulSoup
from groq import Groq
from dotenv import load_dotenv

import sys
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

_GROQ_KEY = os.getenv("GROQ_API_KEY")
if not _GROQ_KEY:
    # Fail fast instead of letting every LLM call error out and get swallowed,
    # which made CI runs pass green while producing zero files.
    print("ERROR: GROQ_API_KEY is not set. Set it as an env var / GitHub secret.")
    sys.exit(1)
# Generous retries: the free tier rate-limits (429) when several long pages are
# formatted back to back, and the SDK backs off between attempts.
client = Groq(api_key=_GROQ_KEY, max_retries=6)

SOURCES_FILE = "knowledge-base/sources.json"
HASHES_FILE  = "scripts/seen_hashes.json"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; SchemeBot/1.0)"}

# Long pages (scheme guideline PDFs run to 30-70k characters) are formatted in
# parts. The old single 4,000-character cut saw under 10% of such documents, so
# amounts and eligibility rules deeper in them never reached the knowledge base.
WINDOW_CHARS = 10000   # text per LLM call
MAX_WINDOWS  = 8       # per source, to bound token use (~80k characters)

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  Warning: Failed to load {path} ({e}). Using default.")
        return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

import urllib3
import io
from pypdf import PdfReader
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def scrape(url):
    r = requests.get(url, timeout=30, headers=HEADERS, verify=False)
    r.raise_for_status()
    
    if url.lower().endswith(".pdf") or "application/pdf" in r.headers.get("Content-Type", ""):
        reader = PdfReader(io.BytesIO(r.content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

def windows(text):
    """Split text into WINDOW_CHARS-sized parts at line breaks, capped at MAX_WINDOWS."""
    parts, current = [], ""
    for line in text.splitlines():
        if current and len(current) + len(line) + 1 > WINDOW_CHARS:
            parts.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current.strip():
        parts.append(current)
    return parts[:MAX_WINDOWS]

def convert_to_markdown(raw_text, url, category, part=(1, 1)):
    prompt = f"""
You are a government welfare document formatter for India.
Convert the scraped text below into structured Markdown.

ACCURACY RULES (this text becomes the chatbot's only source of truth):
- Use ONLY facts stated in the text. Never add anything from memory.
- Copy amounts, percentages, age limits, income limits and eligibility rules EXACTLY as written.
- If the text gives no information for a section, write "Not stated in the source."
- scheme_name must ALWAYS be a real name from the text. For general rules that belong to no single
  scheme, name the document instead, e.g. "Scholarship guidelines - general rules".

For EACH disability scheme found, use this exact format:

---
scheme_name: "<full name>"
ministry: "<ministry or department>"
category: "{category}"
disability_types: ["list relevant types, or write 'all'"]
last_updated: "{date.today()}"
source_url: "{url}"
---

## Overview
(2-3 sentences about what this scheme is)

## Benefits
- benefit 1
- benefit 2

## Eligibility criteria
- criteria 1
- criteria 2

## Required documents
1. document 1
2. document 2

## How to apply
Step by step instructions

## Contact
Phone / email / portal link if available

---NEXT SCHEME---

Repeat the above block for every scheme found on the page.
If the text is a legal aid document, general rule, or court order, STILL FORMAT it as a single scheme summarizing the rights and instructions. Only reply NO_SCHEME_FOUND if the document is completely empty or an error page.

Raw text (part {part[0]} of {part[1]} of this page):
{raw_text}
"""
    model = os.getenv("GROQ_SCRAPE_MODEL", "openai/gpt-oss-120b")
    extra = {}
    if "gpt-oss" in model:
        # Reasoning model: keep its thinking short so it cannot use up the whole
        # reply budget and return empty content.
        extra = {"reasoning_effort": "low", "max_completion_tokens": 8192}
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        **extra,
    )
    return (resp.choices[0].message.content or "").strip()

import re

def slugify(text):
    slug = "".join(
        c if c.isalnum() or c == "-" else "-"
        for c in text.lower().strip()
    )
    slug = re.sub(r"-+", "-", slug)
    return slug[:50].strip("-")

def run(new_only=False):
    sources   = load_json(SOURCES_FILE, [])
    seen      = load_json(HASHES_FILE, {})
    new_files = []

    active    = [s for s in sources if s.get("active", True)]
    if new_only:
        # Only sources never scraped before, e.g. right after adding some to sources.json.
        active = [s for s in active if s["url"] not in seen]
    fetched   = 0   # sources we successfully downloaded
    fetch_err = 0   # sources that failed to download (e.g. IP block / timeout)

    for source in active:
        url      = source["url"]
        category = source["category"]
        print(f"\nScraping: {url}")

        try:
            raw = scrape(url)
            fetched += 1
        except Exception as e:
            fetch_err += 1
            print(f"  ERROR fetching page: {e}")
            continue

        if not raw or not raw.strip():
            print("  Empty content, skipping.")
            continue

        content_hash = hashlib.md5(raw.encode("utf-8")).hexdigest()

        if seen.get(url) == content_hash:
            print("  No changes detected, skipping.")
            continue

        parts = windows(raw)
        print(f"  Converting to markdown via LLM ({len(parts)} part(s))...")
        try:
            mds = [convert_to_markdown(w, url, category, part=(k, len(parts)))
                   for k, w in enumerate(parts, 1)]
        except Exception as e:
            # Hash NOT recorded, so the page is retried on the next run instead
            # of being skipped forever as "No changes detected".
            print(f"  ERROR in LLM call: {e}")
            continue
        seen[url] = content_hash

        mds = [m for m in mds if m and "NO_SCHEME_FOUND" not in m]
        if not mds:
            print("  No disability schemes found on this page.")
            continue

        blocks = [b.strip() for m in mds for b in m.split("---NEXT SCHEME---") if b.strip()]
        print(f"  Found {len(blocks)} scheme(s).")

        for i, block in enumerate(blocks):
            name_lines = [l for l in block.splitlines() if "scheme_name:" in l]
            if name_lines:
                raw_name  = name_lines[0].split(":", 1)[-1].strip().strip('"')
                if raw_name.lower().startswith("not stated"):
                    raw_name = f"{category} general rules"  # never name a file "not-stated-..." 
                slug_name = slugify(raw_name) or f"scheme-{i+1}"
            else:
                slug_name = f"scheme-{i+1}"

            filename = f"{slug_name}-{date.today()}.md"
            folder   = f"knowledge-base/{category}"
            os.makedirs(folder, exist_ok=True)
            filepath = f"{folder}/{filename}"

            counter = 1
            while os.path.exists(filepath):
                filename = f"{slug_name}-{date.today()}_{counter}.md"
                filepath = f"{folder}/{filename}"
                counter += 1

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(block)

            new_files.append(filepath)
            try:
                print(f"  Saved: {filepath}")
            except UnicodeEncodeError:
                print(f"  Saved: {filepath.encode('ascii', 'ignore').decode('ascii')}")

    save_json(HASHES_FILE, seen)
    print(
        f"\nFinished. {len(new_files)} new/updated file(s) created. "
        f"Sources: {fetched} fetched, {fetch_err} failed, {len(active)} active."
    )

    # A total blackout (every active source failed to download) almost always
    # means the runner's IP is blocked or the sites are down -- surface it as a
    # failed job instead of a green run that quietly changed nothing.
    if active and fetched == 0:
        print("ERROR: every active source failed to download. Failing the job.")
        sys.exit(1)

if __name__ == "__main__":
    run(new_only="--new-only" in sys.argv)
