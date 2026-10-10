"""
Build the directory of places that serve children and adults with disabilities.

The knowledge base describes SCHEMES; it cannot answer "which school or centre
near me?". This script collects official lists of actual organisations into
knowledge-base/directory/centres.json, which chatbot/directory.py looks up by
district and state:

  * National Trust Registered Organisations (~450): district-level NGOs running
    special schools, early intervention (Disha), day care (Vikaas), respite and
    residential care, for autism, cerebral palsy, intellectual disability and
    multiple disabilities.
  * DEPwD National Institutes and Composite Regional Centres: national and
    regional centres for every disability type.

Run from the project root:  python scripts/fetch_directory.py
"""

import json
import os
import re
import sys
import time
from datetime import date

import requests
import urllib3
from bs4 import BeautifulSoup

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUT_FILE = "knowledge-base/directory/centres.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SchemeBot/1.0)"}
NT_LIST = "https://thenationaltrust.gov.in/content/registered_organization.php"
DEPWD_NI = "https://depwd.gov.in/en/national-institutes/"
PAGE_SIZE = 10
DELAY_SECONDS = 1.0   # be gentle with government servers


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=60, verify=False)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def unmask_email(text):
    """'name[at]site[dot]com' -> 'name@site.com' (how gov sites publish emails)."""
    return re.sub(r"\s*\[dot\]\s*", ".", re.sub(r"\s*\[at\]\s*", "@", text))


def fetch_national_trust():
    orgs, start, seen = [], 0, set()
    while True:
        soup = get(f"{NT_LIST}?start={start}")
        table = soup.find("table")
        rows = table.find_all("tr")[1:] if table else []
        page = []
        for tr in rows:
            cells = tr.find_all("td")
            if len(cells) < 6:
                continue
            serial = clean(cells[0].get_text())
            if serial in seen:
                continue
            seen.add(serial)
            ngo = [clean(s) for s in cells[3].stripped_strings]
            contact = clean(unmask_email(cells[4].get_text(" ")))
            page.append({
                "state": clean(cells[1].get_text()),
                "district": clean(cells[2].get_text()),
                "name": ngo[0] if ngo else "",
                "address": clean(" ".join(ngo[1:])),
                "contact": contact,
                "schemes": [s.strip() for s in re.split(r",|(?<=[a-z])(?=[A-Z])", clean(cells[5].get_text())) if s.strip()],
            })
        orgs.extend(page)
        print(f"  National Trust: {len(orgs)} organisations so far", flush=True)
        # Past the end the site keeps returning the LAST page instead of an
        # empty one, so stop on a short page or one with no new rows.
        if len(page) < PAGE_SIZE:
            break
        start += PAGE_SIZE
        time.sleep(DELAY_SECONDS)
    return orgs


# DEPwD writes CRC states inconsistently ("A.P.", "Chattisgarh", or not at all),
# so normalise them to the state names the National Trust list uses.
_STATE_FIXES = {"A.P.": "Andhra Pradesh", "H.P.": "Himachal Pradesh", "U.P.": "Uttar Pradesh",
                "J&K": "Jammu and Kashmir", "Chattisgarh": "Chhattisgarh"}
_CITY_STATE = {"Manipur": "Manipur", "Shillong": "Meghalaya", "Jaipur": "Rajasthan",
               "Bhopal": "Madhya Pradesh", "Chhatarpur": "Madhya Pradesh", "Jammu": "Jammu and Kashmir",
               "Sikkim": "Sikkim", "Andaman & Nicobar Islands": "Andaman and Nicobar Islands",
               "Madurai": "Tamil Nadu"}


def normalize_crc(c):
    c["city"] = c["city"].rstrip(", ").strip()
    c["state"] = _STATE_FIXES.get(c["state"], c["state"]) or _CITY_STATE.get(c["city"], "")
    return c


def fetch_depwd_centres():
    soup = get(DEPWD_NI)
    tables = soup.find_all("table")
    institutes, crcs = [], []
    for tr in tables[0].find_all("tr")[1:]:
        c = [clean(td.get_text(" ")) for td in tr.find_all("td")]
        if len(c) >= 3:
            site = re.search(r"https?://\S+", c[2])
            institutes.append({
                "name": c[1],
                "address": clean(re.sub(r"https?://\S+", "", c[2])),
                "website": site.group(0).rstrip(".,") if site else "",
            })
    for tr in tables[1].find_all("tr")[1:]:
        c = [clean(td.get_text(" ")) for td in tr.find_all("td")]
        if len(c) >= 2:
            site = next((x for x in c if x.startswith("http")), "")
            place = re.match(r"CRC,?\s*([^()]+?)\s*(?:\(([^)]+)\))?$", c[1])
            crcs.append(normalize_crc({
                "name": c[1],
                "city": place.group(1).strip() if place else "",
                "state": (place.group(2) or "").strip() if place else "",
                "website": site,
            }))
    return institutes, crcs


def run():
    print("Fetching National Trust registered organisations...")
    orgs = fetch_national_trust()
    print("Fetching DEPwD National Institutes and Composite Regional Centres...")
    institutes, crcs = fetch_depwd_centres()
    data = {
        "fetched": str(date.today()),
        "sources": {
            "national_trust_registered_organisations": NT_LIST,
            "depwd_national_institutes_and_crcs": DEPWD_NI,
        },
        "national_trust_registered_organisations": orgs,
        "national_institutes": institutes,
        "composite_regional_centres": crcs,
    }
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print(f"Saved {len(orgs)} organisations, {len(institutes)} institutes, "
          f"{len(crcs)} regional centres to {OUT_FILE}")


if __name__ == "__main__":
    run()
