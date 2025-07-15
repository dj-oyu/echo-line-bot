#!/bin/bash
set -e

echo "🔨 Building Lambda Layer dependencies..."

# Create layer directory structure
LAYER_DIR="lambda/layer-dist"
mkdir -p "${LAYER_DIR}/python"

# Clean previous build
rm -rf "${LAYER_DIR}/python/*"

echo "📦 Installing Python dependencies to layer..."

# Install dependencies to the layer directory using uv
# Use uv pip install with requirements.txt for layer building (most reliable for Lambda layers)
uv pip install --target "${LAYER_DIR}/python" -r lambda/requirements.txt

echo "🧹 Cleaning up unnecessary files..."

# Remove unnecessary files to reduce layer size
find "${LAYER_DIR}/python" -name "*.pyc" -delete
find "${LAYER_DIR}/python" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "${LAYER_DIR}/python" -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
find "${LAYER_DIR}/python" -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true

echo "📊 Layer build summary:"
echo "Size: $(du -sh ${LAYER_DIR} | cut -f1)"
echo "Files: $(find ${LAYER_DIR} -type f | wc -l)"

echo "✅ Lambda Layer build completed successfully!"
echo "Layer location: ${LAYER_DIR}"