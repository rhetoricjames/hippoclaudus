#!/usr/bin/env python3
"""
Hippoclaudus Conversation Extractor — Pass 2 (On-Demand)
Extracts specific conversations from conversations.json by index number.
Use after reviewing conversation_index.md to identify conversations worth reading.

Usage:
  python3 extract_conversations.py 12 45 78       # Extract specific indices
  python3 extract_conversations.py --range 10-20   # Extract a range
"""

import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "conversations.json")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "extracted")


def extract_conversation(conversations, idx):
    """Extract a single conversation and format as readable markdown."""
    if idx < 0 or idx >= len(conversations):
        print(f"  Index {idx} out of range (0-{len(conversations)-1})")
        return None

    conv = conversations[idx]
    title = conv.get("name", conv.get("title", conv.get("summary", "Untitled")))
    uuid = conv.get("uuid", conv.get("id", f"conv_{idx}"))
    created = conv.get("created_at", conv.get("created", "unknown"))
    updated = conv.get("updated_at", conv.get("updated", "unknown"))
    messages = conv.get("chat_messages", conv.get("messages", conv.get("turns", [])))

    lines = [
        f"# {title}",
        "",
        f"- **Index:** {idx}",
        f"- **UUID:** {uuid}",
        f"- **Created:** {created}",
        f"- **Updated:** {updated}",
        f"- **Messages:** {len(messages)}",
        "",
        "---",
        "",
    ]

    for msg in messages:
        sender = msg.get("sender", "unknown")
        text = msg.get("text", "")

        if sender == "human":
            lines.extend([f"## Human", "", text, ""])
        elif sender == "assistant":
            lines.extend([f"## Assistant", "", text, ""])
        else:
            lines.extend([f"## [{sender}]", "", text, ""])

    return "\n".join(lines)


def sanitize_filename(title, idx):
    """Create a safe filename from conversation title."""
    safe = re.sub(r'[^\w\s-]', '', title or "untitled")
    safe = re.sub(r'\s+', '_', safe.strip())
    safe = safe[:80]
    return f"{idx:04d}_{safe}.md"


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 extract_conversations.py 12 45 78       # Specific indices")
        print("  python3 extract_conversations.py --range 10-20   # Range of indices")
        sys.exit(1)

    # Parse arguments
    indices = []
    if sys.argv[1] == "--range":
        start, end = map(int, sys.argv[2].split("-"))
        indices = list(range(start, end + 1))
    else:
        indices = [int(x) for x in sys.argv[1:]]

    print(f"Loading {INPUT_FILE}...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle different JSON structures
    if isinstance(data, list):
        conversations = data
    elif isinstance(data, dict):
        for key in ["conversations", "data", "items", "results"]:
            if key in data:
                conversations = data[key]
                break
        else:
            conversations = list(data.values())

    print(f"Total conversations: {len(conversations)}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for idx in indices:
        print(f"  Extracting [{idx}]...")
        content = extract_conversation(conversations, idx)
        if content:
            title = conversations[idx].get(
                "name", conversations[idx].get("title", "untitled")
            )
            filename = sanitize_filename(title, idx)
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            size_kb = os.path.getsize(filepath) / 1024
            print(f"    Saved: {filename} ({size_kb:.1f} KB)")

    print(f"\nExtracted {len(indices)} conversations to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
