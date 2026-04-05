import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from chatbot.prompts import SYSTEM_PROMPT

load_dotenv()

VS_DIR = "scripts/vector_store"

_vectorstore = None
_qa_chain    = None

def load_pipeline():
    global _vectorstore, _qa_chain

    if _qa_chain:
        return _qa_chain   # already loaded, reuse

    print("Loading vector store...")
    embeddings   = OpenAIEmbeddings(model="text-embedding-3-small")
    _vectorstore = FAISS.load_local(
        VS_DIR, embeddings, allow_dangerous_deserialization=True
    )

    retriever = _vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5}   # fetch top 5 relevant chunks
    )

    prompt_template = PromptTemplate(
        input_variables=["context", "question"],
        template=SYSTEM_PROMPT + "\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"
    )

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=1000
    )

    _qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": prompt_template},
        return_source_documents=True
    )

    print("Pipeline ready.")
    return _qa_chain

def ask(question: str) -> dict:
    """
    Returns:
        {
          "answer": str,
          "sources": [str]   # list of source file paths
        }
    """
    chain  = load_pipeline()
    result = chain.invoke({"query": question})

    sources = list({
        doc.metadata.get("source", "")
        for doc in result.get("source_documents", [])
    })

    return {
        "answer":  result["result"],
        "sources": sources
    }
