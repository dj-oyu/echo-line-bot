#!/bin/bash

# Build Lambda Layer script for Python dependencies
# This script creates a Lambda Layer with Python dependencies using uv

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAMBDA_DIR="$PROJECT_ROOT/lambda"
LAYER_OUTPUT_DIR="$LAMBDA_DIR/layer-dist"
LAYER_PYTHON_DIR="$LAYER_OUTPUT_DIR/python"

echo "🔨 Building Lambda Layer..."
echo "Project root: $PROJECT_ROOT"
echo "Lambda directory: $LAMBDA_DIR"
echo "Layer output: $LAYER_OUTPUT_DIR"

# Clean up previous builds
if [ -d "$LAYER_OUTPUT_DIR" ]; then
    echo "🧹 Cleaning up previous build..."
    rm -rf "$LAYER_OUTPUT_DIR"
fi

# Create layer directory structure
echo "📁 Creating layer directory structure..."
mkdir -p "$LAYER_PYTHON_DIR"

# Navigate to project root for uv operations
cd "$PROJECT_ROOT"

# Install dependencies using uv into the layer directory
echo "📦 Installing Python dependencies with uv..."
# Pin the target interpreter and platform so the layer matches the Lambda
# runtime regardless of the local Python version (compiled wheels are
# ABI-specific: pydantic-core, grpcio and aiohttp ship cp314 binaries).
uv export --no-dev --no-hashes | uv pip install \
    --target "$LAYER_PYTHON_DIR" \
    --python-version 3.14 \
    --python-platform x86_64-manylinux2014 \
    -r -

# Remove unnecessary files to reduce layer size
echo "🗑️ Removing unnecessary files..."
find "$LAYER_PYTHON_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$LAYER_PYTHON_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$LAYER_PYTHON_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true

# Remove dist-info directories EXCEPT opentelemetry (needed for entry_points discovery)
echo "🗑️ Removing dist-info (preserving opentelemetry)..."
find "$LAYER_PYTHON_DIR" -type d -name "*.dist-info" ! -name "opentelemetry*.dist-info" -exec rm -rf {} + 2>/dev/null || true

# Show layer size
LAYER_SIZE=$(du -sh "$LAYER_OUTPUT_DIR" | cut -f1)
echo "✅ Lambda Layer built successfully!"
echo "📊 Layer size: $LAYER_SIZE"
echo "📍 Location: $LAYER_OUTPUT_DIR"

# List top-level packages for verification
echo "📋 Installed packages:"
ls -la "$LAYER_PYTHON_DIR" | head -10