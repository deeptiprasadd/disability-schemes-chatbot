import os
import json
import re

KB_DIR = "knowledge-base"
OUTPUT_FILE = "scripts/finetune_dataset.jsonl"

def parse_markdown_blocks(content):
    # Split content by '---' to handle files with multiple schemes
    blocks = re.split(r'\n---+\n', content)
    cleaned_blocks = []
    for b in blocks:
        if b.strip():
            cleaned_blocks.append(b.strip())
    return cleaned_blocks

def extract_scheme_name(block):
    # Try to find scheme_name in frontmatter
    match = re.search(r'scheme_name:\s*"(.*?)"', block)
    if not match:
        match = re.search(r'scheme_name:\s*(.*)', block)
    
    if match:
        return match.group(1).strip()
    
    # Fallback to first H1 or H2
    match = re.search(r'#+\s*(.*)', block)
    if match:
        return match.group(1).strip()
    
    return "this scheme"

def extract_section(block, section_name):
    # Extract content under a specific ## header
    pattern = rf'## {section_name}(.*?)(?=\n##|$)'
    match = re.search(pattern, block, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def run():
    print(f"Scanning {KB_DIR} for markdown files...")
    dataset = []
    
    for root, _, files in os.walk(KB_DIR):
        for file in files:
            if file.endswith(".md"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                blocks = parse_markdown_blocks(content)
                for block in blocks:
                    scheme_name = extract_scheme_name(block)
                    
                    # 1. General Info pair
                    dataset.append({
                        "instruction": f"Provide a detailed overview of the {scheme_name}.",
                        "input": "",
                        "output": block
                    })
                    
                    # 2. Benefits pair
                    benefits = extract_section(block, "Benefits")
                    if benefits:
                        dataset.append({
                            "instruction": f"What are the benefits provided under the {scheme_name}?",
                            "input": "",
                            "output": f"The benefits for {scheme_name} include:\n{benefits}"
                        })
                    
                    # 3. Eligibility pair
                    eligibility = extract_section(block, "Eligibility criteria")
                    if eligibility:
                        dataset.append({
                            "instruction": f"Who is eligible for the {scheme_name} in India?",
                            "input": "",
                            "output": f"The eligibility criteria for {scheme_name} are as follows:\n{eligibility}"
                        })

    print(f"Generated {len(dataset)} instruction pairs.")
    
    print(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    print("Done! You can now use this JSONL file with Unsloth or other fine-tuning tools.")

if __name__ == "__main__":
    run()
