#!/bin/bash
# Activate script for Model Fusion virtual environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
VENV_PATH="$PROJECT_ROOT/.venv"

echo ""
echo -e "\033[36mActivating Model Fusion virtual environment...\033[0m"
echo ""

if [ ! -d "$VENV_PATH" ]; then
    echo -e "\033[31mVirtual environment not found at $VENV_PATH\033[0m"
    echo ""
    echo -e "\033[33mPlease run setup-environment.sh first to create the virtual environment.\033[0m"
    echo ""
    exit 1
fi

# Try Windows path first (Scripts/), then Unix (bin/)
if [ -f "$VENV_PATH/Scripts/activate" ]; then
    source "$VENV_PATH/Scripts/activate"
elif [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
else
    echo -e "\033[31mActivation script not found in $VENV_PATH\033[0m"
    echo -e "\033[33mThe virtual environment may be corrupted. Try running setup-environment.sh again.\033[0m"
    exit 1
fi

echo -e "\033[32mVirtual environment activated successfully!\033[0m"
echo ""
echo -e "\033[90mEnvironment: $VENV_PATH\033[0m"
echo -e "\033[90mPython:      $(python --version 2>&1)\033[0m"
echo ""
