import os
import re
import sys
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# Run as `python scripts/embed_docs.py` from the project root: make `chatbot` importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chatbot.embeddings import get_embeddings  # noqa: E402  (same model as the server's search)

KB_DIR = "knowledge-base"
VS_DIR = "scripts/vector_store"

_NAME_RE = re.compile(r'^scheme_name:\s*"?(.+?)"?\s*$', re.M)
_TYPES_RE = re.compile(r"^disability_types:\s*(.+)$", re.M)


def scheme_headers(text):
    """
    [(offset, header)] for each scheme in a file. A file can hold several
    schemes, each starting with its own front matter.
    """
    out = []
    for m in _NAME_RE.finditer(text):
        t = _TYPES_RE.search(text, m.end(), m.end() + 400)
        types = t.group(1).strip("[] ").replace('"', "").replace("'", "") if t else ""
        header = f"[Scheme: {m.group(1)}"
        if types and types.lower() != "all":
            header += f" | For: {types}"
        out.append((m.start(), header + "]"))
    return out


def add_scheme_headers(docs, chunks):
    """
    Prefix every chunk with the scheme it belongs to. A 500-character slice of
    a scheme file rarely names its scheme ("Age 0 to 60 years..."), so search
    could not match "health insurance for my child" to NIRAMAYA's chunks, and
    the model mixed eligibility rules between schemes (e.g. gave the Delhi
    pension the UP pension's 18+ age limit).
    """
    headers = {d.metadata["source"]: scheme_headers(d.page_content) for d in docs}
    for c in chunks:
        spans = headers.get(c.metadata["source"]) or []
        start = c.metadata.get("start_index", 0)
        current = [h for off, h in spans if off <= start]
        header = current[-1] if current else (spans[0][1] if spans else "")
        if header:
            c.metadata["scheme_name"] = header[len("[Scheme: "):].split(" | ")[0].rstrip("]")
            c.page_content = f"{header}\n{c.page_content}"
    return chunks


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
        separators=["\n## ", "\n### ", "\n- ", "\n", " "],
        add_start_index=True,  # needed to find which scheme each chunk belongs to
    )
    chunks = add_scheme_headers(docs, splitter.split_documents(docs))
    print(f"  Created {len(chunks)} chunks (each labelled with its scheme).")

    print("Loading local embedding model (first time downloads ~90MB)...")
    embeddings = get_embeddings()

    print("Embedding and saving vector store...")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    os.makedirs(VS_DIR, exist_ok=True)
    vectorstore.save_local(VS_DIR)
    print(f"  Vector store saved to {VS_DIR}/")
    print("Done.")

if __name__ == "__main__":
    run()