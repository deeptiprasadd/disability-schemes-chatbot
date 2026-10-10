import sys
import os

# Add the project root to sys.path (must happen before importing chatbot)
sys.path.append(os.getcwd())

from chatbot.rag_pipeline import ask  # noqa: E402

def test():
    question = "my kid is mentally disabled and cannot study, what benefits can I get as money or schemes?"
    print(f"Testing Question: {question}")
    
    result = ask(question)
    
    print("\n--- Assistant Answer ---")
    print(result["answer"])
    print("\n--- Sources Used ---")
    print(result["sources"])

    # Basic verification
    answer_lower = result["answer"].lower()
    if not answer_lower.strip():
        # An empty answer trivially contains no scholarships — that is a failure, not a pass.
        print("\n❌ Verification FAILURE: The model returned an empty answer.")
    elif "scholarship" in answer_lower or "student" in answer_lower:
        if "since your child cannot pursue education" in answer_lower:
             print("\n✅ Verification SUCCESS: Model acknowledged the non-student status.")
        else:
             print("\n❌ Verification FAILURE: Model still recommended educational benefits inappropriately.")
    else:
        print("\n✅ Verification SUCCESS: No educational benefits found in the answer.")

if __name__ == "__main__":
    test()
