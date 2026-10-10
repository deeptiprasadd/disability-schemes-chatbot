"""
Helpers that read a scheme's own section of a knowledge-base file.

Files can hold several schemes, each starting with front matter that names it
(`scheme_name: "..."`). Retrieval returns ~500-character chunks, so a chunk with
a scheme's benefit often arrives without that scheme's eligibility rules — and
the model then borrowed rules from another scheme (it gave the Delhi pension,
open to ages 0-60, the UP pension's "above 18" rule). `scheme_rules_block()`
puts each retrieved scheme's complete Benefits and Eligibility next to the
chunks, so the model never has to guess them.
"""

import re

from chatbot.link_utils import _read_source_file

_KEY_SECTION_RE = re.compile(r"benefit|eligib|criteri|who can", re.I)
MAX_SCHEMES = 6
SECTION_CHARS = 700


def _name_key(name: str) -> str:
    return re.sub(r"[\W_]+", "", (name or "").lower())


def scheme_block(path: str, name: str) -> str:
    """The part of `path` that belongs to the scheme called `name` ("" if not found)."""
    text = _read_source_file(path)
    starts = [(m.start(), m.group(1)) for m in
              re.finditer(r'^scheme_name:\s*"?(.+?)"?\s*$', text, re.M)]
    for i, (pos, found) in enumerate(starts):
        if _name_key(found) == _name_key(name):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
            return text[pos:end]
    return ""


def key_sections(block: str) -> str:
    """Only the Benefits and Eligibility sections of a scheme block."""
    heads = list(re.finditer(r"^#{1,4}\s+(.*)$", block, re.M))
    picked = []
    for i, h in enumerate(heads):
        if _KEY_SECTION_RE.search(h.group(1)):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(block)
            picked.append(block[h.start():end].strip())
    return re.sub(r"\n{2,}", "\n", "\n".join(picked)).strip()[:SECTION_CHARS]


def scheme_rules_block(docs) -> str:
    """Complete Benefits + Eligibility for each scheme the retrieved chunks came from."""
    seen, parts = set(), []
    for d in docs:
        name, path = d.metadata.get("scheme_name"), d.metadata.get("source")
        key = _name_key(name)
        if not name or not path or key in seen:
            continue  # dated re-scrapes of one scheme count once
        seen.add(key)
        sections = key_sections(scheme_block(path, name))
        if sections:
            parts.append(f"[Scheme: {name}] COMPLETE benefits and eligibility:\n{sections}")
        if len(parts) >= MAX_SCHEMES:
            break
    if not parts:
        return ""
    return ("\n---\nFULL RULES of each scheme above (use these, not guesses, for "
            "eligibility and amounts):\n" + "\n---\n".join(parts) + "\n")


# Sections the model writes even when told to skip them: "### Day care" followed
# only by "No information available in the provided material."
_EMPTY_LINE_RE = re.compile(
    r"no (specific |further |relevant )?(information|details|data|guidance)"
    r"|not (mentioned|available|provided|specified|covered)"
    r"|nothing (is )?(mentioned|listed)|जानकारी (उपलब्ध )?नहीं|उपलब्ध नहीं|उल्लेख नहीं|स्पष्ट नहीं"
    r"|koi jaankari nahi|jankari nahi|zikr nahi",
    re.I,
)
# A Markdown heading, or a line that is entirely bold (models use both as headings).
_HEADING_RE = re.compile(r"^\s*(#{2,6}\s+\S|\*\*[^*]+\*\*:?\s*$)")
_BOLD_HEADING_RE = re.compile(r"^\s*\*\*[^*]+\*\*:?\s*$")


def _says_only_no_info(line: str) -> bool:
    """
    True when the "no information" phrase IS the content: the whole line
    ("No information available.") or right after a label ("Day care – not in
    the source"). A line with real facts that merely contains such a phrase
    ("Rs 2500 per month; not mentioned for other states") is kept.
    """
    text = re.sub(r"^[\s>*_\-•\d.)]+", "", line).replace("*", "").strip()
    if not text or len(text) > 160:
        return False
    head = r"^(?:\S+\s+){0,3}?"                       # up to 3 words before the phrase
    if re.search(head + f"(?:{_EMPTY_LINE_RE.pattern})", text, re.I):
        return True
    after_label = re.search(r"^[^.;]{1,90}?\s[–—:-]\s*(.*)$", text)
    return bool(after_label and re.search(head + f"(?:{_EMPTY_LINE_RE.pattern})", after_label.group(1), re.I))


def drop_empty_sections(answer: str) -> str:
    """Remove lines that only say "no information", then headings left with nothing under them."""
    lines = [l for l in answer.splitlines() if _HEADING_RE.match(l) or not _says_only_no_info(l)]
    out, i = [], 0
    while i < len(lines):
        if _HEADING_RE.match(lines[i]):
            bold = bool(_BOLD_HEADING_RE.match(lines[i]))
            j = i + 1
            while (j < len(lines) and not _HEADING_RE.match(lines[j]) and lines[j].strip() != "---"
                   and not (bold and not lines[j].strip() and j > i + 1)):
                j += 1  # a bold-line "heading" owns only the block right under it
            if not any(l.strip() for l in lines[i + 1:j]):
                i = j  # heading with an empty body
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)
