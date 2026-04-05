import requests
from bs4 import BeautifulSoup
import hashlib, os, json
from datetime import date
from openai import OpenAI

client = OpenAI()  # uses OPENAI_API_KEY from env

SOURCES = [
    {"url": "https://depwd.gov.in/en/schemes/", "category": "central-schemes"},
    {"url": "https://scholarships.gov.in/All-Scholarships", "category": "central-schemes"},
    {"url": "https://swavlambancard.gov.in", "category": "eligibility"},
]

SEEN_HASHES_FILE = "scripts/seen_hashes.json"

def load_seen_hashes():
    if os.path.exists(SEEN_HASHES_FILE):
        return json.load(open(SEEN_HASHES_FILE))
    return {}

def save_seen_hashes(hashes):
    json.dump(hashes, open(SEEN_HASHES_FILE, "w"), indent=2)

def scrape_page(url):
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    # Remove nav, footer, scripts
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

def content_to_md(raw_text, url, category):
    """Use GPT-4o-mini to convert raw scraped text into structured .md"""
    prompt = f"""
You are a government scheme document formatter for India's disability welfare portal.

Convert the following raw scraped text from {url} into a clean Markdown file.
Use EXACTLY this structure:

---
scheme_name: "<name>"
ministry: "<ministry name>"
category: "{category}"
disability_types: ["<type1>", "<type2>"]
last_updated: "{date.today()}"
source_url: "{url}"
---

## Overview
(2-3 sentences)

## Benefits
(bullet points)

## Eligibility criteria
(bullet points)

## Required documents
(numbered list)

## How to apply
(steps)

## Contact
(phone, email if available)

If the page contains multiple schemes, create one section per scheme separated by ---

Raw text:
{raw_text[:4000]}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

def slug(text):
    return text.lower().replace(" ", "-").replace("/", "-")[:50]

def run():
    seen = load_seen_hashes()
    new_files = []

    for source in SOURCES:
        print(f"Scraping: {source['url']}")
        try:
            raw = scrape_page(source["url"])
        except Exception as e:
            print(f"  Failed: {e}")
            continue

        content_hash = hashlib.md5(raw.encode()).hexdigest()

        # Skip if nothing changed since last run
        if seen.get(source["url"]) == content_hash:
            print(f"  No changes detected, skipping.")
            continue

        seen[source["url"]] = content_hash

        # Convert to markdown using LLM
        md_content = content_to_md(raw, source["url"], source["category"])

        # Save file
        filename = f"{slug(source['url'].split('/')[-2] or 'scheme')}-{date.today()}.md"
        filepath = f"{source['category']}/{filename}"
        os.makedirs(source["category"], exist_ok=True)

        with open(filepath, "w") as f:
            f.write(md_content)

        new_files.append(filepath)
        print(f"  Saved: {filepath}")

    save_seen_hashes(seen)
    print(f"\nDone. {len(new_files)} new/updated files.")

if __name__ == "__main__":
    run()
