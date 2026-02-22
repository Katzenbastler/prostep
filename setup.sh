#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="$(dirname "$0")/v"
REQUIRED_MINOR=11  # open3d wheels top out at 3.11 for now

# Find a Python 3.11.x interpreter
find_python() {
    for candidate in python3.11 python3 python; do
        if command -v "$candidate" &>/dev/null; then
            ver=$("$candidate" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo 0)
            maj=$("$candidate" -c 'import sys; print(sys.version_info.major)' 2>/dev/null || echo 0)
            if [ "$maj" -eq 3 ] && [ "$ver" -eq $REQUIRED_MINOR ]; then
                echo "$candidate"
                return
            fi
        fi
    done
    # pyenv fallback
    if command -v pyenv &>/dev/null; then
        pyenv_py=$(pyenv prefix 3.11 2>/dev/null)/bin/python3 || true
        if [ -x "${pyenv_py:-}" ]; then
            echo "$pyenv_py"
            return
        fi
    fi
    echo ""
}

PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.11 not found. Install it or activate it via pyenv before running this script." >&2
    exit 1
fi

echo "Using $($PYTHON --version) at $(command -v $PYTHON)"

echo "Creating virtual environment at $VENV_DIR ..."
"$PYTHON" -m venv "$VENV_DIR"

PIP="$VENV_DIR/bin/pip"
"$PIP" install --upgrade pip -q

echo "Installing dependencies ..."
"$PIP" install -r "$(dirname "$0")/requirements-stl-reconstructor.txt"

echo "Installing package (editable) ..."
"$PIP" install -e "$(dirname "$0")"

echo ""
echo "Done. Activate with:"
echo "  source $VENV_DIR/bin/activate"
