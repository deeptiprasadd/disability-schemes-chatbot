import requests
import json
import os
import hashlib
from datetime import date
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SOURCES_FILE = "knowledge-base/sources.json"
HASHES_FILE  = "scripts/seen_hashes.json"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; SchemeBot/1.0)"}

def load_json(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

def scrape(url):
    r = requests.get(url, timeout=20, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

def convert_to_markdown(raw_text, url, category):
    prompt = f"""
You are a government welfare document formatter for India.
Convert the scraped text below into structured Markdown.

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
If no disability-related scheme is found, reply with exactly: NO_SCHEME_FOUND

Raw text (first 4000 characters):
{raw_text[:4000]}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return resp.choices[0].message.content.strip()

def slugify(text):
    return "".join(
        c if c.isalnum() or c == "-" else "-"
        for c in text.lower().strip()
    )[:50].strip("-")

def run():
    sources   = load_json(SOURCES_FILE, [])
    seen      = load_json(HASHES_FILE, {})
    new_files = []

    for source in sources:
        if not source.get("active", True):
            continue

        url      = source["url"]
        category = source["category"]
        print(f"\nScraping: {url}")

        try:
            raw = scrape(url)
        except Exception as e:
            print(f"  ERROR fetching page: {e}")
            continue

        content_hash = hashlib.md5(raw.encode("utf-8")).hexdigest()

        if seen.get(url) == content_hash:
            print("  No changes detected, skipping.")
            continue

        seen[url] = content_hash

        print("  Converting to markdown via LLM...")
        try:
            md = convert_to_markdown(raw, url, category)
        except Exception as e:
            print(f"  ERROR in LLM call: {e}")
            continue

        if "NO_SCHEME_FOUND" in md:
            print("  No disability schemes found on this page.")
            continue

        blocks = [b.strip() for b in md.split("---NEXT SCHEME---") if b.strip()]
        print(f"  Found {len(blocks)} scheme(s).")

        for i, block in enumerate(blocks):
            name_lines = [l for l in block.splitlines() if "scheme_name:" in l]
            if name_lines:
                raw_name  = name_lines[0].split(":", 1)[-1].strip().strip('"')
                slug_name = slugify(raw_name) or f"scheme-{i+1}"
            else:
                slug_name = f"scheme-{i+1}"

            filename = f"{slug_name}-{date.today()}.md"
            folder   = f"knowledge-base/{category}"
            os.makedirs(folder, exist_ok=True)
            filepath = f"{folder}/{filename}"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(block)

            new_files.append(filepath)
            print(f"  Saved: {filepath}")

    save_json(HASHES_FILE, seen)
    print(f"\nFinished. {len(new_files)} new/updated file(s) created.")

if __name__ == "__main__":
    run()
