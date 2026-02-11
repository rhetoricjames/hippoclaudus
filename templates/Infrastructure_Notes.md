# Infrastructure Notes
*Update when tools, servers, configs, or paths change.*

---

## Hardware
- **Machine:** [Your machine description]
- **OS:** [macOS / Linux / Windows version]

## MCP Configuration
- **Config file:** [Path to claude_desktop_config.json]
- **Memory server:** mcp-memory-service via Python venv
- **Database:** `mcp-memory/data/memory.db`

## Key Paths
| Resource | Path |
|----------|------|
| Claude root | [Your base path] |
| Long-term memory | `mcp-memory/long-term/` |
| Working memory | `mcp-memory/working/` |
| Conversation archive | `mcp-memory/conversations/` |
| Memory DB | `mcp-memory/data/memory.db` |

## Tools Available
- **Claude Code:** CLI access for technical tasks
- **Claude Desktop:** Chat interface with MCP tools
- **MCP Memory:** Semantic search via sqlite-vec

## Known Issues
- *(Log issues and fixes here as they arise)*

---
*Created: [date]*
*Last updated: [date]*
