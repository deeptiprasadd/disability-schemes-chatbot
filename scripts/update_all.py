import subprocess
import sys
import os

def run_script(script_path):
    print(f"\n--- Running {script_path} ---")
    # Use the current python interpreter (which should be in venv if run via bat)
    result = subprocess.run([sys.executable, script_path], capture_output=False)
    if result.returncode != 0:
        print(f"Error running {script_path}")
        return False
    return True

def main():
    # 1. Scrape new schemes
    if not run_script("scripts/scrape_schemes.py"):
        print("Scraping failed. Stopping.")
        return

    # 2. Update vector store
    if not run_script("scripts/embed_docs.py"):
        print("Embedding failed. Stopping.")
        return

    print("\n✅ Knowledge base successfully updated and re-indexed!")

if __name__ == "__main__":
    # Ensure current directory is the project root
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
