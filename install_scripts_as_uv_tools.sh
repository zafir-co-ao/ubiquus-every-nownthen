#!/bin/bash

# install_scripts_as_uv_tools.sh
#
# This script crawls all directories under ./scripts and installs any
# Python packages (directories containing pyproject.toml) as uv tools.
#
# Usage:
#   ./install_scripts_as_uv_tools.sh

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed.${NC}"
    echo "Please install uv first: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}UV Tools Installation Script${NC}"
echo -e "${BLUE}===========================================${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"

# Check if scripts directory exists
if [ ! -d "$SCRIPTS_DIR" ]; then
    echo -e "${RED}Error: scripts directory not found at $SCRIPTS_DIR${NC}"
    exit 1
fi

echo -e "${YELLOW}Searching for Python packages in: $SCRIPTS_DIR${NC}"
echo ""

# Counter for tracking installations
TOTAL_FOUND=0
TOTAL_SUCCESS=0
TOTAL_FAILED=0

# Find all directories containing pyproject.toml
while IFS= read -r pyproject_file; do
    TOTAL_FOUND=$((TOTAL_FOUND + 1))

    # Get the directory containing pyproject.toml
    PACKAGE_DIR="$(dirname "$pyproject_file")"
    PACKAGE_NAME="$(basename "$PACKAGE_DIR")"

    echo -e "${BLUE}-------------------------------------------${NC}"
    echo -e "${YELLOW}Found package: $PACKAGE_NAME${NC}"
    echo -e "Location: $PACKAGE_DIR"
    echo ""

    # Change to package directory and install
    cd "$PACKAGE_DIR"

    echo -e "Installing ${GREEN}$PACKAGE_NAME${NC} as uv tool..."

    if uv tool install --force --reinstall .; then
        echo -e "${GREEN}✓ Successfully installed $PACKAGE_NAME${NC}"
        TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
    else
        echo -e "${RED}✗ Failed to install $PACKAGE_NAME${NC}"
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi

    echo ""

    # Return to script directory
    cd "$SCRIPT_DIR"

done < <(find "$SCRIPTS_DIR" -name "pyproject.toml" -type f)

# Print summary
echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}Installation Summary${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "Total packages found: ${YELLOW}$TOTAL_FOUND${NC}"
echo -e "Successfully installed: ${GREEN}$TOTAL_SUCCESS${NC}"
echo -e "Failed installations: ${RED}$TOTAL_FAILED${NC}"
echo ""

if [ $TOTAL_FOUND -eq 0 ]; then
    echo -e "${YELLOW}No Python packages found in $SCRIPTS_DIR${NC}"
    echo -e "${YELLOW}Make sure your packages contain a pyproject.toml file.${NC}"
    exit 0
fi

if [ $TOTAL_FAILED -gt 0 ]; then
    echo -e "${RED}Some installations failed. Please check the output above.${NC}"
    exit 1
else
    echo -e "${GREEN}All packages installed successfully!${NC}"
    echo ""
    echo -e "You can now use the installed tools. To see all installed tools, run:"
    echo -e "  ${BLUE}uv tool list${NC}"
fi
