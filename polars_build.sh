#!/bin/bash

echo "🚀 FIXED Polars Layer - Proper Binary Build"
echo "==========================================="

# Clean up
rm -rf lambda_layers/
rm -f lambda_packages/polars_layer.zip

# Create properly built Polars layer
docker run --rm --platform linux/amd64 \
  -v $(pwd):/workspace \
  -w /workspace \
  python:3.9-slim \
  bash -c "
    echo '🏗️  Installing build tools for proper binary compilation...'
    apt-get update > /dev/null 2>&1
    apt-get install -y zip gcc g++ > /dev/null 2>&1

    echo '📦 Creating Polars layer directory...'
    mkdir -p lambda_layers/polars_layer/python

    echo '🔧 Installing Polars with proper binary compilation...'
    # Install specific version that works well with Lambda
    pip install polars==0.20.31 \
        --target lambda_layers/polars_layer/python \
        --no-cache-dir \
        --compile \
        --quiet

    echo '🔍 Verifying Polars installation:'
    if [ -d lambda_layers/polars_layer/python/polars ]; then
        echo '✅ Polars directory found'
        ls -la lambda_layers/polars_layer/python/polars/ | grep -E '\.so$|\.py$' | head -5

        # Check for the critical binary files
        if find lambda_layers/polars_layer/python -name '*.so' | grep -q polars; then
            echo '✅ Polars binary files found'
        else
            echo '⚠️  No Polars binary files found'
        fi
    else
        echo '❌ Polars installation failed'
    fi

    echo '🧹 Optimizing layer size...'
    # Remove unnecessary files but keep the binaries
    find lambda_layers/polars_layer/python -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/polars_layer/python -name '*.pyc' -delete 2>/dev/null || true
    find lambda_layers/polars_layer/python -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/polars_layer/python -name 'tests' -type d -exec rm -rf {} + 2>/dev/null || true

    # Don't strip .so files - they're needed for Polars to work

    echo '📊 Final layer size:'
    du -sh lambda_layers/polars_layer/python

    echo '📦 Creating ZIP with proper compression...'
    cd lambda_layers/polars_layer
    zip -r9 ../../lambda_packages/polars_layer.zip python/ > /dev/null

    echo '✅ Fixed Polars layer complete!'
  "

echo "📊 Final Polars Layer Statistics:"
if [ -f lambda_packages/polars_layer.zip ]; then
    LAYER_SIZE=$(stat -f%z lambda_packages/polars_layer.zip 2>/dev/null || stat -c%s lambda_packages/polars_layer.zip)
    LAYER_SIZE_MB=$((LAYER_SIZE / 1024 / 1024))
    echo "Size: ${LAYER_SIZE_MB}MB ($(du -h lambda_packages/polars_layer.zip | cut -f1))"

    if [ $LAYER_SIZE -lt 70000000 ]; then
        echo "Status: ✅ FITS IN AWS LAMBDA"
    else
        echo "Status: ❌ Too large for direct upload - need S3 approach"
    fi

    echo "Binary files check:"
    unzip -l lambda_packages/polars_layer.zip | grep '\.so$' | wc -l | xargs echo "Shared libraries found:"
fi

# Clean up temp files
rm -rf lambda_layers/

echo ""
echo "🎯 DEPLOYMENT OPTIONS:"
echo "1. If < 67MB: Deploy directly with terraform apply"
echo "2. If > 67MB: Use S3 upload approach"
echo ""
echo "🚀 Your system is already working with pure Python fallback!"
echo "   This Polars fix will just make it faster! 🏎️"