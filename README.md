# ♿ Disability Schemes Chatbot

An empathetic, user-friendly assistant designed to provide clear, simple, and direct information about government schemes for persons with disabilities in India. It is optimized for GPU and utilizes an advanced Hybrid Search Retrieval-Augmented Generation (RAG) pipeline for maximum accuracy.

## 🌟 Features

- **Hybrid Search Retrieval**: Combines semantic search (FAISS) and keyword search (BM25) to accurately find relevant scheme details.
- **Reranking**: Uses FlashRank to rerank retrieved documents, ensuring the most pertinent information is provided to the LLM.
- **Multilingual Support**: Supports multiple Indian languages (English, Hindi, Tamil, Telugu, Marathi, Bengali, Gujarati, Kannada, Malayalam, Punjabi) with seamless translation using `deep-translator`.
- **Voice Search Integration**: Users can ask questions via voice using the `streamlit-mic-recorder`.
- **Empathetic & Accurate Responses**: Strict system prompts prevent hallucinations and ensure responses are tailored to the user's specific constraints (e.g., age, disability type, education status).
- **Source Citations**: Clearly displays the sources from which the information was retrieved.

## 🛠️ Tech Stack

- **Frontend**: Streamlit
- **LLM**: Llama 3.1 8B (via Groq API for fast inference)
- **Embeddings**: HuggingFace (`all-MiniLM-L6-v2`)
- **Vector Store**: FAISS (GPU-accelerated if CUDA is available, fallback to CPU)
- **RAG & Orchestration**: LangChain (`EnsembleRetriever`, `ContextualCompressionRetriever`, `BM25Retriever`)
- **Translation**: `deep-translator`
- **Data Ingestion**: `requests`, `beautifulsoup4`, `pypdf`

## 🧩 Supported Disabilities

The chatbot provides information relevant to a wide range of disabilities, including:
- Visual impairment
- Locomotor disability
- Hearing impairment
- Intellectual disability
- Mental illness
- Autism spectrum disorder
- Cerebral palsy
- Specific learning disability
- Multiple disabilities

## ⚙️ How It Works (Working Pipeline)

1. **Data Ingestion & Embedding**: Official sources are scraped and parsed. The data is embedded using HuggingFace models and stored locally in a FAISS vector store.
2. **User Input**: The user interacts with the Streamlit app via text or voice in their preferred language.
3. **Translation**: The input is translated to English to maintain high retrieval and generation quality.
4. **Hybrid Retrieval**: An `EnsembleRetriever` fetches documents using FAISS (Semantic, 70% weight) and BM25 (Keyword, 30% weight).
5. **Reranking**: `FlashrankRerank` compresses and reranks the retrieved documents to surface the absolute best context.
6. **Generation**: The context and question are passed to the Groq-powered Llama 3.1 8B model. A strict system prompt ensures the output is factual, empathetic, and formatted with clear eligibility and financial details.
7. **Output**: The generated answer is translated back to the user's language and displayed alongside citation tags.

## 🚀 Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd disability-schemes-chatbot
   ```

2. **Set up Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Copy `.env.example` to `.env` and fill in your API keys (e.g., `GROQ_API_KEY`).

5. **Update Knowledge Base**:
   Run the batch file to scrape data and build the vector store:
   ```bash
   run_updates.bat
   # Or run manually: python scripts/update_all.py
   ```

6. **Run the Application**:
   ```bash
   streamlit run chatbot/app.py
   ```

## 📦 Version Information

- **Project Version**: 1.0.0
- **LLM**: Llama-3.1-8b-instant
- **Embeddings**: all-MiniLM-L6-v2

## 📞 Support Helpline
For immediate assistance, the official helpline is **1800-111-555**.
