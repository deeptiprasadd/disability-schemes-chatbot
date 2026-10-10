"""
Directory lookup: actual organisations near the user, not just schemes.

The knowledge base explains schemes, so "which schools are best for my child
in my area?" used to get "no school list available". This module looks the
user's district / state up in knowledge-base/directory/centres.json (built by
scripts/fetch_directory.py from official National Trust and DEPwD lists) and
returns a block of real organisations for the prompt. When the place is
missing or unrecognised, the block tells the model to ask for the district,
suggesting close matches ("Daur" -> "Dhar", "Indore"?).
"""

import difflib
import json
import os
import re
from functools import lru_cache

DIRECTORY_FILE = "knowledge-base/directory/centres.json"
MAX_ORGS = 12

# Only questions about FINDING a place get the directory.
_PLACE_QUESTION_RE = re.compile(
    r"\b(schools?|centres?|centers?|ngos?|organi[sz]ations?|institutes?|day[\s-]?care|therapy|"
    r"admission|enrol\w*|near(by| me)?|where can|where do|address|contact|hostel|home for|"
    r"special educat\w*|residential|respite)\b"
    r"|स्कूल|विद्यालय|संस्था|केंद्र|केन्द्र|दाखिला|पास में",
    re.I,
)
# "I live in X region/district/city" — the place the user named, matched or not.
_NAMED_PLACE_RE = re.compile(
    r"\b(?:in|at|from|near)\s+(?:the\s+)?([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)(?:'s)?\s*(?:region|district|city|area|town|village)?",
)
_SCHEME_MEANING = {
    "Disha": "early intervention and school readiness, up to age 10",
    "Vikaas": "day care and skills, age 10+",
    "Samarth": "respite and residential care",
    "Gharaunda": "lifelong group home for adults",
    "Niramaya": "health insurance enrolment",
    "Badhte Kadam": "awareness programmes",
    "Sahyogi": "caregiver training",
}


@lru_cache(maxsize=1)
def _load() -> dict:
    if not os.path.exists(DIRECTORY_FILE):
        return {}
    with open(DIRECTORY_FILE, encoding="utf-8") as f:
        return json.load(f)


def _key(s: str) -> str:
    """'Jammu & Kashmir' == 'Jammu and Kashmir'."""
    return re.sub(r"[^a-z]", "", re.sub(r"\band\b|&", "", (s or "").lower()))


def _word_in(name: str, text: str) -> bool:
    return bool(name) and re.search(rf"\b{re.escape(name)}\b", text, re.I) is not None


def find_place(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """([(state, district)...] named in text, [states named in text])."""
    orgs = _load().get("national_trust_registered_organisations", [])
    districts = sorted({(o["state"], o["district"]) for o in orgs if o["district"]})
    states = sorted({o["state"] for o in orgs if o["state"]})
    hit_d = [(s, d) for s, d in districts if len(d) > 2 and _word_in(d, text)]
    hit_s = [s for s in states if _word_in(s, text)]
    return hit_d, hit_s


def _suggest(text: str) -> list[str]:
    """Close district names for a place the user named that we do not know."""
    orgs = _load().get("national_trust_registered_organisations", [])
    names = {o["district"]: o["state"] for o in orgs if o["district"]}
    out = []
    for m in _NAMED_PLACE_RE.finditer(text):
        word = m.group(1).split("'")[0]
        for d in difflib.get_close_matches(word.title(), list(names), n=3, cutoff=0.6):
            label = f"{d} ({names[d]})"
            if label not in out:
                out.append(label)
    return out[:4]


def _org_line(i: int, o: dict) -> str:
    runs = ", ".join(f"{s} ({_SCHEME_MEANING[s]})" if s in _SCHEME_MEANING else s for s in o["schemes"])
    return (f"{i}. {o['name']} — {o['address'] or 'address not listed'} — contact: "
            f"{o['contact'] or 'not listed'} — runs: {runs or 'not listed'} — {o['district']}, {o['state']}")


FOUND_TASK = (
    "THE USER WANTS ACTUAL SCHOOLS / CENTRES NEAR THEM, and the OFFICIAL DIRECTORY below lists them. "
    "START your answer with that list: every organisation, each with its address, contact and what it "
    "runs, exactly as given. Then add at most 5 short bullets: that government schools must admit the "
    "child under Samagra Shiksha (if the material says so), the government regional centre if listed, and "
    "to call to confirm admission for the child's age and disability. Do NOT repeat a scheme overview "
    "already given earlier in the conversation.\n\n"
)
ASK_TASK = (
    "THE USER WANTS ACTUAL SCHOOLS / CENTRES NEAR THEM, but their district is not known. Answer what you "
    "can from the material, then END by asking which district and state they live in (mention the close "
    "matches from the OFFICIAL DIRECTORY note, if any) so you can list real organisations there.\n\n"
)


def directory_block(question: str, user_text: str = "", last_user_turn: str = "") -> tuple[str, set[str], str]:
    """
    (prompt block, official URLs it contains, task instruction) for a question
    about finding a school or centre; ("", set(), "") otherwise. The task
    instruction goes at the TOP of the prompt: buried after the retrieved
    scheme chunks, the list was sometimes ignored. `last_user_turn` keeps the
    context when the user answers "which district?" with just "Indore".
    """
    data = _load()
    if not data or not (_PLACE_QUESTION_RE.search(question) or _PLACE_QUESTION_RE.search(last_user_turn)):
        return "", set(), ""
    text = f"{question}\n{user_text}"
    orgs = data.get("national_trust_registered_organisations", [])
    hit_d, hit_s = find_place(text)
    urls: set[str] = set()

    lines = ["\n---\nOFFICIAL DIRECTORY (National Trust registered organisations, from "
             f"{data['sources']['national_trust_registered_organisations']}; fetched {data['fetched']}). "
             "These organisations work with autism, cerebral palsy, intellectual disability and multiple "
             "disabilities; many run special schools, early intervention and day care."]
    if hit_d:
        picked = [o for o in orgs if (o["state"], o["district"]) in set(hit_d)]
        lines.append(f"Organisations in {', '.join(d for _, d in hit_d)}:")
    elif hit_s:
        picked = [o for o in orgs if o["state"] in hit_s]
        covered = sorted({o["district"] for o in picked})
        lines.append(f"The user named the state ({', '.join(hit_s)}) but no district. Districts with "
                     f"listed organisations: {', '.join(covered)}. Some organisations in the state:")
    else:
        picked = []
        hint = _suggest(text)
        lines.append(
            "THE USER'S DISTRICT IS NOT KNOWN or not in the directory. Ask which DISTRICT and STATE they "
            "live in, so you can list real schools and centres there."
            + (f" Close matches to the place they named: {', '.join(hint)}. Ask if they meant one of these."
               if hint else "")
        )
    lines += [_org_line(i, o) for i, o in enumerate(picked[:MAX_ORGS], 1)]
    if len(picked) > MAX_ORGS:
        lines.append(f"(+{len(picked) - MAX_ORGS} more in the official list)")

    # Regional centres serve every disability type, so they help any family.
    named_states = {_key(s) for s in hit_s} | {_key(s) for s, _ in hit_d}
    crcs = [c for c in data.get("composite_regional_centres", [])
            if c["state"] and _key(c["state"]) in named_states]
    if crcs:
        lines.append("Government Composite Regional Centre(s) in this state (all disability types): "
                     + "; ".join(f"{c['name']} {c['website']}" for c in crcs))
        urls |= {c["website"] for c in crcs if c["website"]}

    lines.append(
        "RULES FOR THIS DIRECTORY: name ONLY organisations listed above, with their address and contact "
        "exactly as given. Never invent a school. Tell the parent to call and confirm admission for their "
        "child's age and disability. Also explain that under Samagra Shiksha every government school must "
        "admit the child, with a special educator's support, if the reference material says so."
    )
    return "\n".join(lines) + "\n", urls, (FOUND_TASK if picked else ASK_TASK)
