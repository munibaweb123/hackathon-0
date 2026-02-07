#!/bin/bash
# Script to install development dependencies with uv

echo "Installing development dependencies with uv..."

# Install dev dependencies
uv pip install -r requirements-dev.txt

echo "Development dependencies installed successfully!"