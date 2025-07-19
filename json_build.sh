#!/bin/bash

echo "🎯 SIMPLE orjson Layer - Guaranteed to Work"
echo "==========================================="

# Clean up
rm -rf lambda_layers/
rm -f lambda_packages/json_layer.zip

# Create a super simple orjson layer
docker run --rm --platform linux/amd64 \
  -v $(pwd):/workspace \
  -w /workspace \
  python:3.9-slim \
  bash -c "
    echo '📦 Installing system tools...'
    apt-get update > /dev/null 2>&1
    apt-get install -y zip > /dev/null 2>&1

    echo '🎯 Creating simple orjson layer...'
    mkdir -p lambda_layers/json_layer/python

    echo '📥 Installing orjson...'
    pip install orjson==3.9.15 \
        --target lambda_layers/json_layer/python \
        --no-cache-dir \
        --quiet

    echo '🔍 Checking what was installed:'
    find lambda_layers/json_layer/python -name 'orjson*' -type d
    find lambda_layers/json_layer/python -name '*.py' | grep orjson
    find lambda_layers/json_layer/python -name '*.so' | grep orjson

    echo '🧹 Minimal cleanup...'
    find lambda_layers/json_layer/python -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/json_layer/python -name '*.pyc' -delete 2>/dev/null || true

    echo '📊 Layer size:'
    du -sh lambda_layers/json_layer/python

    echo '📦 Creating ZIP...'
    cd lambda_layers/json_layer
    zip -r9 ../../lambda_packages/json_layer.zip python/ > /dev/null

    echo '✅ Simple orjson layer complete!'
  "

echo "📊 Final JSON Layer:"
if [ -f lambda_packages/json_layer.zip ]; then
    LAYER_SIZE=$(stat -f%z lambda_packages/json_layer.zip 2>/dev/null || stat -c%s lambda_packages/json_layer.zip)
    LAYER_SIZE_MB=$((LAYER_SIZE / 1024 / 1024))
    echo "Size: ${LAYER_SIZE_MB}MB ($(du -h lambda_packages/json_layer.zip | cut -f1))"

    echo "Contents check:"
    unzip -l lambda_packages/json_layer.zip | grep orjson | head -5
fi

# Clean up temp files
rm -rf lambda_layers/

echo "🎯 Ready to deploy! Update your Lambda with this layer."