#!/usr/bin/env python3
"""
Hippoclaudus Conversation Scanner — Pass 1
Scans a Claude conversations.json export and produces a lightweight index.
Extracts: title, dates, message count, first few human messages as topic indicators.

Pass 2: Once you identify high-value conversations from the index,
run extract_conversations.py to pull specific ones into individual files.

Usage: python3 scan_conversations.py

Customize HIGH_VALUE_KEYWORDS below with terms relevant to YOUR work.
"""

import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "conversations.json")
INDEX_FILE = os.path.join(SCRIPT_DIR, "conversation_index.json")
INDEX_READABLE = os.path.join(SCRIPT_DIR, "conversation_index.md")

# ============================================================
# CUSTOMIZE THESE: Keywords that signal high-value conversations
# for YOUR specific work. Add project names, people, technical
# terms, business concepts — anything you'd want to find later.
# ============================================================
HIGH_VALUE_KEYWORDS = [
    # Projects (replace with yours)
    "project alpha", "redesign", "migration",
    # People (replace with yours)
    "alice", "bob",
    # Technical terms
    "architecture", "deployment", "database", "api",
    # Business/strategy
    "launch", "pricing", "partnership", "strategy",
    # Meta/memory
    "memory", "mcp", "identity", "persistence",
    # Key decisions
    "decision", "pivot", "restructur",
]


def extract_topic_keywords(text, keywords=HIGH_VALUE_KEYWORDS):
    """Find which high-value keywords appear in text."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def get_first_human_messages(messages, n=3):
    """Extract first N human messages as topic indicators."""
    human_msgs = []
    for msg in messages:
        if msg.get("sender") == "human" and msg.get("text"):
            text = msg["text"][:300].strip()
            if text:
                human_msgs.append(text)
            if len(human_msgs) >= n:
                break
    return human_msgs


def count_messages(messages):
    """Count human and assistant messages."""
    human = sum(1 for m in messages if m.get("sender") == "human")
    assistant = sum(1 for m in messages if m.get("sender") == "assistant")
    return {"human": human, "assistant": assistant, "total": len(messages)}


def estimate_conversation_size(messages):
    """Estimate total text size in characters."""
    return sum(len(m.get("text", "")) for m in messages if m.get("text"))


def scan_conversations():
    print(f"Loading {INPUT_FILE}...")
    print(f"File size: {os.path.getsize(INPUT_FILE) / 1024 / 1024:.1f} MB")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle different JSON structures from Claude exports
    if isinstance(data, list):
        conversations = data
    elif isinstance(data, dict):
        for key in ["conversations", "data", "items", "results"]:
            if key in data:
                conversations = data[key]
                break
        else:
            conversations = list(data.values()) if all(
                isinstance(v, dict) for v in list(data.values())[:5]
            ) else [data]
    else:
        print(f"Unexpected JSON type: {type(data)}")
        return

    print(f"Found {len(conversations)} conversations")

    index = []

    for i, conv in enumerate(conversations):
        if i % 50 == 0 and i > 0:
            print(f"  Scanning conversation {i}/{len(conversations)}...")

        entry = {
            "index": i,
            "uuid": conv.get("uuid", conv.get("id", conv.get("conversation_id", f"conv_{i}"))),
            "title": conv.get("name", conv.get("title", conv.get("summary", "Untitled"))),
            "created": conv.get("created_at", conv.get("created", "")),
            "updated": conv.get("updated_at", conv.get("updated", "")),
        }

        messages = conv.get("chat_messages", conv.get("messages", conv.get("turns", [])))

        if messages:
            entry["message_counts"] = count_messages(messages)
            entry["char_size"] = estimate_conversation_size(messages)
            entry["first_human_messages"] = get_first_human_messages(messages)

            # Sample first + last 5 messages for keyword scanning
            sample_messages = messages[:5] + messages[-5:] if len(messages) > 10 else messages
            full_sample = " ".join(m.get("text", "") for m in sample_messages if m.get("text"))

            scan_text = (entry["title"] or "") + " " + full_sample
            entry["keywords_found"] = extract_topic_keywords(scan_text)
            entry["keyword_count"] = len(entry["keywords_found"])
        else:
            entry["message_counts"] = {"human": 0, "assistant": 0, "total": 0}
            entry["char_size"] = 0
            entry["first_human_messages"] = []
            entry["keywords_found"] = extract_topic_keywords(entry.get("title", ""))
            entry["keyword_count"] = len(entry["keywords_found"])

        index.append(entry)

    # Sort by keyword relevance
    index.sort(key=lambda x: (-x["keyword_count"], x.get("updated", "") or ""))

    high_value = [e for e in index if e["keyword_count"] >= 2]
    medium_value = [e for e in index if e["keyword_count"] == 1]
    low_value = [e for e in index if e["keyword_count"] == 0]

    # Save JSON index
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "scan_date": datetime.now().isoformat(),
            "total_conversations": len(index),
            "high_value_count": len(high_value),
            "medium_value_count": len(medium_value),
            "low_value_count": len(low_value),
            "high_value": high_value,
            "medium_value": medium_value,
            "low_value_summary": [
                {"index": e["index"], "title": e["title"], "updated": e.get("updated", "")}
                for e in low_value
            ],
        }, f, indent=2, default=str)

    # Save readable markdown index
    with open(INDEX_READABLE, "w", encoding="utf-8") as f:
        f.write("# Conversation History Index\n\n")
        f.write(f"Scanned: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Total conversations: {len(index)}\n\n")

        f.write(f"## High Value ({len(high_value)} conversations, 2+ keyword matches)\n\n")
        for e in high_value:
            f.write(f"### [{e['index']}] {e['title']}\n")
            f.write(f"- **Updated:** {e.get('updated', 'unknown')}\n")
            f.write(f"- **Messages:** {e['message_counts']['total']} ({e['message_counts']['human']}H/{e['message_counts']['assistant']}A)\n")
            f.write(f"- **Size:** {e['char_size']:,} chars\n")
            f.write(f"- **Keywords:** {', '.join(e['keywords_found'])}\n")
            if e["first_human_messages"]:
                f.write(f"- **Opening:** {e['first_human_messages'][0][:200]}\n")
            f.write("\n")

        f.write(f"\n## Medium Value ({len(medium_value)} conversations, 1 keyword match)\n\n")
        for e in medium_value:
            f.write(f"- [{e['index']}] **{e['title']}** — {', '.join(e['keywords_found'])} — {e['message_counts']['total']} msgs\n")

        f.write(f"\n## Low Value ({len(low_value)} conversations, 0 keyword matches)\n\n")
        for e in low_value:
            f.write(f"- [{e['index']}] {e['title']}\n")

    print(f"\nResults:")
    print(f"  High value:   {len(high_value)} conversations")
    print(f"  Medium value: {len(medium_value)} conversations")
    print(f"  Low value:    {len(low_value)} conversations")
    print(f"\nIndex saved to:")
    print(f"  {INDEX_FILE}")
    print(f"  {INDEX_READABLE}")


if __name__ == "__main__":
    scan_conversations()
