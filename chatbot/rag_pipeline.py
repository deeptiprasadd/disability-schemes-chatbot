import os
import torch
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
from dotenv import load_dotenv

load_dotenv()


def make_llm(temperature: float = 0.1):
    """
    Build the chat model from environment configuration so the app is not
    hard-locked to a single provider (the root cause of a total outage when
    Groq is unreachable — e.g. a VPN IP, a region block, or a Groq outage).

    Controlled by LLM_PROVIDER (default "groq"):
      * groq   -> Groq cloud (GROQ_MODEL, default llama-3.1-8b-instant)
      * ollama -> a LOCAL model, no external network at all
                  (OLLAMA_MODEL default llama3.1, OLLAMA_BASE_URL default
                   http://localhost:11434). Works even behind a VPN.
      * openai -> any OpenAI-compatible endpoint (OPENAI_MODEL, OPENAI_BASE_URL)

    Default stays Groq, so existing behaviour is unchanged unless configured.
    """
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.1"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            temperature=temperature,
        )

    from langchain_groq import ChatGroq
    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        temperature=temperature,
    )

from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage

from chatbot.router import classify, is_link_retry, format_hint_instruction, Intent, Route  # noqa: F401  (Intent/Route re-exported)
from chatbot.link_utils import find_verified_links, format_verified_block, extract_urls, sanitize_answer_links

VS_DIR = "scripts/vector_store"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Using device: {DEVICE}")

CONDENSE_QUESTION_PROMPT = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question, in its original language.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""

SYSTEM_PROMPT = """You are an empathetic, user-friendly assistant for persons with disabilities in India. 
Your goal is to provide clear, simple, and direct information about government schemes.

CRITICAL RULES:
1. **NO HALLUCINATIONS**: 
   - NEVER invent user details. If you don't know the person's age, disability %, or income, DO NOT make them up (e.g., do not say "Since you are 21 years old").
   - If information is missing, use general terms like "Applicable beneficiaries" or "Depending on age/disability" and ask the user for these details at the end of your response.
   - NEVER assume a large number (like a Pincode or Phone number) is a financial benefit. ONLY use amounts explicitly stated as "Grant", "Pension", "Allowance", or "Scholarship amount".

2. **ELIGIBILITY & NEGATIVE CONSTRAINTS**:
   - If the user explicitly states the person **cannot study**, is **not in school**, or has a **severe intellectual disability** that prevents education, you MUST NOT suggest scholarships or educational schemes.
   - For a "kid who cannot study", focus exclusively on: **Niramaya (Health Insurance)**, **Subsistence Allowance (Pension)**, and **National Trust residential care (Samarth/Gharaunda)**.
   - If a scheme requires being a "student" or having "passed Class 10", and the user information doesn't match, EXCLUDE it.

3. **ANSWER THE QUESTION THAT WAS ASKED — NEVER REPEAT YOURSELF**:
   - The conversation history below is BACKGROUND CONTEXT ONLY. It is NOT a template to refill.
   - You have ALREADY told the user everything in that history. NEVER restate, re-list
     or re-format it. Do not re-describe a scheme's benefits, eligibility, or application
     steps that you already gave earlier in this conversation.
   - If the user asks something NARROW (a link, a form, a document, a definition, a
     clarification, "what type of X"), answer ONLY that, in 2-5 sentences. NOTHING ELSE.
   - Produce the full multi-section scheme layout ONLY when the user is asking broadly
     about what schemes/benefits are available and you have not already answered that.
   - Only summarise earlier answers if the user EXPLICITLY asks for a recap or summary.
   - Ask for age / disability % AT MOST ONCE per conversation. If the history shows you
     already asked, DO NOT ask again.

4. **GENERAL STYLE** (the task instruction below overrides these defaults):
   - **Bold** every amount, deadline, percentage, scheme name and form number.
   - `-` bullets for facts, `1.` `2.` for ordered steps, at most one `>` callout.
   - NEVER re-ask for a detail (age, disability type/%, state, income, education
     status) the user already gave — use it silently. Ask for a missing detail at
     most ONCE per conversation.
   - Match the user's level of detail: short question, short answer.

6. **LINKS — ABSOLUTE RULE**:
   - NEVER type a URL from memory or training data, even one that looks correct.
   - The ONLY URLs you are permitted to output are the ones listed under
     VERIFIED LINKS below. If it says none are available, give no URL at all —
     say so plainly and name the official portal/ministry instead.

=========================== YOUR TASK THIS TURN ===========================
{task_instruction}
===========================================================================

Conversation so far (background only — ALREADY DELIVERED, do NOT repeat it):
{chat_history}
{context_block}
{verified_links_block}

User's message: {question}

Answer:"""

_chain              = None
_base_retriever     = None
_ensemble_retriever = None

import re

def format_docs(docs):
    context = ""
    for doc in docs:
        content = doc.page_content
        # Remove contact-heavy sections to prevent Pincode/Phone hallucinations
        content = re.sub(r'## Contact.*', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'Address:.*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'Phone:.*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'Email:.*', '', content, flags=re.IGNORECASE)
        context += f"\n---\n{content}\n"
    return context

def load_pipeline():
    global _chain, _ensemble_retriever
    if _chain:
        return _chain

    print("Loading vector store and reranker...")
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": DEVICE}
    )

    # 1. Load FAISS (Semantic)
    vectorstore = FAISS.load_local(
        VS_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )
    
    faiss_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

    # 2. Setup BM25 (Keyword) - we rebuild it from the FAISS docs
    # This ensures we have the same corpus for both
    docs = list(vectorstore.docstore._dict.values())
    bm25_retriever = BM25Retriever.from_documents(docs)
    bm25_retriever.k = 10

    # 3. Create Ensemble Retriever (Hybrid)
    _ensemble_retriever = EnsembleRetriever(
        retrievers=[faiss_retriever, bm25_retriever],
        weights=[0.7, 0.3]
    )

    # 4. Add Reranking Layer (FlashRank)
    # NOTE: FlashrankRerank() defaults to top_n=3 — every request, regardless of
    # intent, was silently capped to 3 chunks of context. That's invisible for a
    # single-scheme question but it structurally breaks "list all schemes" or
    # "compare X and Y": the model can never see more than 3 fragments (often
    # from the SAME scheme) no matter what is asked. A second, wider pipeline
    # below fixes that for the intents that genuinely need to see many schemes
    # at once (see Route.retrieval_depth in router.py).
    compressor = FlashrankRerank()
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=_ensemble_retriever
    )

    print("Building broad retriever (list-all / compare)...")
    faiss_retriever_broad = vectorstore.as_retriever(search_kwargs={"k": 20})
    bm25_retriever_broad = BM25Retriever.from_documents(docs)  # separate instance: own .k
    bm25_retriever_broad.k = 20
    ensemble_retriever_broad = EnsembleRetriever(
        retrievers=[faiss_retriever_broad, bm25_retriever_broad],
        weights=[0.7, 0.3]
    )
    compression_retriever_broad = ContextualCompressionRetriever(
        base_compressor=FlashrankRerank(top_n=15),
        base_retriever=ensemble_retriever_broad,
    )

    llm = make_llm(temperature=0.1)

    _chain = {
        "llm": llm,
        "retriever": compression_retriever,
        "retriever_broad": compression_retriever_broad,
        "answer_chain": PromptTemplate.from_template(SYSTEM_PROMPT) | llm | StrOutputParser(),
        "condense_chain": PromptTemplate.from_template(CONDENSE_QUESTION_PROMPT) | llm | StrOutputParser(),
    }

    print("Advanced Pipeline ready.")
    return _chain


# --------------------------------------------------------------- routed execution

def _condense(question: str, history_msgs: list, comps: dict) -> str:
    """
    Rewrite a follow-up into a standalone RETRIEVAL query, so "which form?" still
    finds the right documents. Only used when we are actually retrieving.
    """
    if not history_msgs:
        return question
    history_str = "\n".join(
        f"{'Human' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in history_msgs[-4:]
    )
    try:
        return comps["condense_chain"].invoke(
            {"chat_history": history_str, "question": question}
        ).strip() or question
    except Exception as e:
        print(f"[pipeline] condense failed, using raw question: {e}")
        return question


# Intents where the answer might present a link, so verification is worth its cost.
_LINK_AWARE_INTENTS = {Intent.RESOURCE_LINK, Intent.WRITE_DOCUMENT}


def _prior_answer_urls(history_msgs: list) -> set[str]:
    """URLs from the most recent assistant turn — excluded on a link-retry."""
    for m in reversed(history_msgs):
        if isinstance(m, AIMessage):
            return set(extract_urls(m.content))
    return set()


def _build_prompt_inputs(question: str, chat_history: list, extra_context: str,
                         route) -> tuple[dict, set]:
    """
    Assemble exactly the inputs this route needs, plus the set of verified URLs
    (for the caller to strip anything else the model outputs anyway).

    The key behavioural change: retrieval and history are now CONDITIONAL. A
    "write me an application" turn no longer drags the whole scheme corpus into
    the prompt, which is what caused the model to re-emit the scheme summary.
    Links are handled the same way: only URLs that pass a live reachability
    check are ever placed in front of the model.
    """
    comps = load_pipeline()
    history_msgs = _to_lc_messages(chat_history)
    retry = is_link_retry(question)

    # 1. Retrieval — only when the route says the knowledge base is relevant.
    # "broad" (list-all / compare) uses a much wider retriever so the model can
    # actually see many distinct schemes instead of FlashrankRerank's top_n=3.
    docs = []
    if route.needs_retrieval:
        query = _condense(question, history_msgs, comps)
        retriever_key = "retriever_broad" if route.retrieval_depth == "broad" else "retriever"
        docs = comps[retriever_key].invoke(query)
    context_block = format_docs(docs) if docs else ""
    if extra_context:
        context_block += (
            f"\n---\nDocument uploaded by the user:\n{extra_context[:6000]}\n"
        )
    context_block = (
        f"\nRetrieved reference material:\n{context_block}\n" if context_block.strip()
        else "\n(No reference documents needed for this task.)\n"
    )

    # 1b. Link verification — never let the model see or output an unchecked URL.
    # Runs for ANY retrieval route (so a stray "Where to go" link is checked too),
    # but only escalates to a live web search when a resource was actually asked
    # for — that is the expensive path and shouldn't fire on every scheme lookup.
    verified_urls: set[str] = set()
    verified_block = "VERIFIED LINKS: not applicable to this request."
    if route.needs_retrieval:
        link_focused = route.intent in _LINK_AWARE_INTENTS or retry
        exclude = _prior_answer_urls(history_msgs) if retry else set()
        result = find_verified_links(
            question, docs, exclude=exclude, allow_web_search=link_focused,
        )
        verified_block = format_verified_block(result)
        verified_urls = {r["url"] for r in result["verified"]}

    # 2. History — scoped to what this route can actually use.
    if route.history_mode == "none":
        history_str = "(not relevant to this request)"
    elif route.history_mode == "full":
        history_str = _history_to_str(history_msgs, clip=False)
    else:  # "facts"
        history_str = _history_to_str(history_msgs)

    # 3. Format hint — "put this in a table" etc. can modify ANY intent above,
    # so it's layered onto the instruction per-turn rather than being its own Route.
    task_instruction = route.instruction + format_hint_instruction(question)

    inputs = {
        "question": question,
        "chat_history": history_str,
        "context_block": context_block,
        "verified_links_block": verified_block,
        "task_instruction": task_instruction,
    }
    return inputs, verified_urls

def _to_lc_messages(chat_history: list) -> list:
    """Convert [{'role','content'}] session history to LangChain messages."""
    messages = []
    for msg in chat_history or []:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        messages.append(cls(content=msg["content"]))
    return messages


ASSISTANT_CLIP = 220  # chars of a past answer kept as a reminder, not a template


def _history_to_str(messages, clip: bool = True) -> str:
    """
    Render recent turns as background context.

    User turns are kept in full (they carry the constraints we must honour, like
    age or "cannot study"). Past ASSISTANT turns are deliberately CLIPPED: given
    a full previous answer the model tends to re-emit it verbatim, which is what
    made every follow-up repeat the entire scheme summary.
    """
    if not messages:
        return "(no prior conversation)"
    lines = []
    for m in messages[-6:]:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {m.content}")
        else:
            gist = " ".join((m.content or "").split())
            # clip=False only for an explicit recap, where the full text is the point.
            if clip and len(gist) > ASSISTANT_CLIP:
                gist = gist[:ASSISTANT_CLIP].rstrip() + " …(already delivered in full)"
            lines.append(f"You already answered: {gist}")
    return "\n".join(lines)


def get_sources(question: str) -> list:
    """Top source filenames for a question, via the hybrid retriever."""
    if _ensemble_retriever is None:
        load_pipeline()
    docs = _ensemble_retriever.invoke(question)
    return list({
        os.path.basename(doc.metadata.get("source", ""))
        for doc in docs
    })


def ask(question: str, chat_history: list = None, extra_context: str = None) -> dict:
    """
    Answer a question, routing it to the appropriate strategy first.

    Returns the answer, the citations (empty when the route did not retrieve),
    and the detected intent so callers can log or display it. Any URL the model
    outputs is sanitized against the verified set as a deterministic backstop —
    prompting alone cannot guarantee an 8B model never types a link from memory.
    """
    comps = load_pipeline()
    route = classify(question, _history_to_str(_to_lc_messages(chat_history)))
    inputs, verified_urls = _build_prompt_inputs(question, chat_history, extra_context, route)
    answer = comps["answer_chain"].invoke(inputs)
    if route.needs_retrieval:
        answer = sanitize_answer_links(answer, verified_urls)
    return {
        "answer":  answer,
        "sources": get_sources(question) if route.needs_retrieval else [],
        "intent":  route.intent.value,
    }


def route_for(question: str, chat_history: list = None):
    """Resolve the Route for a message (exposed so the API can report intent)."""
    return classify(question, _history_to_str(_to_lc_messages(chat_history)))


def ask_stream(question: str, chat_history: list = None, extra_context: str = None,
               route=None, result: dict = None):
    """
    Yield answer tokens as they are generated.

    `route` may be supplied by the caller to avoid classifying twice when it
    already needed the intent (e.g. to decide whether to show citations).

    A URL can span several streamed tokens, so it cannot be sanitized token by
    token. Pass a `result` dict and this generator fills in `result["verified_urls"]`
    before it starts yielding; once the stream is exhausted the caller applies
    `sanitize_answer_links(full_text, result["verified_urls"])` to the assembled
    text before showing or translating it — see server/main.py. Using an
    out-param (rather than a module-level variable) keeps this safe under
    concurrent requests.
    """
    comps = load_pipeline()
    route = route or route_for(question, chat_history)
    inputs, verified_urls = _build_prompt_inputs(question, chat_history, extra_context, route)
    if result is not None:
        result["verified_urls"] = verified_urls
    yield from comps["answer_chain"].stream(inputs)


# --------------------------------------------------------------- follow-ups

FOLLOWUP_PROMPT = """You help users navigate Indian government disability schemes.

Conversation so far:
{chat_history}

User just asked: {question}
Assistant just answered: {answer}

Write 3 to 5 SHORT follow-up questions that THIS USER would naturally ask next.

Rules:
- Written from the USER's point of view, asking the assistant.
- Specific to the topic above - e.g. required documents, where to apply,
  eligibility limits, timelines, fees, or closely related benefits.
- Maximum 10 words each. Each must end with a question mark.
- Output ONE question per line. No numbering, no bullets, no preamble.
"""

_followup_llm = None


def _parse_followups(raw: str, max_items: int) -> list:
    """Turn raw LLM lines into a clean, deduped list of questions."""
    out = []
    for line in (raw or "").splitlines():
        s = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().strip('"\'')
        # Keep only things that actually look like a short user question.
        if len(s) < 8 or len(s) > 90 or "?" not in s:
            continue
        if s not in out:
            out.append(s)
        if len(out) >= max_items:
            break
    return out


def generate_followups(question: str, answer: str, chat_history: list = None,
                       max_items: int = 5) -> list:
    """
    Ask the LLM for contextual follow-up questions based on the latest turn.
    Returns [] on any failure so the UI simply shows no chips.
    """
    global _followup_llm
    if not question or not answer:
        return []
    try:
        if _followup_llm is None:
            # Slightly higher temperature for variety across turns.
            _followup_llm = make_llm(temperature=0.4)
        chain = PromptTemplate.from_template(FOLLOWUP_PROMPT) | _followup_llm | StrOutputParser()
        raw = chain.invoke({
            "chat_history": _history_to_str(_to_lc_messages(chat_history)),
            "question": question[:600],
            "answer": answer[:1800],
        })
        return _parse_followups(raw, max_items)
    except Exception as e:
        print(f"[followups] generation failed: {e}")
        return []