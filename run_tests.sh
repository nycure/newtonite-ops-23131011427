#!/usr/bin/env bash
set -e
echo "========================================================"
echo " Running Newtonite Ops Behavioral Test Suite (Pytest)"
echo "========================================================"
if [ -f "backend/venv/bin/pytest" ]; then
    backend/venv/bin/pytest -v
else
    pytest -v
fi
