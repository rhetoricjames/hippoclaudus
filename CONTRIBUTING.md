# Contributing to Hippoclaudus

Thank you for your interest in contributing. Hippoclaudus is a deliberate architecture — it's opinionated by design. Before submitting a PR, please understand the principles that constrain it.

## Design Principles (Non-Negotiable)

Every contribution must respect these:

### 1. Selective Loading
Claude should never load everything at session start. The system is designed for lazy loading — read the index, read working memory, pull deeper files only when needed. PRs that add automatic bulk-loading of files will be rejected.

### 2. Signal Over Noise
If it doesn't add clear value, leave it out. Don't pad templates with placeholder content. Don't add optional fields "just in case." The Total Update protocol explicitly says: if nothing changed, say so and move on. Apply that principle to code too.

### 3. Memory Hygiene
Every new memory layer or storage mechanism must include a corresponding cleanup/pruning path. Memory systems that only grow degrade over time. If you add a way to store something, add a way to prune it.

### 4. Human in the Loop
Deep recall (Tier 3) is intentionally manual. The user runs extraction scripts. The user reviews what's recalled. Don't automate this away — the human awareness is a feature, not a limitation.

### 5. Local First
Everything runs on the user's machine. No external services, no cloud dependencies, no accounts to create. The MCP database is local. The files are local. The conversation archive is local.

## What We Welcome

- **Bug fixes** — especially cross-platform issues
- **Template improvements** — better structure, clearer instructions, useful defaults
- **Script enhancements** — more robust parsing, better error handling, new output formats
- **Platform support** — Windows paths, Linux config locations, etc.
- **Documentation** — clearer setup instructions, troubleshooting guides, examples
- **Doctor improvements** — more diagnostic checks, better error messages

## What We'll Push Back On

- Features that require external services or API keys
- Automatic context loading that bloats session startup
- Complex dependency chains (keep the pip install list minimal)
- UI layers or dashboards (this is infrastructure, not an app)
- Changes that make setup harder for the sake of flexibility

## How to Contribute

1. Fork the repo
2. Create a feature branch (`git checkout -b improve-scanner`)
3. Make your changes
4. Test against the doctor (`python3 doctor.py`)
5. Submit a PR with a clear description of what and why

## Style

- Markdown files: clear, concise, scannable. No walls of text.
- Python: standard library preferred. Type hints welcome. Docstrings required.
- Commit messages: imperative mood, concise. "Add cross-platform config detection" not "I added some stuff for Windows."

## Questions?

Open an issue. We're happy to discuss approaches before you invest time building.
