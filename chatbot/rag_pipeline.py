import os
import torch
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
from langchain_ollama import ChatOllama
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

    llm = ChatOllama(
        model="llama3.2:3b",
        temperature=0.1,
    )

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

    from langchain_core.runnables import RunnablePassthrough

    # The Final Pipeline
    _chain = (
        RunnablePassthrough.assign(
            standalone_question=RunnableLambda(condense_question)
        )
        | RunnablePassthrough.assign(
            context=lambda x: format_docs(compression_retriever.invoke(x["standalone_question"])),
            question=lambda x: x["standalone_question"]
        )
        | answer_prompt
        | llm
        | StrOutputParser()
    )

    print("Advanced Pipeline ready.")
    return _chain

def ask(question: str, chat_history: list = None) -> dict:
    chain = load_pipeline()
    
    # Convert session history to LangChain messages
    formatted_history = []
    if chat_history:
        for msg in chat_history:
            if msg["role"] == "user":
                formatted_history.append(HumanMessage(content=msg["content"]))
            else:
                formatted_history.append(AIMessage(content=msg["content"]))

    answer = chain.invoke({
        "question": question,
        "chat_history": formatted_history
    })

    # For sources, we use the retriever directly with the final question
    # (Simplified: we'll just use the ensemble retriever's top results)
    docs = _ensemble_retriever.invoke(question)
    sources = list({
        os.path.basename(doc.metadata.get("source", ""))
        for doc in docs
    })

    return {
        "answer":  answer,
        "sources": sources
    }