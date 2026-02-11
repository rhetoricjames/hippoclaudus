#!/bin/bash
#
# Hippoclaudus Installer
# Sets up the three-tier persistent memory architecture for Claude.
#
# Usage: bash install.sh [base_path]
#   base_path: Where to install (default: ~/Claude)
#
# What this script does:
#   1. Creates the directory structure
#   2. Sets up a Python virtual environment
#   3. Installs mcp-memory-service
#   4. Copies templates to the right locations
#   5. Shows you what to configure next
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Hippoclaudus Installer        ║${NC}"
echo -e "${BLUE}║   Persistent Memory for Claude       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo ""

# Determine base path
if [ -n "$1" ]; then
    BASE_PATH="$1"
else
    echo -e "Where should Hippoclaudus be installed?"
    echo -e "  Default: ${YELLOW}~/Claude${NC}"
    read -p "  Path (press Enter for default): " user_path
    BASE_PATH="${user_path:-$HOME/Claude}"
fi

# Expand ~ if present
BASE_PATH="${BASE_PATH/#\~/$HOME}"

# Resolve to absolute path
BASE_PATH="$(cd "$(dirname "$BASE_PATH")" 2>/dev/null && pwd)/$(basename "$BASE_PATH")" 2>/dev/null || BASE_PATH="$BASE_PATH"

echo ""
echo -e "${BLUE}Installing to:${NC} $BASE_PATH"
echo ""

# Detect script directory (where templates live)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR/templates"

if [ ! -d "$TEMPLATE_DIR" ]; then
    echo -e "${RED}Error: templates/ directory not found at $TEMPLATE_DIR${NC}"
    echo "Make sure you're running this from the hippoclaudus repo directory."
    exit 1
fi

# Step 1: Create directory structure
echo -e "${GREEN}[1/5]${NC} Creating directory structure..."
mkdir -p "$BASE_PATH/mcp-memory/long-term"
mkdir -p "$BASE_PATH/mcp-memory/working"
mkdir -p "$BASE_PATH/mcp-memory/data"
mkdir -p "$BASE_PATH/mcp-memory/conversations"
echo "  ✓ Created mcp-memory/{long-term,working,data,conversations}"

# Step 2: Set up Python venv
echo -e "${GREEN}[2/5]${NC} Setting up Python virtual environment..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found. Please install Python 3.10+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Found Python $PYTHON_VERSION"

if [ ! -d "$BASE_PATH/mcp-memory/venv" ]; then
    python3 -m venv "$BASE_PATH/mcp-memory/venv"
    echo "  ✓ Created virtual environment"
else
    echo "  ✓ Virtual environment already exists"
fi

# Step 3: Install mcp-memory-service
echo -e "${GREEN}[3/5]${NC} Installing mcp-memory-service..."
"$BASE_PATH/mcp-memory/venv/bin/pip" install --quiet mcp-memory-service 2>&1 | tail -1
echo "  ✓ Installed mcp-memory-service"

# Verify installation
if "$BASE_PATH/mcp-memory/venv/bin/python" -c "import mcp_memory_service" 2>/dev/null; then
    echo "  ✓ Verified: mcp_memory_service importable"
else
    echo -e "${RED}  ✗ Warning: mcp_memory_service could not be imported${NC}"
fi

# Step 4: Copy templates
echo -e "${GREEN}[4/5]${NC} Copying templates..."

# Long-term memory
cp "$TEMPLATE_DIR/INDEX.md" "$BASE_PATH/mcp-memory/long-term/"
cp "$TEMPLATE_DIR/Total_Update_Protocol.md" "$BASE_PATH/mcp-memory/long-term/"
echo "  ✓ Copied INDEX.md and Total_Update_Protocol.md (legacy reference) to long-term/"

# Working memory
cp "$TEMPLATE_DIR/Session_Summary_Log.md" "$BASE_PATH/mcp-memory/working/"
cp "$TEMPLATE_DIR/Open_Questions_Blockers.md" "$BASE_PATH/mcp-memory/working/"
cp "$TEMPLATE_DIR/Decision_Log.md" "$BASE_PATH/mcp-memory/working/"
echo "  ✓ Copied working memory templates"

# Conversation scripts
cp "$TEMPLATE_DIR/scan_conversations.py" "$BASE_PATH/mcp-memory/conversations/"
cp "$TEMPLATE_DIR/extract_conversations.py" "$BASE_PATH/mcp-memory/conversations/"
if [ -f "$TEMPLATE_DIR/keywords.yaml" ]; then
    cp "$TEMPLATE_DIR/keywords.yaml" "$BASE_PATH/mcp-memory/conversations/"
fi
echo "  ✓ Copied conversation scanner scripts"

# CLAUDE.md — copy to base path
cp "$TEMPLATE_DIR/CLAUDE.md" "$BASE_PATH/"
echo "  ✓ Copied CLAUDE.md to project root"

# Step 5: Path substitution in CLAUDE.md
echo -e "${GREEN}[5/5]${NC} Configuring paths..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|YOUR_PATH|$BASE_PATH|g" "$BASE_PATH/CLAUDE.md"
else
    sed -i "s|YOUR_PATH|$BASE_PATH|g" "$BASE_PATH/CLAUDE.md"
fi
echo "  ✓ Updated paths in CLAUDE.md"

# Done — show next steps
PYTHON_PATH="$BASE_PATH/mcp-memory/venv/bin/python"
DB_PATH="$BASE_PATH/mcp-memory/data/memory.db"

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Add the MCP memory server to your Claude Desktop config."
echo ""
echo "   Config file location:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "     ~/Library/Application Support/Claude/claude_desktop_config.json"
elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "win"* ]]; then
    echo "     %APPDATA%\\Claude\\claude_desktop_config.json"
else
    echo "     ~/.config/claude/claude_desktop_config.json"
fi
echo ""
echo "   Add this to your mcpServers config:"
echo ""
echo "   \"memory\": {"
echo "     \"command\": \"$PYTHON_PATH\","
echo "     \"args\": [\"-m\", \"mcp_memory_service.server\"],"
echo "     \"env\": {"
echo "       \"MCP_MEMORY_STORAGE_BACKEND\": \"sqlite_vec\","
echo "       \"MCP_MEMORY_SQLITE_PATH\": \"$DB_PATH\""
echo "     }"
echo "   }"
echo ""
echo "2. Restart Claude Desktop to pick up the new config."
echo ""
echo "3. Edit $BASE_PATH/CLAUDE.md to add your personal context"
echo "   (identity, key people, projects)."
echo ""
echo "4. (Optional) Export your conversation history from claude.ai"
echo "   and place conversations.json in:"
echo "   $BASE_PATH/mcp-memory/conversations/"
echo "   Then run: python3 scan_conversations.py"
echo ""
echo "5. Run the diagnostic to verify everything:"
echo "   python3 $(dirname "$0")/doctor.py --base-path $BASE_PATH"
echo ""
echo -e "${BLUE}Full documentation: https://github.com/rhetoricjames/hippoclaudus${NC}"
echo ""
