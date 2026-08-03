"""
Link verification and hallucination prevention.

The assistant used to let the LLM recall URLs from its own training data, which
is exactly how it ends up citing dead or invented links. This module makes that
impossible for the routes that can present a link: candidate URLs are pulled
ONLY from retrieved knowledge-base documents (their `source_url` frontmatter
plus any URL in the body) or a live web search, each is verified reachable, and
only verified URLs are ever allowed into the prompt or the final answer.

Verification nuance (learned from this project's own scraper): many legitimate
.gov.in / .nic.in sites reject HEAD requests or bot-like traffic with a 403/405,
or simply time out under load — that is NOT the same as the link being dead.
Only a DNS resolution failure (the domain does not exist) or an explicit 404 is
treated as definitively broken. Everything else ambiguous is surfaced as
"unconfirmed" rather than silently dropped or silently trusted.
"""

from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SchemeBot/1.0)"}
TIMEOUT = 5
CACHE_TTL = 6 * 3600  # seconds

# Domains we trust as "official" without further judgement.
_OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".gov", ".ac.in")
_OFFICIAL_KEYWORDS = ("myscheme.gov.in", "swavlambancard.gov.in", "nsp.gov.in")

# Stops before markdown emphasis/code markers (*, `, |) so "**url**" or "`url`"
# doesn't get swallowed into the match — otherwise a verified URL the model
# wraps in bold fails an exact-string match and gets wrongly stripped.
_URL_RE = re.compile(r"https?://[^\s\)\]\"'<>*`|]+")

# status: "OK" | "NOT_FOUND" | "DNS_ERROR" | "UNCONFIRMED" | "ERROR"
_cache: dict[str, tuple[float, dict]] = {}


def is_official_domain(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host.endswith(_OFFICIAL_SUFFIXES) or any(k in host for k in _OFFICIAL_KEYWORDS)


def extract_urls(text: str) -> list[str]:
    """Find URLs in raw text (frontmatter, markdown body, or a generated answer)."""
    if not text:
        return []
    out, seen = [], set()
    for m in _URL_RE.findall(text):
        url = m.rstrip(".,;:!?)]}’”")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _verify_one(url: str) -> dict:
    """Reachability check for a single URL, with a small process-local cache."""
    now = time.time()
    cached = _cache.get(url)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]

    result = {"url": url, "status": "ERROR", "official": is_official_domain(url)}
    try:
        r = requests.head(url, timeout=TIMEOUT, headers=HEADERS,
                          allow_redirects=True, verify=False)
        # Some gov sites reject HEAD (405/403) but serve GET fine — confirm before
        # judging them, rather than trusting the HEAD response for those codes.
        if r.status_code in (403, 405) or r.status_code >= 500:
            r = requests.get(url, timeout=TIMEOUT + 3, headers=HEADERS,
                             allow_redirects=True, verify=False, stream=True)
            r.close()

        if r.status_code < 400:
            result["status"] = "OK"
        elif r.status_code == 404:
            result["status"] = "NOT_FOUND"          # page removed -> definitively broken
        else:
            result["status"] = "UNCONFIRMED"        # 403/5xx after retry -> ambiguous
    except requests.exceptions.ConnectionError as e:
        # NameResolutionError text means the domain itself doesn't exist.
        result["status"] = "DNS_ERROR" if "NameResolutionError" in str(e) else "UNCONFIRMED"
    except requests.exceptions.Timeout:
        result["status"] = "UNCONFIRMED"            # server slow/blocking, not necessarily dead
    except Exception:
        result["status"] = "ERROR"

    _cache[url] = (now, result)
    return result


def verify_urls(urls: list[str], max_urls: int = 4) -> list[dict]:
    """Verify up to `max_urls` candidates in parallel."""
    urls = urls[:max_urls]
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        futures = [pool.submit(_verify_one, u) for u in urls]
        return [f.result() for f in as_completed(futures)]


# --------------------------------------------------------------- web search fallback

def web_search_official(query: str, max_results: int = 3) -> list[str]:
    """
    Live web search for an official source, used only when nothing verified was
    found in the knowledge base. Requires TAVILY_API_KEY (https://tavily.com,
    free tier available); returns [] gracefully if not configured so the caller
    can tell the user honestly instead of guessing.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": f"{query} official government website India",
                "max_results": max_results,
                "include_domains": [],
            },
            timeout=8,
        )
        resp.raise_for_status()
        return [r["url"] for r in resp.json().get("results", []) if r.get("url")]
    except Exception as e:
        print(f"[link_utils] web search failed: {e}")
        return []


# --------------------------------------------------------------- orchestration

_file_cache: dict[str, str] = {}


def _read_source_file(path: str) -> str:
    """Cached read of a knowledge-base file (small Markdown docs, cheap to keep)."""
    if path not in _file_cache:
        try:
            with open(path, encoding="utf-8") as f:
                _file_cache[path] = f.read()
        except OSError:
            _file_cache[path] = ""
    return _file_cache[path]


def extract_candidates_from_docs(docs) -> list[str]:
    """
    Pull every URL associated with the retrieved documents.

    Retrieval returns a ~500-char CHUNK of a scheme file, and the chunk that
    matches the query semantically is often not the one containing the
    `source_url:` frontmatter line (the splitter puts frontmatter in its own
    chunk). So this reads each doc's full source file — via metadata["source"],
    the path the vector store already carries — rather than trusting only the
    retrieved slice, which is what let scheme lookups silently miss a perfectly
    valid, already-scraped official URL.
    """
    urls, seen = [], set()
    for doc in docs or []:
        text = getattr(doc, "page_content", "")
        path = getattr(doc, "metadata", {}).get("source")
        if path:
            text += "\n" + _read_source_file(path)
        for url in extract_urls(text):
            if url not in seen:
                seen.add(url)
                urls.append(url)
    # Official domains first — they're the ones we want to prefer and surface.
    urls.sort(key=lambda u: not is_official_domain(u))
    return urls


def find_verified_links(question: str, docs, exclude: set[str] | None = None,
                        allow_web_search: bool = False) -> dict:
    """
    Resolve the set of links safe to mention in an answer.

    Returns {"verified": [...], "note": str} where `verified` is a list of
    {url, status, official} dicts with status == "OK", and `note` explains what
    happened when nothing could be verified (so the model — and the user — get
    an honest answer instead of silence or a guess).
    """
    exclude = exclude or set()
    candidates = [u for u in extract_candidates_from_docs(docs) if u not in exclude]
    checked = verify_urls(candidates)
    verified = [r for r in checked if r["status"] == "OK"]

    if not verified and allow_web_search:
        found = [u for u in web_search_official(question) if u not in exclude]
        checked += verify_urls(found)
        verified = [r for r in checked if r["status"] == "OK"]

    if verified:
        return {"verified": verified, "note": ""}

    dead = [r for r in checked if r["status"] in ("NOT_FOUND", "DNS_ERROR")]
    unconfirmed = [r for r in checked if r["status"] == "UNCONFIRMED"]
    if dead:
        note = "The stored link appears to be obsolete or incorrect (page not found / domain unreachable)."
    elif unconfirmed:
        note = ("A candidate official link exists but could not be confirmed reachable right now "
                "(the server may be blocking automated checks or is temporarily down) — this may be "
                "a temporary issue rather than a dead link.")
    else:
        note = "No link was found in the knowledge base or web search for this request."
    return {"verified": [], "note": note}


def format_verified_block(result: dict) -> str:
    """Render find_verified_links()'s result as the prompt's VERIFIED LINKS section."""
    if result["verified"]:
        lines = [
            f"- {r['url']}" + ("  (official government domain)" if r["official"] else "")
            for r in result["verified"]
        ]
        return "VERIFIED LINKS (the ONLY URLs you may use in your answer):\n" + "\n".join(lines)
    return (
        "VERIFIED LINKS: none available. " + result["note"] + "\n"
        "Do NOT output any URL. Instead name the official ministry/portal by name and tell the "
        "user to search for it, or that you could not confirm a working link right now."
    )


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def sanitize_answer_links(answer: str, verified_urls: set[str]) -> str:
    """
    Deterministic backstop: strip any URL the LLM produced anyway that is not in
    the verified set. Small models don't always follow instructions perfectly,
    so generation alone cannot be trusted to never invent a link.
    """
    def _is_verified(url: str) -> bool:
        return url.rstrip(".,;:!?)]}’”") in verified_urls

    # Markdown links first: an unverified [text](url) becomes plain text rather
    # than a link pointing at a placeholder string, which would render as a
    # broken/confusing hyperlink instead of just... text.
    def _replace_md(match: re.Match) -> str:
        text, url = match.group(1), match.group(2)
        return match.group(0) if _is_verified(url) else text

    answer = _MD_LINK_RE.sub(_replace_md, answer)

    # Then any remaining bare URL.
    def _replace_bare(match: re.Match) -> str:
        return match.group(0) if _is_verified(match.group(0)) else "[link unavailable — could not be verified]"

    return _URL_RE.sub(_replace_bare, answer)
