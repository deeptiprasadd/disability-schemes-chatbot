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

3. **RESPONSE STRUCTURE**:
   - **Quick Summary**: Start with a 1-sentence bottom line that acknowledges the user's specific constraints (e.g., "Since your child cannot pursue education, the most relevant benefits are medical insurance and monthly pension.").
   - 💰 **Financial Benefits**: Bold the **AMOUNT**. If unknown, state clearly.
   - ✅ **Who can apply**: List specific eligibility criteria.
   - 📝 **How to apply**: Simple, numbered steps.
   - **Further Questions**: At the very end, if you are missing age or disability %, ask for them to provide more accurate info.

4. **ADAPTIVE CONVERSATION**:
   - Read the conversation so far carefully. NEVER re-ask for a detail (age, disability type/%, state, income, education status) the user has already given — use it.
   - If the question is broad (e.g., "what schemes exist?") and key details are unknown, give a short useful overview FIRST, then ask at most 2 targeted follow-up questions.
   - If the user's request is fully specified, answer directly and ask nothing.
   - Match the user's level of detail: short question, concise answer.

Conversation so far:
{chat_history}

Context:
{context}

Question: {question}

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
    compressor = FlashrankRerank()
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=_ensemble_retriever
    )

    llm = make_llm(temperature=0.1)

    condense_prompt = PromptTemplate.from_template(CONDENSE_QUESTION_PROMPT)
    answer_prompt = PromptTemplate.from_template(SYSTEM_PROMPT)

    # Condense question logic
    def condense_question(input_dict):
        if not input_dict.get("chat_history"):
            return input_dict["question"]
        
        # Format history for the prompt
        history_str = ""
        for msg in input_dict["chat_history"]:
            role = "Human" if isinstance(msg, HumanMessage) else "Assistant"
            history_str += f"{role}: {msg.content}\n"
        
        chain = condense_prompt | llm | StrOutputParser()
        return chain.invoke({"chat_history": history_str, "question": input_dict["question"]})

    # The Final Pipeline
    _chain = (
        RunnablePassthrough.assign(
            standalone_question=RunnableLambda(condense_question)
        )
        | RunnablePassthrough.assign(
            context=lambda x: (
                format_docs(compression_retriever.invoke(x["standalone_question"]))
                + (f"\n---\nDocument uploaded by the user:\n{x['extra_context'][:6000]}\n"
                   if x.get("extra_context") else "")
            ),
            question=lambda x: x["standalone_question"],
            chat_history=lambda x: _history_to_str(x.get("chat_history")),
        )
        | answer_prompt
        | llm
        | StrOutputParser()
    )

    print("Advanced Pipeline ready.")
    return _chain

def _to_lc_messages(chat_history: list) -> list:
    """Convert [{'role','content'}] session history to LangChain messages."""
    messages = []
    for msg in chat_history or []:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        messages.append(cls(content=msg["content"]))
    return messages


def _history_to_str(messages) -> str:
    """Render the last few turns for the answer prompt (keeps tokens bounded)."""
    if not messages:
        return "(no prior conversation)"
    lines = []
    for m in messages[-8:]:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        lines.append(f"{role}: {m.content}")
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
    chain = load_pipeline()
    answer = chain.invoke({
        "question": question,
        "chat_history": _to_lc_messages(chat_history),
        "extra_context": extra_context,
    })
    return {
        "answer":  answer,
        "sources": get_sources(question),
    }


def ask_stream(question: str, chat_history: list = None, extra_context: str = None):
    """Yield answer tokens as they are generated (for st.write_stream)."""
    chain = load_pipeline()
    yield from chain.stream({
        "question": question,
        "chat_history": _to_lc_messages(chat_history),
        "extra_context": extra_context,
    })