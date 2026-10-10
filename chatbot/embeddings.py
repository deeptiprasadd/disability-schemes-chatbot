"""
The sentence-embedding model, shared by indexing (scripts/embed_docs.py) and
search (chatbot/rag_pipeline.py) so both always produce comparable vectors.

This is the ONNX build of all-MiniLM-L6-v2 run by fastembed. It gives the same
vectors as the sentence-transformers version (cosine similarity 1.00000 in
testing) without loading PyTorch, which took the server from ~1.5 GB of RAM
down to a size that fits free 512 MB hosting tiers.
"""

import os

from langchain_community.embeddings import FastEmbedEmbeddings

MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_embeddings() -> FastEmbedEmbeddings:
    # FASTEMBED_CACHE_PATH lets the Docker image bake the model in at build time.
    # One thread by default: a single short query gains nothing from more, and
    # each extra ONNX thread costs memory on a 512 MB host.
    return FastEmbedEmbeddings(model_name=MODEL, cache_dir=os.getenv("FASTEMBED_CACHE_PATH"),
                               threads=int(os.getenv("EMBED_THREADS", "1")))
