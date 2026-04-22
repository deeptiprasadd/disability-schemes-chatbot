import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

KB_DIR = "knowledge-base"
VS_DIR = "scripts/vector_store"

def run():
    print("Loading documents...")
    loader = DirectoryLoader(
        KB_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        recursive=True
    )
    docs = loader.load()
    print(f"  Loaded {len(docs)} files.")

    print("Splitting into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n## ", "\n### ", "\n- ", "\n", " "]
    )
    chunks = splitter.split_documents(docs)
    print(f"  Created {len(chunks)} chunks.")

    print("Loading local embedding model (first time downloads ~90MB)...")
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"}
    )

    print("Embedding and saving vector store...")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    os.makedirs(VS_DIR, exist_ok=True)
    vectorstore.save_local(VS_DIR)
    print(f"  Vector store saved to {VS_DIR}/")
    print("Done.")

if __name__ == "__main__":
    run()