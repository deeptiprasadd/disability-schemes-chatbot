"""
Publish the app to a Hugging Face Space (Docker SDK).

Note: since mid-2026 Hugging Face requires a paid plan (PRO) for Docker
Spaces; the free recommended host is Render (see docs/DEPLOY.md). This script
is kept for anyone who has PRO.

From your PC (one time):
    venv\\Scripts\\pip install huggingface_hub
    venv\\Scripts\\hf auth login            (paste a token with WRITE access)
    venv\\Scripts\\python scripts\\deploy_space.py <your-username>/sneh-saathi

The Space builds the Dockerfile. GROQ_API_KEY must be added as a Space secret
(Space -> Settings -> Variables and secrets); pass --set-groq-secret to copy it
from your environment / .env instead.
"""

import os
import shutil
import sys
import tempfile

from huggingface_hub import HfApi

# Hugging Face reads this header from the Space's README to know how to build it.
SPACE_HEADER = """---
title: Sneh Saathi
emoji: ♿
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Government schemes and support for persons with disabilities
---

"""

# Not needed to run the app (and .env holds secrets: never upload it).
IGNORE = shutil.ignore_patterns(
    ".git", ".github", ".claude", "venv", ".venv", "__pycache__", "*.pyc", ".env",
    "test_output.txt", "research", "finetune_dataset.jsonl",
)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    space = args[0] if args else os.environ.get("HF_SPACE", "")
    if "/" not in space:
        sys.exit("Usage: python scripts/deploy_space.py <username>/<space-name>   (or set HF_SPACE)")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api = HfApi(token=os.environ.get("HF_TOKEN"))  # falls back to `hf auth login`
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)

    if "--set-groq-secret" in sys.argv:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root, ".env"))
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            sys.exit("GROQ_API_KEY not found in the environment or .env")
        api.add_space_secret(space, "GROQ_API_KEY", key)
        print("GROQ_API_KEY secret set on the Space.")

    # Stage a clean copy so the Space gets its own README header in ONE commit
    # (a separate README commit would trigger a build without the header).
    with tempfile.TemporaryDirectory() as tmp:
        stage = os.path.join(tmp, "space")
        shutil.copytree(root, stage, ignore=IGNORE)
        with open(os.path.join(root, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        with open(os.path.join(stage, "README.md"), "w", encoding="utf-8") as f:
            f.write(SPACE_HEADER + readme)
        api.upload_folder(
            folder_path=stage, repo_id=space, repo_type="space",
            commit_message="Deploy from GitHub", delete_patterns="*",  # drop files removed locally
        )

    user, name = space.split("/", 1)
    print(f"Uploaded. The Space builds in ~5-10 minutes:\n"
          f"  build logs: https://huggingface.co/spaces/{space}\n"
          f"  public app: https://{user.lower()}-{name.lower().replace('_', '-').replace('.', '-')}.hf.space")


if __name__ == "__main__":
    main()
