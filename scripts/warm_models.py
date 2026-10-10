"""
Download the local models into the image at BUILD time (see Dockerfile), so
the first visitor after a restart does not wait for downloads:

  * all-MiniLM-L6-v2 (ONNX, via fastembed) — sentence embeddings for search
  * ms-marco-TinyBERT — FlashRank reranker (~4 MB, cached in /tmp)

The LLM itself runs on Groq, so nothing else is needed locally.
"""

import os
import sys

from flashrank import Ranker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chatbot.embeddings import get_embeddings  # noqa: E402

get_embeddings().embed_query("warm up")
Ranker()  # FlashrankRerank's default model and cache directory
print("Models cached.")
