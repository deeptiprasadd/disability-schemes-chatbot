import os
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

KB_DIR     = "knowledge-base"
VS_DIR     = "scripts/vector_store"

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

    print("Embedding and saving vector store...")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(VS_DIR)
    print(f"  Vector store saved to {VS_DIR}/")
    print("Done.")

if __name__ == "__main__":
    run()
