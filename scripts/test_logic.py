from chatbot.rag_pipeline import ask
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

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
    if "scholarship" in answer_lower or "student" in answer_lower:
        if "since your child cannot pursue education" in answer_lower:
             print("\n✅ Verification SUCCESS: Model acknowledged the non-student status.")
        else:
             print("\n❌ Verification FAILURE: Model still recommended educational benefits inappropriately.")
    else:
        print("\n✅ Verification SUCCESS: No educational benefits found in the answer.")

if __name__ == "__main__":
    test()
