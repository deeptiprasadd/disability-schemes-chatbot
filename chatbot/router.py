"""
Intent classification and routing.

The original pipeline treated EVERY message as a document-retrieval task: it
always retrieved, always injected the full conversation, and always aimed for
the same sectioned scheme layout. That is why a request like

    "give me the application form link, and if I have to write an application,
     write it in proper format"

came back as yet another copy of the scheme summary — there was no notion of
"writing a document" as a distinct kind of work, and the retrieved scheme text
crowded out the actual request.

This module classifies each incoming message and returns a `Route` describing:
  * whether retrieval is needed at all,
  * how much conversation history is relevant,
  * and the task-specific instruction the generator should follow.

Classification is LLM-based (a small, fast, near-zero-token call) because
composite requests need judgement, with a deterministic regex fast path for the
unambiguous cases and as a fallback if the model call fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate


class Intent(str, Enum):
    SCHEME_LOOKUP = "SCHEME_LOOKUP"    # which schemes/benefits apply (a few, in depth)
    LIST_ALL = "LIST_ALL"              # enumerate every relevant scheme, not just the top few
    COMPARE = "COMPARE"                # compare schemes and/or recommend the best one
    ELIGIBILITY = "ELIGIBILITY"        # does this person qualify
    RESOURCE_LINK = "RESOURCE_LINK"    # a link, portal, form, download
    WRITE_DOCUMENT = "WRITE_DOCUMENT"  # write an application / letter / email
    STEPS = "STEPS"                    # the application procedure, step by step
    EXPLAIN = "EXPLAIN"                # how does X work, how to fill a form
    SUMMARIZE = "SUMMARIZE"            # recap the conversation
    SMALL_TALK = "SMALL_TALK"          # greeting / thanks
    GENERAL = "GENERAL"                # anything else; answer from reasoning


# "facts" keeps user turns in full but clips past answers, so the model can use
# what the user told it without being handed its own previous reply to copy.
HistoryMode = str  # "none" | "facts" | "full"

# "narrow" = the default retriever (fewer, tightly-reranked chunks) — right for a
# single scheme in depth. "broad" = a much wider retriever for requests that must
# see MANY distinct schemes at once (list-all, compare) — see rag_pipeline.py,
# where FlashrankRerank's default top_n=3 was silently capping every answer,
# including "list all schemes", to three chunks regardless of what was asked.
RetrievalDepth = str  # "narrow" | "broad"


@dataclass(frozen=True)
class Route:
    intent: Intent
    needs_retrieval: bool
    history_mode: HistoryMode
    instruction: str
    retrieval_depth: RetrievalDepth = "narrow"


# --------------------------------------------------------------------------- routes
_WRITE_INSTRUCTION = (
    "The user asked you to WRITE a document (an application, letter, email or "
    "filled format).\n"
    "- OUTPUT THE COMPLETE DOCUMENT ITSELF, ready to copy and send.\n"
    "- Use a proper layout: To / The <authority>, Subject, Respected Sir-Madam, "
    "body paragraphs, Yours faithfully, Name, Address, Date, and an Enclosures "
    "list where relevant.\n"
    "- Put clearly-marked placeholders like [Full Name], [Address], [UDID Number] "
    "wherever you do not know a detail. NEVER invent personal details.\n"
    "- Use the retrieved context ONLY to get names right (the scheme, the issuing "
    "authority, the portal). DO NOT describe the scheme's benefits, eligibility "
    "or application steps — the user already has those.\n"
    "- If the user ALSO asked for a link, use ONLY a URL from the VERIFIED LINKS "
    "section below, in one short line FIRST, then the document. If that section "
    "has none, do NOT include any link — say a working link could not be confirmed.\n"
    "- Do NOT use the sectioned scheme layout. No 'Financial benefits' heading."
)

_LINK_INSTRUCTION = (
    "The user asked for a SPECIFIC RESOURCE (link, portal, form or download).\n"
    "- You may ONLY output a URL that appears in the VERIFIED LINKS section below "
    "— it has already been checked and is confirmed reachable right now.\n"
    "- If VERIFIED LINKS says none are available, say so plainly in one line and "
    "name the official ministry/portal instead. NEVER invent, guess, or recall a "
    "URL from memory — an unverified link is worse than admitting you don't have one.\n"
    "- If the user is reporting that a PREVIOUS link failed, acknowledge that "
    "briefly, then give the newly verified link — do not repeat the broken one.\n"
    "- Then at most two sentences on how to use it.\n"
    "- NO section headings. Do NOT restate benefits, eligibility or the process."
)

_LIST_ALL_INSTRUCTION = (
    "The user wants EVERY relevant scheme listed, not just a few highlights.\n"
    "- Enumerate every DISTINCT scheme found in the retrieved context as a numbered list.\n"
    "- Each entry: **Scheme name** — one-line description of what it offers, no more.\n"
    "- Do NOT go into eligibility or how-to-apply detail for each one — that is a "
    "follow-up question, not this one.\n"
    "- If the schemes fall into clear categories (e.g. education, financial, "
    "healthcare), group them under short sub-headings.\n"
    "- Do NOT use the single-scheme sectioned layout (no 'Financial benefits' heading).\n"
    "- Skip a scheme you have already listed earlier in this conversation."
)

_COMPARE_INSTRUCTION = (
    "The user wants schemes COMPARED and/or wants a RECOMMENDATION for the best one.\n"
    "- Identify the distinct schemes actually in play — from the retrieved context and "
    "from schemes already named earlier in this conversation.\n"
    "- Build a Markdown TABLE comparing them: columns for Scheme, Key benefit, Who "
    "qualifies, Best for. Keep each cell to a few words.\n"
    "- After the table, in 2-4 sentences, RECOMMEND the best option for THIS user's "
    "stated situation (age, disability type/%, needs already given in the conversation) "
    "and explain why, referring back to the table.\n"
    "- If you do not have enough detail about the user's situation to recommend "
    "confidently, say so and ask ONE clarifying question instead of guessing.\n"
    "- Do NOT re-describe each scheme in full prose outside the table."
)

_STEPS_INSTRUCTION = (
    "The user wants ONLY the application procedure, not the scheme description.\n"
    "- Give a numbered list of steps (1. 2. 3. ...), each step one line.\n"
    "- Fold in where to go/submit and what's required directly into the relevant step, "
    "rather than a separate documents section.\n"
    "- NO headings, and do NOT re-explain benefits or eligibility — only the process."
)

_EXPLAIN_INSTRUCTION = (
    "The user wants something EXPLAINED (how it works, how to fill a form, what a "
    "term means).\n"
    "- Explain only that, in 3-6 sentences or a short numbered list.\n"
    "- If it is a form, walk through the fields in order and what goes in each.\n"
    "- NO section headings. Do NOT re-describe the whole scheme."
)

_LOOKUP_INSTRUCTION = (
    "The user is asking which schemes or benefits are available.\n"
    "- Lead with a 1-2 sentence bottom line reflecting their stated situation.\n"
    "- Then use the sectioned layout, including only the sections that apply:\n"
    "  `## 💰 Financial benefits`, `## ✅ Who can apply`, `## 📝 How to apply`,\n"
    "  `## 📄 Documents needed`, `## 📞 Where to go`.\n"
    "- Bold every amount, percentage, deadline, scheme name and form number.\n"
    "- Skip any scheme you have already covered earlier in this conversation."
)

_ELIGIBILITY_INSTRUCTION = (
    "The user is asking whether someone QUALIFIES.\n"
    "- Give the verdict first: likely eligible, not eligible, or depends on X.\n"
    "- Then list only the criteria that decide it, marking which are met/unmet "
    "based on what the user has told you.\n"
    "- Ask for a missing detail only if it actually changes the answer, and only "
    "if you have not already asked for it."
)

_SUMMARIZE_INSTRUCTION = (
    "The user explicitly asked for a recap. Summarise what has already been "
    "discussed in a short bulleted list. Add no new sections and no new schemes."
)

_SMALL_TALK_INSTRUCTION = (
    "This is conversational, not a scheme question. Reply warmly in one or two "
    "sentences and invite their question. Do not list schemes."
)

_GENERAL_INSTRUCTION = (
    "Answer using your own reasoning and general knowledge, clearly and directly.\n"
    "- If this concerns Indian disability schemes but your knowledge base has "
    "nothing on it, say what you do know, state plainly that it is not in your "
    "sources, and point to the official portal to confirm.\n"
    "- Do NOT force an unrelated scheme summary into the answer."
)

ROUTES: dict[Intent, Route] = {
    #                            retrieval  history   instruction               retrieval_depth
    Intent.SCHEME_LOOKUP:  Route(Intent.SCHEME_LOOKUP,  True,  "facts", _LOOKUP_INSTRUCTION),
    # These two must see MANY schemes at once, not the narrow top-3 default —
    # see RetrievalDepth above for why that default silently broke both.
    Intent.LIST_ALL:       Route(Intent.LIST_ALL,       True,  "facts", _LIST_ALL_INSTRUCTION, "broad"),
    Intent.COMPARE:        Route(Intent.COMPARE,        True,  "facts", _COMPARE_INSTRUCTION,  "broad"),
    Intent.ELIGIBILITY:    Route(Intent.ELIGIBILITY,    True,  "facts", _ELIGIBILITY_INSTRUCTION),
    Intent.RESOURCE_LINK:  Route(Intent.RESOURCE_LINK,  True,  "none",  _LINK_INSTRUCTION),
    # Retrieval stays ON so names/portals are accurate, but the instruction makes
    # the document the output — this is the composite "link + write it" case.
    Intent.WRITE_DOCUMENT: Route(Intent.WRITE_DOCUMENT, True,  "facts", _WRITE_INSTRUCTION),
    Intent.STEPS:          Route(Intent.STEPS,          True,  "none",  _STEPS_INSTRUCTION),
    Intent.EXPLAIN:        Route(Intent.EXPLAIN,        True,  "none",  _EXPLAIN_INSTRUCTION),
    # No retrieval at all for these three — the knowledge base is irrelevant.
    Intent.SUMMARIZE:      Route(Intent.SUMMARIZE,      False, "full",  _SUMMARIZE_INSTRUCTION),
    Intent.SMALL_TALK:     Route(Intent.SMALL_TALK,     False, "none",  _SMALL_TALK_INSTRUCTION),
    Intent.GENERAL:        Route(Intent.GENERAL,        False, "facts", _GENERAL_INSTRUCTION),
}


# --------------------------------------------------------------------------- fast path
# Only patterns that are unambiguous on their own. Anything else goes to the LLM.
# "write/draft/compose an application" beats a bare "link" mention, because the
# writing task is the harder requirement and subsumes quoting a URL.
_WRITE_RE = re.compile(
    r"\b(write|draft|compose|prepare|type|make)\b[^.?!]{0,40}"
    r"\b(application|letter|email|mail|request|appeal|complaint|format|template|sample)\b"
    r"|\b(application|letter|email|request)\s+(format|template|sample|draft)\b"
    r"|\bproper format\b", re.I)
_SUMMARIZE_RE = re.compile(
    r"\b(summar\w+|recap|tl;?dr|say (that )?again|repeat that)\b", re.I)
_COMPARE_RE = re.compile(
    r"\b(compare|comparison|versus|vs\.?)\b|\bwhich\b.{0,15}\b(is )?better\b|"
    r"\bwhich (one|scheme|option)\b.{0,20}\b(better|best|should)\b|"
    r"\bpros and cons\b|\bdifference between\b|\bwhat.?s the difference\b|"
    r"\brecommend\b.{0,15}\b(scheme|option|one)\b|\bbest (scheme|option) for\b", re.I)
_LIST_ALL_RE = re.compile(
    r"\b(list|show|enumerate|give me)\b.{0,20}\b(all|every)\b.{0,25}\b(scheme|benefit|option|program)\b"
    r"|\ball (the )?(available )?schemes\b|\bevery (available )?scheme\b"
    r"|\ball (the )?(available )?(benefits|options|programs)\b", re.I)
_STEPS_RE = re.compile(
    r"\bhow (do|can|to) i (apply|register|enroll|enrol|submit)\b|\bapplication process\b|"
    r"\bstep[- ]by[- ]step\b|\bsteps to apply\b|\bprocedure to apply\b|\bhow to apply\b", re.I)
_LINK_RE = re.compile(
    r"\b(link|links|url|website|portal|download|pdf)\b", re.I)
_SMALL_TALK_RE = re.compile(
    r"^\s*(hi|hello|hey|thanks|thank you|thankyou|ok|okay|good (morning|evening|night)|bye)"
    r"[\s!.]*$", re.I)

# A user reporting a broken link is still a RESOURCE_LINK request, but it must
# force a fresh search rather than repeat the same (now known-bad) URL.
LINK_RETRY_RE = re.compile(
    r"\b(link|url|website|site|page|form)\b.{0,25}\b(not work\w*|not opening|"
    r"broken|dead|expired|invalid|wrong|outdated|doesn'?t work\w*|isn'?t work\w*|"
    r"404|403|not found|error)\b"
    r"|\b(404|403|dns_probe|page not found|(site|page|link)\s+can'?t be reached)\b", re.I)


def is_link_retry(question: str) -> bool:
    """True when the user is reporting that a previously given link failed."""
    return bool(LINK_RETRY_RE.search(question or ""))


def _fast_path(question: str) -> Intent | None:
    q = (question or "").strip()
    if not q:
        return None
    if _SMALL_TALK_RE.match(q):
        return Intent.SMALL_TALK
    if is_link_retry(q):             # checked first: "this link is broken" always means retry
        return Intent.RESOURCE_LINK
    if _SUMMARIZE_RE.search(q):
        return Intent.SUMMARIZE
    if _WRITE_RE.search(q):          # checked before links: writing dominates
        return Intent.WRITE_DOCUMENT
    if _COMPARE_RE.search(q):
        return Intent.COMPARE
    if _LIST_ALL_RE.search(q):
        return Intent.LIST_ALL
    if _STEPS_RE.search(q):
        return Intent.STEPS
    if _LINK_RE.search(q):
        return Intent.RESOURCE_LINK
    return None


# --------------------------------------------------------------------------- LLM path
CLASSIFY_PROMPT = """Classify the user's LATEST message into exactly one label.

Labels:
SCHEME_LOOKUP - asking WHICH schemes, benefits, scholarships or financial help exist
                for a described situation (wants the best few, in some depth)
LIST_ALL - wants EVERY relevant scheme enumerated, not just the top few
           ("list all schemes", "show every option", "what are all the benefits")
COMPARE - wants schemes compared against each other, or wants a recommendation for
          which one is best ("which is better", "compare X and Y", "what do you recommend")
ELIGIBILITY - asking whether a SPECIFIC person qualifies (a yes/no judgement), or what
              the eligibility cut-offs of a named scheme are
RESOURCE_LINK - asking for a link, website, portal, form or download
WRITE_DOCUMENT - asking you to WRITE something: an application, letter, email, request, or a filled-in format/template
STEPS - wants ONLY the step-by-step application procedure ("how to apply", "application process")
EXPLAIN - asking how something works, or what a term means (not the application process)
SUMMARIZE - asking you to recap or summarise the conversation so far
SMALL_TALK - greeting, thanks, or chit-chat
GENERAL - anything else, including questions your scheme documents would not cover

If the message asks for BOTH a link and for you to write something, choose WRITE_DOCUMENT.

Examples:
"Scholarships for a visually impaired college student?" -> SCHEME_LOOKUP
"What help can I get for my autistic child?" -> SCHEME_LOOKUP
"Health insurance schemes for a child with autism?" -> SCHEME_LOOKUP
"List down all the schemes" -> LIST_ALL
"Show me every benefit available for locomotor disability" -> LIST_ALL
"Which scheme is better for my daughter?" -> COMPARE
"What would you recommend given her situation?" -> COMPARE
"Compare Niramaya and the Subsistence Allowance" -> COMPARE
"Is my daughter eligible with 45% disability?" -> ELIGIBILITY
"Does she qualify for the Post-Matric scholarship?" -> ELIGIBILITY
"Give me the application form link" -> RESOURCE_LINK
"Write an application for the scholarship" -> WRITE_DOCUMENT
"Application form link, and if I have to write an application give me a proper format" -> WRITE_DOCUMENT
"How do I apply for the UDID card?" -> STEPS
"What is the application process for Niramaya?" -> STEPS
"How do I fill the UDID form?" -> EXPLAIN
"What does benchmark disability mean?" -> EXPLAIN

Conversation so far (context only):
{history}

Latest message: {question}

Reply with ONLY the label, nothing else."""

_classifier = None


def _classify_llm(question: str, history: str) -> Intent | None:
    """Ask the LLM for a label. Returns None if the call or parse fails."""
    global _classifier
    try:
        if _classifier is None:
            from chatbot.rag_pipeline import make_llm
            # Deterministic and tiny: we only need one word back.
            _classifier = make_llm(temperature=0.0)
        chain = PromptTemplate.from_template(CLASSIFY_PROMPT) | _classifier | StrOutputParser()
        raw = (chain.invoke({"question": question[:600], "history": history[:1200]}) or "").strip()
        token = re.sub(r"[^A-Z_]", "", raw.upper())
        for intent in Intent:
            if intent.value in token:
                return intent
    except Exception as e:
        print(f"[router] classification failed, falling back: {e}")
    return None


def classify(question: str, history: str = "") -> Route:
    """
    Resolve a message to a Route. Order: deterministic fast path, then the LLM,
    then a safe default of SCHEME_LOOKUP (the original behaviour).
    """
    intent = _fast_path(question) or _classify_llm(question, history) or Intent.SCHEME_LOOKUP
    return ROUTES[intent]


# --------------------------------------------------------------------------- format hints
# A presentation request ("put this in a table") can modify ANY intent above —
# it is not a topic of its own, so it is layered on top of the classified route
# rather than being its own Intent.
_TABLE_RE = re.compile(r"\b(as a table|in a table|tabular( form)?|table format)\b", re.I)
_CHECKLIST_RE = re.compile(r"\b(checklist|check[- ]?list|as a checklist|tick(ing)? off)\b", re.I)


def format_hint_instruction(question: str) -> str:
    """Extra formatting directive to append, or "" if no explicit format was asked for."""
    q = question or ""
    if _TABLE_RE.search(q):
        return ("\n\nThe user explicitly asked for a TABLE: present the core information "
                "as a Markdown table with clear column headers, in addition to (or instead "
                "of) the format above.")
    if _CHECKLIST_RE.search(q):
        return ("\n\nThe user explicitly asked for a CHECKLIST: present the items as "
                "`- [ ] item` checkbox entries, one per line.")
    return ""
