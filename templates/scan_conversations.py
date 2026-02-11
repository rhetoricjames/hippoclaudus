#!/usr/bin/env python3
"""
Hippoclaudus Conversation Scanner — Pass 1
Scans a Claude conversations.json export and produces a lightweight index.
Extracts: title, dates, message count, first few human messages as topic indicators.

Keywords are loaded from keywords.yaml if present, otherwise falls back to
built-in defaults. Each category is scored independently so the index shows
WHY a conversation ranked high, not just that it did.

Pass 2: Once you identify high-value conversations from the index,
run extract_conversations.py to pull specific ones into individual files.

Usage:
  python3 scan_conversations.py                    # Scan with default/yaml keywords
  python3 scan_conversations.py --search "database migration"  # Ad-hoc keyword search
"""

import argparse
import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "conversations.json")
INDEX_FILE = os.path.join(SCRIPT_DIR, "conversation_index.json")
INDEX_READABLE = os.path.join(SCRIPT_DIR, "conversation_index.md")
KEYWORDS_FILE = os.path.join(SCRIPT_DIR, "keywords.yaml")

# ============================================================
# FALLBACK KEYWORDS: Used only if keywords.yaml is not found.
# Prefer editing keywords.yaml instead of modifying these.
# ============================================================
FALLBACK_KEYWORDS = {
    "technical": ["architecture", "deployment", "database", "api", "migration", "refactor"],
    "decisions": ["decision", "pivot", "strategy", "restructur"],
    "relationships": ["alice", "bob"],
    "projects": ["project alpha", "redesign", "launch"],
    "milestones": ["shipped", "released", "completed", "milestone"],
    "meta": ["memory", "mcp", "identity", "persistence"],
}


def load_keywords():
    """Load keywords from keywords.yaml if available, else use fallback."""
    if os.path.exists(KEYWORDS_FILE):
        try:
            # Try yaml first
            import yaml
            with open(KEYWORDS_FILE, "r") as f:
                categories = yaml.safe_load(f)
            if isinstance(categories, dict):
                print(f"  Loaded keywords from {KEYWORDS_FILE}")
                return categories
        except ImportError:
            # No yaml module — parse it manually (it's simple enough)
            categories = {}
            current_category = None
            with open(KEYWORDS_FILE, "r") as f:
                for line in f:
                    line = line.rstrip()
                    # Skip comments and blank lines
                    if not line or line.lstrip().startswith("#"):
                        continue
                    # Category header: "technical:"
                    if not line.startswith(" ") and not line.startswith("-") and line.endswith(":"):
                        current_category = line[:-1].strip()
                        categories[current_category] = []
                    # Keyword entry: "  - architecture"
                    elif line.lstrip().startswith("- ") and current_category:
                        keyword = line.lstrip()[2:].strip()
                        # Strip inline comments
                        if " #" in keyword:
                            keyword = keyword[:keyword.index(" #")].strip()
                        if keyword:
                            categories[current_category].append(keyword)
            if categories:
                print(f"  Loaded keywords from {KEYWORDS_FILE} (parsed manually, no yaml module)")
                return categories
        except Exception as e:
            print(f"  Warning: Could not load {KEYWORDS_FILE}: {e}")

    print("  Using fallback keywords (create keywords.yaml to customize)")
    return FALLBACK_KEYWORDS


def extract_category_matches(text, keyword_categories):
    """Find keyword matches organized by category."""
    text_lower = text.lower()
    matches = {}
    flat_matches = []
    for category, keywords in keyword_categories.items():
        found = [kw for kw in keywords if kw.lower() in text_lower]
        if found:
            matches[category] = found
            flat_matches.extend(found)
    return matches, flat_matches


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


def load_conversations():
    """Load and parse the conversations.json file."""
    print(f"Loading {INPUT_FILE}...")
    print(f"File size: {os.path.getsize(INPUT_FILE) / 1024 / 1024:.1f} MB")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        for key in ["conversations", "data", "items", "results"]:
            if key in data:
                return data[key]
        return list(data.values()) if all(
            isinstance(v, dict) for v in list(data.values())[:5]
        ) else [data]
    else:
        print(f"Unexpected JSON type: {type(data)}")
        return []


def build_sample_text(conv, entry):
    """Build text sample from a conversation for keyword scanning."""
    messages = conv.get("chat_messages", conv.get("messages", conv.get("turns", [])))
    if not messages:
        return entry.get("title", ""), messages

    sample_messages = messages[:5] + messages[-5:] if len(messages) > 10 else messages
    full_sample = " ".join(m.get("text", "") for m in sample_messages if m.get("text"))
    scan_text = (entry["title"] or "") + " " + full_sample
    return scan_text, messages


def scan_conversations(keyword_categories):
    """Full scan: build a scored index of all conversations."""
    conversations = load_conversations()
    if not conversations:
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

            scan_text, _ = build_sample_text(conv, entry)
            category_matches, flat_matches = extract_category_matches(scan_text, keyword_categories)

            entry["category_matches"] = category_matches
            entry["keywords_found"] = flat_matches
            entry["keyword_count"] = len(flat_matches)
            entry["category_count"] = len(category_matches)
        else:
            entry["message_counts"] = {"human": 0, "assistant": 0, "total": 0}
            entry["char_size"] = 0
            entry["first_human_messages"] = []
            title_matches, title_flat = extract_category_matches(entry.get("title", ""), keyword_categories)
            entry["category_matches"] = title_matches
            entry["keywords_found"] = title_flat
            entry["keyword_count"] = len(title_flat)
            entry["category_count"] = len(title_matches)

        index.append(entry)

    # Sort by category breadth first, then keyword count, then recency
    index.sort(key=lambda x: (-x["category_count"], -x["keyword_count"], x.get("updated", "") or ""))

    high_value = [e for e in index if e["category_count"] >= 2]
    medium_value = [e for e in index if e["category_count"] == 1]
    low_value = [e for e in index if e["category_count"] == 0]

    # Save JSON index
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "scan_date": datetime.now().isoformat(),
            "total_conversations": len(index),
            "high_value_count": len(high_value),
            "medium_value_count": len(medium_value),
            "low_value_count": len(low_value),
            "keyword_categories": list(keyword_categories.keys()),
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
        f.write(f"Total conversations: {len(index)}\n")
        f.write(f"Keyword categories: {', '.join(keyword_categories.keys())}\n\n")

        f.write(f"## High Value ({len(high_value)} conversations, 2+ category matches)\n\n")
        for e in high_value:
            f.write(f"### [{e['index']}] {e['title']}\n")
            f.write(f"- **Updated:** {e.get('updated', 'unknown')}\n")
            f.write(f"- **Messages:** {e['message_counts']['total']} ({e['message_counts']['human']}H/{e['message_counts']['assistant']}A)\n")
            f.write(f"- **Size:** {e['char_size']:,} chars\n")
            # Show matches by category
            for cat, kws in e.get("category_matches", {}).items():
                f.write(f"- **{cat}:** {', '.join(kws)}\n")
            if e["first_human_messages"]:
                f.write(f"- **Opening:** {e['first_human_messages'][0][:200]}\n")
            f.write("\n")

        f.write(f"\n## Medium Value ({len(medium_value)} conversations, 1 category match)\n\n")
        for e in medium_value:
            cats = ", ".join(f"{cat}: {', '.join(kws)}" for cat, kws in e.get("category_matches", {}).items())
            f.write(f"- [{e['index']}] **{e['title']}** — {cats} — {e['message_counts']['total']} msgs\n")

        f.write(f"\n## Low Value ({len(low_value)} conversations, 0 category matches)\n\n")
        for e in low_value:
            f.write(f"- [{e['index']}] {e['title']}\n")

    print(f"\nResults:")
    print(f"  High value:   {len(high_value)} conversations (2+ categories)")
    print(f"  Medium value: {len(medium_value)} conversations (1 category)")
    print(f"  Low value:    {len(low_value)} conversations (0 categories)")
    print(f"\nIndex saved to:")
    print(f"  {INDEX_FILE}")
    print(f"  {INDEX_READABLE}")


def search_conversations(search_terms, keyword_categories):
    """Ad-hoc search: find conversations matching specific terms."""
    conversations = load_conversations()
    if not conversations:
        return

    print(f"Found {len(conversations)} conversations")
    print(f"Searching for: {', '.join(search_terms)}")

    # Create a temporary category for the search terms
    search_categories = {"search": search_terms}
    # Also include regular categories for context
    search_categories.update(keyword_categories)

    results = []
    for i, conv in enumerate(conversations):
        entry = {
            "index": i,
            "title": conv.get("name", conv.get("title", conv.get("summary", "Untitled"))),
            "updated": conv.get("updated_at", conv.get("updated", "")),
        }

        messages = conv.get("chat_messages", conv.get("messages", conv.get("turns", [])))
        if messages:
            entry["message_counts"] = count_messages(messages)
            # For search, scan ALL messages, not just a sample
            all_text = " ".join(m.get("text", "") for m in messages if m.get("text"))
            scan_text = (entry["title"] or "") + " " + all_text

            # Check if ANY search term matches
            text_lower = scan_text.lower()
            found_terms = [t for t in search_terms if t.lower() in text_lower]
            if found_terms:
                entry["matched_terms"] = found_terms
                entry["match_count"] = len(found_terms)
                entry["first_human_messages"] = get_first_human_messages(messages, n=2)
                results.append(entry)
        else:
            entry["message_counts"] = {"human": 0, "assistant": 0, "total": 0}

    results.sort(key=lambda x: (-x["match_count"], x.get("updated", "") or ""))

    print(f"\nFound {len(results)} matching conversations:\n")
    for r in results[:30]:  # Cap at 30 results
        terms = ", ".join(r["matched_terms"])
        msgs = r["message_counts"]["total"]
        print(f"  [{r['index']}] {r['title']}")
        print(f"       Matched: {terms} | {msgs} msgs | Updated: {r.get('updated', 'unknown')}")
        if r.get("first_human_messages"):
            print(f"       Opening: {r['first_human_messages'][0][:120]}")
        print()

    if len(results) > 30:
        print(f"  ... and {len(results) - 30} more. Refine your search terms.")

    print(f"\nTo extract: python3 extract_conversations.py {' '.join(str(r['index']) for r in results[:5])}")


def main():
    parser = argparse.ArgumentParser(description="Hippoclaudus Conversation Scanner")
    parser.add_argument("--search", nargs="+", help="Ad-hoc search for specific terms")
    args = parser.parse_args()

    keyword_categories = load_keywords()

    if args.search:
        search_conversations(args.search, keyword_categories)
    else:
        scan_conversations(keyword_categories)


if __name__ == "__main__":
    main()
