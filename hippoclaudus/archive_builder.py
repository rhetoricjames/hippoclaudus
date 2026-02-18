"""Archive Builder — incremental conversation archive from JSONL session transcripts.

Hippoclaudus v4.1: Replaces manual Anthropic export dependency with automatic
local ingestion. Reads Claude Code session transcripts from ~/.claude/projects/,
parses messages, stores to SQLite archive with keyword indexing.

Also migrates the legacy conversations.json bulk export for full history.
"""

import hashlib
import json
import math
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# --- Default Paths ---

DEFAULT_ARCHIVE_DB = Path.home() / "Desktop/Claude/mcp-memory/data/conversations_archive.db"
DEFAULT_PROJECTS_DIR = Path.home() / ".claude/projects"
DEFAULT_LEGACY_JSON = Path.home() / "Desktop/Claude/mcp-memory/Conversations_Feb_7_26/conversations.json"


# --- Schema ---

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'jsonl',
    project_hash TEXT,
    name TEXT,
    summary TEXT,
    started_at TEXT,
    ended_at TEXT,
    message_count INTEGER DEFAULT 0,
    user_message_count INTEGER DEFAULT 0,
    assistant_message_count INTEGER DEFAULT 0,
    topics TEXT DEFAULT '[]',
    entities TEXT DEFAULT '[]',
    files_touched TEXT DEFAULT '[]',
    raw_path TEXT,
    ingested_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT REFERENCES conversations(id),
    role TEXT,
    content TEXT,
    timestamp TEXT,
    message_index INTEGER,
    has_tool_calls BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conversation_keywords (
    conversation_id TEXT REFERENCES conversations(id),
    keyword TEXT,
    frequency INTEGER,
    tf_idf_score REAL DEFAULT 0.0,
    PRIMARY KEY (conversation_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_keywords ON conversation_keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_conversations_date ON conversations(started_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_source ON conversations(source);
"""


# --- Stop words for keyword extraction ---

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "is", "it", "this", "that", "are", "was", "were", "be",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "can", "not", "no", "so", "if", "then", "than", "too", "very",
    "just", "about", "up", "out", "all", "also", "as", "into", "more", "some",
    "what", "when", "where", "which", "who", "how", "why", "each", "every",
    "both", "few", "many", "much", "most", "other", "such", "only", "own", "same",
    "here", "there", "these", "those", "them", "their", "its", "my", "your", "our",
    "his", "her", "we", "they", "i", "you", "he", "she", "me", "him", "us",
    "been", "being", "get", "got", "let", "like", "make", "made", "say", "said",
    "see", "seen", "go", "going", "gone", "come", "take", "think", "know", "want",
    "one", "two", "well", "now", "way", "even", "new", "because", "any", "give",
    "use", "her", "right", "look", "still", "try", "back", "thing", "over",
}


class ConversationArchive:
    """SQLite-backed conversation archive with keyword indexing."""

    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_ARCHIVE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # --- Check if already ingested ---

    def is_ingested(self, conversation_id: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        )
        return cursor.fetchone() is not None

    # --- JSONL Ingestion (Claude Code transcripts) ---

    def ingest_session(self, jsonl_path: str) -> Optional[str]:
        """Parse a JSONL session transcript and store to archive.

        Returns conversation ID if ingested, None if skipped (already exists).
        """
        path = Path(jsonl_path)
        if not path.exists():
            return None

        # Session ID is the filename without extension
        session_id = path.stem

        # Skip if already ingested
        if self.is_ingested(session_id):
            return None

        # Parse the JSONL
        messages = []
        timestamps = []
        files_touched = set()
        has_any_content = False

        for line in path.open("r", encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            timestamp = entry.get("timestamp")

            if entry_type in ("user", "assistant"):
                msg = entry.get("message", {})
                role = msg.get("role", entry_type)
                content_parts = msg.get("content", "")

                # Extract text content
                if isinstance(content_parts, str):
                    text = content_parts
                    has_tools = False
                elif isinstance(content_parts, list):
                    text_parts = []
                    has_tools = False
                    for part in content_parts:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                            elif part.get("type") == "tool_use":
                                has_tools = True
                                # Track files from tool calls
                                tool_input = part.get("input", {})
                                for key in ("file_path", "path", "jsonl_path"):
                                    if key in tool_input:
                                        files_touched.add(tool_input[key])
                        elif isinstance(part, str):
                            text_parts.append(part)
                    text = "\n".join(text_parts)
                else:
                    text = str(content_parts)
                    has_tools = False

                if text.strip():
                    has_any_content = True

                messages.append({
                    "role": role,
                    "content": text,
                    "timestamp": timestamp,
                    "has_tool_calls": has_tools,
                })

                if timestamp:
                    timestamps.append(timestamp)

        # Skip empty sessions
        if not has_any_content or len(messages) < 2:
            return None

        # Determine project hash from path
        project_hash = path.parent.name if path.parent != Path.home() else None

        # Compute time range
        started_at = min(timestamps) if timestamps else None
        ended_at = max(timestamps) if timestamps else None

        user_count = sum(1 for m in messages if m["role"] == "user")
        assistant_count = sum(1 for m in messages if m["role"] == "assistant")

        # Generate name from first user message
        first_user_msg = next(
            (m["content"] for m in messages if m["role"] == "user" and m["content"].strip()),
            "Untitled session"
        )
        name = first_user_msg[:100].strip()
        if len(first_user_msg) > 100:
            name += "..."

        # Store conversation
        self.conn.execute(
            """INSERT INTO conversations
               (id, source, project_hash, name, started_at, ended_at,
                message_count, user_message_count, assistant_message_count,
                files_touched, raw_path)
               VALUES (?, 'jsonl', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id, project_hash, name, started_at, ended_at,
                len(messages), user_count, assistant_count,
                json.dumps(list(files_touched)), str(path),
            ),
        )

        # Store messages
        for idx, msg in enumerate(messages):
            self.conn.execute(
                """INSERT INTO messages
                   (conversation_id, role, content, timestamp, message_index, has_tool_calls)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, msg["role"], msg["content"], msg["timestamp"], idx, msg["has_tool_calls"]),
            )

        self.conn.commit()

        # Build keyword index for this conversation
        self._index_conversation_keywords(session_id, messages)

        return session_id

    def ingest_project_sessions(self, project_path: str, since: datetime = None) -> list[str]:
        """Ingest all JSONL session files from a project directory.

        If `since` provided, only ingest sessions modified after that time.
        Returns list of newly ingested conversation IDs.
        """
        project_dir = Path(project_path)
        if not project_dir.exists():
            return []

        ingested = []
        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            if since:
                mod_time = datetime.fromtimestamp(jsonl_file.stat().st_mtime, tz=timezone.utc)
                if mod_time < since:
                    continue

            result = self.ingest_session(str(jsonl_file))
            if result:
                ingested.append(result)

        return ingested

    def ingest_all_projects(self, projects_dir: str = None, since: datetime = None) -> dict:
        """Scan all projects under ~/.claude/projects/ and ingest new sessions.

        Returns summary: {project_name: [conversation_ids]}.
        """
        base = Path(projects_dir) if projects_dir else DEFAULT_PROJECTS_DIR
        if not base.exists():
            return {}

        results = {}
        for project_dir in sorted(base.iterdir()):
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue

            ingested = self.ingest_project_sessions(str(project_dir), since)
            if ingested:
                results[project_dir.name] = ingested

        return results

    # --- Legacy conversations.json Migration ---

    def migrate_legacy_archive(self, json_path: str = None) -> int:
        """Import conversations.json bulk export into the new archive.

        Returns number of conversations imported.
        """
        path = Path(json_path) if json_path else DEFAULT_LEGACY_JSON
        if not path.exists():
            print(f"Legacy archive not found: {path}")
            return 0

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"Unexpected format: expected list, got {type(data).__name__}")
            return 0

        imported = 0
        for conv in data:
            conv_id = conv.get("uuid", "")
            if not conv_id or self.is_ingested(conv_id):
                continue

            chat_messages = conv.get("chat_messages", [])
            name = conv.get("name", "Untitled")
            summary = conv.get("summary", "")
            created_at = conv.get("created_at")
            updated_at = conv.get("updated_at")

            user_count = sum(1 for m in chat_messages if m.get("sender") == "human")
            assistant_count = sum(1 for m in chat_messages if m.get("sender") == "assistant")

            self.conn.execute(
                """INSERT INTO conversations
                   (id, source, name, summary, started_at, ended_at,
                    message_count, user_message_count, assistant_message_count)
                   VALUES (?, 'legacy', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    conv_id, name, summary, created_at, updated_at,
                    len(chat_messages), user_count, assistant_count,
                ),
            )

            # Store messages
            for idx, msg in enumerate(chat_messages):
                role = msg.get("sender", "unknown")
                # Map legacy sender names
                if role == "human":
                    role = "user"
                text = msg.get("text", "")
                ts = msg.get("created_at")

                self.conn.execute(
                    """INSERT INTO messages
                       (conversation_id, role, content, timestamp, message_index)
                       VALUES (?, ?, ?, ?, ?)""",
                    (conv_id, role, text, ts, idx),
                )

            self.conn.commit()

            # Build keyword index
            messages_for_index = [
                {"role": m.get("sender", ""), "content": m.get("text", "")}
                for m in chat_messages
            ]
            self._index_conversation_keywords(conv_id, messages_for_index)

            imported += 1

        return imported

    # --- Keyword Indexing ---

    def _extract_keywords(self, text: str) -> Counter:
        """Extract meaningful keywords from text."""
        # Lowercase, split on non-alphanumeric
        words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{2,}', text.lower())
        # Filter stop words and very short words
        meaningful = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        return Counter(meaningful)

    def _index_conversation_keywords(self, conversation_id: str, messages: list[dict]):
        """Build keyword index for a single conversation."""
        all_text = " ".join(m.get("content", "") for m in messages)
        keywords = self._extract_keywords(all_text)

        if not keywords:
            return

        # Store top keywords (limit to avoid noise)
        top_keywords = keywords.most_common(50)
        for keyword, freq in top_keywords:
            self.conn.execute(
                """INSERT OR REPLACE INTO conversation_keywords
                   (conversation_id, keyword, frequency)
                   VALUES (?, ?, ?)""",
                (conversation_id, keyword, freq),
            )

        self.conn.commit()

    def rebuild_tfidf(self):
        """Rebuild TF-IDF scores across all conversations.

        TF = frequency in this conversation / total words in this conversation
        IDF = log(total conversations / conversations containing this keyword)
        """
        total_convos = self.conn.execute(
            "SELECT COUNT(*) FROM conversations"
        ).fetchone()[0]

        if total_convos == 0:
            return

        # Get document frequency for each keyword
        doc_freq = {}
        cursor = self.conn.execute(
            "SELECT keyword, COUNT(DISTINCT conversation_id) as df FROM conversation_keywords GROUP BY keyword"
        )
        for row in cursor:
            doc_freq[row["keyword"]] = row["df"]

        # Get all keyword entries
        cursor = self.conn.execute(
            "SELECT conversation_id, keyword, frequency FROM conversation_keywords"
        )
        updates = []
        for row in cursor:
            keyword = row["keyword"]
            tf = row["frequency"]  # Raw frequency as TF (simple but effective)
            idf = math.log(total_convos / doc_freq.get(keyword, 1))
            tfidf = tf * idf
            updates.append((tfidf, row["conversation_id"], keyword))

        # Batch update
        self.conn.executemany(
            "UPDATE conversation_keywords SET tf_idf_score = ? WHERE conversation_id = ? AND keyword = ?",
            updates,
        )
        self.conn.commit()

    # --- Search ---

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Keyword search across conversation archive.

        Returns matching conversations with relevance scores.
        """
        query_words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{2,}', query.lower())
        query_words = [w for w in query_words if w not in STOP_WORDS]

        if not query_words:
            return []

        placeholders = ",".join("?" * len(query_words))
        cursor = self.conn.execute(
            f"""SELECT c.id, c.name, c.source, c.started_at, c.ended_at,
                       c.message_count, c.summary,
                       SUM(ck.tf_idf_score) as relevance,
                       COUNT(DISTINCT ck.keyword) as matched_keywords
                FROM conversation_keywords ck
                JOIN conversations c ON c.id = ck.conversation_id
                WHERE ck.keyword IN ({placeholders})
                GROUP BY c.id
                ORDER BY relevance DESC
                LIMIT ?""",
            (*query_words, limit),
        )

        results = []
        for row in cursor:
            results.append({
                "id": row["id"],
                "name": row["name"],
                "source": row["source"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "message_count": row["message_count"],
                "summary": row["summary"],
                "relevance": round(row["relevance"], 3),
                "matched_keywords": row["matched_keywords"],
            })

        return results

    # --- Export ---

    def export_conversation(self, conversation_id: str, format: str = "markdown") -> Optional[str]:
        """Export a single conversation in readable format."""
        conv = self.conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()

        if not conv:
            return None

        messages = self.conn.execute(
            """SELECT role, content, timestamp FROM messages
               WHERE conversation_id = ?
               ORDER BY message_index""",
            (conversation_id,),
        ).fetchall()

        if format == "markdown":
            lines = [
                f"# {conv['name']}",
                f"",
                f"**Source:** {conv['source']}",
                f"**Date:** {conv['started_at']} → {conv['ended_at']}",
                f"**Messages:** {conv['message_count']}",
            ]
            if conv["summary"]:
                lines.append(f"**Summary:** {conv['summary']}")
            lines.append("")
            lines.append("---")
            lines.append("")

            for msg in messages:
                role_label = "**James:**" if msg["role"] == "user" else "**Claude:**"
                content = msg["content"] or "(no text)"
                # Truncate very long messages for readability
                if len(content) > 2000:
                    content = content[:2000] + "\n\n*[truncated]*"
                lines.append(f"{role_label}")
                lines.append(f"{content}")
                lines.append("")

            return "\n".join(lines)

        elif format == "json":
            return json.dumps({
                "id": conv["id"],
                "name": conv["name"],
                "source": conv["source"],
                "started_at": conv["started_at"],
                "ended_at": conv["ended_at"],
                "messages": [
                    {"role": m["role"], "content": m["content"], "timestamp": m["timestamp"]}
                    for m in messages
                ],
            }, indent=2)

        return None

    # --- Stats ---

    def get_stats(self) -> dict:
        """Return archive health info."""
        total = self.conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        legacy = self.conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE source = 'legacy'"
        ).fetchone()[0]
        jsonl = self.conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE source = 'jsonl'"
        ).fetchone()[0]

        date_range = self.conn.execute(
            "SELECT MIN(started_at), MAX(ended_at) FROM conversations"
        ).fetchone()

        total_messages = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        total_keywords = self.conn.execute(
            "SELECT COUNT(DISTINCT keyword) FROM conversation_keywords"
        ).fetchone()[0]

        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "total_conversations": total,
            "legacy_conversations": legacy,
            "jsonl_conversations": jsonl,
            "total_messages": total_messages,
            "unique_keywords": total_keywords,
            "earliest": date_range[0],
            "latest": date_range[1],
            "db_size_mb": round(db_size / (1024 * 1024), 2),
        }


# --- CLI Entry Point ---

def main():
    """Simple CLI for archive operations."""
    import argparse

    parser = argparse.ArgumentParser(description="Hippoclaudus Conversation Archive Builder")
    sub = parser.add_subparsers(dest="command")

    # ingest
    ingest_parser = sub.add_parser("ingest", help="Ingest JSONL session transcripts")
    ingest_parser.add_argument("--project", help="Specific project directory")
    ingest_parser.add_argument("--since", help="Only sessions since date (YYYY-MM-DD)")
    ingest_parser.add_argument("--db", help="Archive database path")

    # migrate
    migrate_parser = sub.add_parser("migrate", help="Import legacy conversations.json")
    migrate_parser.add_argument("--json", help="Path to conversations.json")
    migrate_parser.add_argument("--db", help="Archive database path")

    # search
    search_parser = sub.add_parser("search", help="Search conversation archive")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--db", help="Archive database path")

    # export
    export_parser = sub.add_parser("export", help="Export a conversation")
    export_parser.add_argument("conversation_id", help="Conversation UUID")
    export_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    export_parser.add_argument("--db", help="Archive database path")

    # status
    status_parser = sub.add_parser("status", help="Archive health check")
    status_parser.add_argument("--db", help="Archive database path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    db_path = args.db if hasattr(args, "db") and args.db else None

    with ConversationArchive(db_path) as archive:

        if args.command == "ingest":
            since = None
            if args.since:
                since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)

            if args.project:
                results = archive.ingest_project_sessions(args.project, since)
                print(f"Ingested {len(results)} sessions from {args.project}")
            else:
                results = archive.ingest_all_projects(since=since)
                total = sum(len(v) for v in results.values())
                print(f"Ingested {total} sessions from {len(results)} projects")
                for project, ids in results.items():
                    print(f"  {project}: {len(ids)} sessions")

            # Rebuild TF-IDF after ingestion
            if any(results.values()) if isinstance(results, dict) else results:
                print("Rebuilding TF-IDF index...")
                archive.rebuild_tfidf()
                print("Done.")

        elif args.command == "migrate":
            json_path = args.json or None
            count = archive.migrate_legacy_archive(json_path)
            print(f"Migrated {count} legacy conversations")
            if count > 0:
                print("Rebuilding TF-IDF index...")
                archive.rebuild_tfidf()
                print("Done.")

        elif args.command == "search":
            results = archive.search(args.query, args.limit)
            if not results:
                print(f"No results for: {args.query}")
            else:
                print(f"Found {len(results)} conversations matching: {args.query}\n")
                for r in results:
                    source_tag = f"[{r['source']}]"
                    print(f"  {source_tag} {r['name'][:80]}")
                    print(f"    ID: {r['id']}")
                    print(f"    Date: {r['started_at']}  Messages: {r['message_count']}  Relevance: {r['relevance']}")
                    if r["summary"]:
                        print(f"    Summary: {r['summary'][:120]}")
                    print()

        elif args.command == "export":
            output = archive.export_conversation(args.conversation_id, args.format)
            if output:
                print(output)
            else:
                print(f"Conversation not found: {args.conversation_id}")

        elif args.command == "status":
            stats = archive.get_stats()
            print("=== Conversation Archive Status ===")
            print(f"  Total conversations: {stats['total_conversations']}")
            print(f"    Legacy (Anthropic export): {stats['legacy_conversations']}")
            print(f"    JSONL (local sessions):    {stats['jsonl_conversations']}")
            print(f"  Total messages: {stats['total_messages']}")
            print(f"  Unique keywords: {stats['unique_keywords']}")
            print(f"  Date range: {stats['earliest']} → {stats['latest']}")
            print(f"  Database size: {stats['db_size_mb']} MB")


if __name__ == "__main__":
    main()
