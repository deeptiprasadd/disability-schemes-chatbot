"""
Profile extraction + scheme matching for the "Matched schemes" panel.

After each answer the UI calls /api/insights, which returns:
  * profile — facts the USER has stated (state, age, disability, income, ...)
  * schemes — knowledge-base schemes checked against that profile, each marked
              eligible / check / not_eligible with a short reason

Grounding: scheme names and source URLs come from the knowledge-base front
matter, never from the LLM. The model only chooses which retrieved schemes are
relevant and judges eligibility against their official text, so the panel
cannot invent a scheme or a link.
"""

import json
import os
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from chatbot.language_utils import NATIVE_NAMES, language_name
from chatbot.link_utils import _read_source_file
from chatbot.rag_pipeline import load_pipeline, make_llm

PROFILE_FIELDS = {  # JSON key -> label shown in the UI
    "state": "State",
    "age": "Age",
    "disability": "Disability",
    "disability_percent": "Disability %",
    "income": "Family income",
    "occupation": "Occupation",
}
STATUS_ORDER = {"eligible": 0, "check": 1, "not_eligible": 2}
MAX_CANDIDATES = 6     # schemes shown to the LLM (keeps us inside Groq's TPM limit)
MAX_SCHEMES = 4        # schemes returned to the UI
EXCERPT_CHARS = 1000

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
_SECTION_RE = re.compile(r"^#{1,4}\s+(.*)$", re.M)
_KEY_SECTION_RE = re.compile(r"benefit|eligib|criteri|amount|assistance|who can", re.I)
_CONTACT_RE = re.compile(r"^#{1,4}\s*contact.*?(?=^#{1,4}\s|\Z)", re.S | re.M | re.I)


# --------------------------------------------------------------- knowledge base

def _name_key(name: str) -> str:
    """Match key for scheme names: "Pre-Matric Scholarship" == "Pre Matric scholarship"."""
    return re.sub(r"[\W_]+", "", name.lower())


def scheme_meta(path: str) -> dict:
    """{name, url, updated} from a knowledge-base file's front matter."""
    meta = {"name": os.path.splitext(os.path.basename(path))[0], "url": "", "updated": ""}
    m = _FRONTMATTER_RE.match(_read_source_file(path))
    if not m:
        return meta
    for line in m.group(1).splitlines():
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip().strip("\"'")
        if key == "scheme_name" and val:
            meta["name"] = val
        elif key == "source_url":
            meta["url"] = val
        elif key == "last_updated":
            meta["updated"] = val
    return meta


def _excerpt(path: str) -> str:
    """
    The parts of a scheme file that decide eligibility: Benefits and
    Eligibility sections first (they are what the matcher reasons over),
    falling back to the top of the document.
    """
    body = _FRONTMATTER_RE.sub("", _read_source_file(path), count=1)
    body = _CONTACT_RE.sub("", body)
    heads = list(_SECTION_RE.finditer(body))
    picked = []
    for i, h in enumerate(heads):
        if _KEY_SECTION_RE.search(h.group(1)):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
            picked.append(body[h.start():end].strip())
    text = "\n".join(picked) or body
    return re.sub(r"\n{2,}", "\n", text).strip()[:EXCERPT_CHARS]


def _candidates(query: str) -> list[dict]:
    """Distinct schemes for a query, best match first; dated re-scrapes collapse into one."""
    docs = load_pipeline()["retriever_broad"].invoke(query)
    by_name: dict[str, dict] = {}
    for d in docs:
        path = d.metadata.get("source", "")
        if not path:
            continue
        meta = scheme_meta(path)
        key = _name_key(meta["name"])
        best = by_name.get(key)
        if best is None or meta["updated"] > best["updated"]:
            # Keep the rank of the first hit, but the newest file's content.
            by_name[key] = {**meta, "path": path, "rank": best["rank"] if best else len(by_name)}
    ranked = sorted(by_name.values(), key=lambda c: c["rank"])[:MAX_CANDIDATES]
    for c in ranked:
        c["text"] = _excerpt(c["path"])
    return ranked


def source_links(paths) -> list[dict]:
    """De-duplicated [{name, url}] for a list of knowledge-base file paths."""
    out, seen = [], set()
    for p in paths:
        meta = scheme_meta(p)
        key = _name_key(meta["name"])
        if key not in seen:
            seen.add(key)
            out.append({"name": meta["name"], "url": meta["url"]})
    return out


# --------------------------------------------------------------- LLM matching

INSIGHTS_PROMPT = """You check which Indian government disability schemes fit a user.

What the user has said, in their own words:
{user_turns}

Candidate schemes (official text excerpts):
{schemes}

Return ONLY a JSON object, no other text, in exactly this shape:
{{"profile": {{"state": null, "age": null, "disability": null, "disability_percent": null, "income": null, "occupation": null}},
 "schemes": [{{"id": 1, "benefit": "...", "status": "eligible", "reason": "..."}}]}}

Rules for "profile":
- Fill a field ONLY with something the user explicitly said. Otherwise null. Never guess.
- Keep values short, e.g. "Delhi", "34", "Locomotor", "60%", "Under Rs 75,000 a year", "Student".
- "age": a number if given; if the user only makes the age group clear (e.g. "my kid", "my son"), use "Child".

Rules for "schemes":
- Include at most 4 candidates that give the KIND of help the user is asking for
  (a pension question -> monthly allowances; a study question -> scholarships). Leave out the rest.
- "id" is the candidate's number above.
- "benefit": the main benefit in at most 8 words, taken from the excerpt. Never invent amounts.
- "status": "eligible" if the user meets every criterion the excerpt states,
  "not_eligible" if the user clearly fails a criterion,
  "check" if a criterion depends on something the user has not said.
- "reason": at most 10 words naming the deciding criterion, e.g. "Needs 80% or more disability".
- Write "benefit" and "reason" in {language}. Keep amounts and percentages as written.
- Best fit first.
"""

_llm = None


def _parse_json(raw: str) -> dict:
    """First {...} block in the model output, or {} — small models add chatter."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def build_insights(question: str, history: list, lang: str = "en") -> dict:
    """
    Profile + matched schemes for the conversation so far.
    Returns empty lists on any failure so the panel simply keeps its last state.
    """
    global _llm
    empty = {"profile": [], "schemes": []}
    user_turns = [m["content"] for m in history if m.get("role") == "user"][-5:]
    user_turns.append(question)
    try:
        # Retrieval query: the latest question plus recent user context, so a
        # follow-up like "what documents?" still finds this user's schemes.
        cands = _candidates(" ".join(user_turns[-3:])[-500:])
        if _llm is None:
            _llm = make_llm(temperature=0)
        chain = PromptTemplate.from_template(INSIGHTS_PROMPT) | _llm | StrOutputParser()
        raw = chain.invoke({
            "user_turns": "\n".join(f"- {t[:400]}" for t in user_turns),
            "schemes": "\n\n".join(
                f"[{i}] {c['name']}\n{c['text']}" for i, c in enumerate(cands, 1)
            ) or "(none)",
            "language": f"{language_name(lang)} ({NATIVE_NAMES.get(lang, 'English')})",
        })
    except Exception as e:
        print(f"[insights] failed: {e}")
        return empty

    data = _parse_json(raw)
    stated = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    profile = []
    for key, label in PROFILE_FIELDS.items():
        val = stated.get(key)
        if val is not None and str(val).strip().lower() not in ("", "null", "none", "unknown", "n/a"):
            profile.append({"key": key, "label": label, "value": str(val).strip()[:40]})

    schemes, used = [], set()
    for item in data.get("schemes") or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("id")) - 1
        except (TypeError, ValueError):
            continue
        if not 0 <= idx < len(cands) or idx in used:
            continue
        used.add(idx)
        status = item.get("status") if item.get("status") in STATUS_ORDER else "check"
        schemes.append({
            "name": cands[idx]["name"],
            "url": cands[idx]["url"],
            "benefit": str(item.get("benefit") or "").strip()[:80],
            "status": status,
            "reason": str(item.get("reason") or "").strip()[:100],
        })
        if len(schemes) >= MAX_SCHEMES:
            break
    schemes.sort(key=lambda s: STATUS_ORDER[s["status"]])  # stable: keeps fit order within a status
    return {"profile": profile, "schemes": schemes}
