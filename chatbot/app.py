import streamlit as st
import sys, os
from streamlit_mic_recorder import mic_recorder, speech_to_text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.rag_pipeline import ask
from chatbot.language_utils import (
    translate_to_english,
    translate_to_language,
    SUPPORTED_LANGUAGES
)

st.set_page_config(
    page_title="Disability Schemes Assistant",
    page_icon="♿",
    layout="wide"
)

# Custom CSS for better aesthetics
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stChatMessage {
        border-radius: 15px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .source-tag {
        font-size: 0.8rem;
        color: #6c757d;
        background: #e9ecef;
        padding: 2px 8px;
        border-radius: 10px;
        margin-right: 5px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("♿ Disability Schemes Assistant (Advanced)")
st.caption("Ask about government welfare schemes in India. Optimized for GPU & Hybrid Search.")

# Language Selection
with st.sidebar:
    st.header("⚙️ Settings")
    lang_name = st.selectbox(
        "Preferred Language",
        options=list(SUPPORTED_LANGUAGES.keys()),
        index=0
    )
    lang_code = SUPPORTED_LANGUAGES[lang_name]
    
    st.markdown("---")
    st.header("🎙️ Voice Search")
    # Voice search component
    voice_text = speech_to_text(
        language=lang_code, 
        start_prompt="Click to Speak",
        stop_prompt="Stop Recording",
        just_once=True,
        key='speech'
    )

    st.markdown("---")
    st.header("ℹ️ About")
    st.info("Using Hybrid Search (Semantic + Keyword) with FlashRank reranking for maximum accuracy.")
    st.write("🔥 **GPU-accelerated** pipeline.")

# Session State for History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            sources_html = "".join([f'<span class="source-tag">{s}</span>' for s in msg["sources"]])
            st.markdown(f"**Sources:** {sources_html}", unsafe_allow_html=True)

# Input logic
user_input = st.chat_input("Ask your question here...")

# If voice input was detected, use it as the user_input
if voice_text:
    user_input = voice_text

if user_input:
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Processing your request with advanced retrieval..."):

            # Translate to English for retrieval
            english_question, detected_lang = translate_to_english(user_input)

            # Get answer from the pipeline (passing history!)
            result = ask(english_question, chat_history=st.session_state.messages[:-1])
            answer = result["answer"]
            sources = result["sources"]

            # Translate back to user's language
            final_answer = translate_to_language(answer, lang_code)

            st.markdown(final_answer)
            
            if sources:
                sources_html = "".join([f'<span class="source-tag">{s}</span>' for s in sources])
                st.markdown(f"**Sources:** {sources_html}", unsafe_allow_html=True)

    # Save to history
    st.session_state.messages.append({
        "role": "assistant",
        "content": final_answer,
        "sources": sources
    })