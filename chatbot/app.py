import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.rag_pipeline import ask
from scripts.translate import (
    detect_and_translate_to_english,
    translate_to_language,
    SUPPORTED_LANGUAGES
)

# --- Page config ---
st.set_page_config(
    page_title="Disability Schemes Assistant",
    page_icon="♿",
    layout="centered"
)

st.title("♿ Disability Schemes Assistant")
st.caption("Ask about government schemes for persons with disabilities in India — in any language.")

# --- Language selector ---
lang_name = st.selectbox(
    "Choose your language / अपनी भाषा चुनें",
    options=list(SUPPORTED_LANGUAGES.keys()),
    index=0
)
lang_code = SUPPORTED_LANGUAGES[lang_name]

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- User input ---
user_input = st.chat_input("Ask your question here...")

if user_input:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Looking up schemes..."):
            # Step 1: Translate question to English
            english_question, detected_lang = detect_and_translate_to_english(user_input)

            # Step 2: Get answer from RAG pipeline
            result  = ask(english_question)
            answer  = result["answer"]
            sources = result["sources"]

            # Step 3: Translate answer back to user's language
            final_answer = translate_to_language(answer, lang_code)

            # Step 4: Display
            st.markdown(final_answer)

            # Show source files as expandable
            if sources:
                with st.expander("Sources from knowledge base"):
                    for s in sources:
                        st.write(f"- `{os.path.basename(s)}`")

    st.session_state.messages.append({"role": "assistant", "content": final_answer})

# --- Sidebar info ---
with st.sidebar:
    st.header("About")
    st.write("This assistant helps persons with disabilities find relevant government schemes.")
    st.write("**Knowledge base:** Auto-updated daily from official govt. portals.")
    st.markdown("---")
    st.write("**Key sources:**")
    st.write("- [DEPwD](https://depwd.gov.in)")
    st.write("- [UDID Portal](https://swavlambancard.gov.in)")
    st.write("- [National Scholarship Portal](https://scholarships.gov.in)")
    st.markdown("---")
    st.write("**Helpline:** 1800-111-555 (toll-free)")
