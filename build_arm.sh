#!/bin/bash

echo "🚀 GRAVITON2 (ARM64) Layer Builder - Maximum Performance"
echo "======================================================="

# Configuration
PYTHON_VERSION="3.9"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ensure lambda_packages directory exists
mkdir -p lambda_packages

# Clean up any existing build artifacts
echo -e "${YELLOW}🧹 Cleaning up previous x86_64 build artifacts...${NC}"
rm -rf lambda_layers/
rm -f lambda_packages/*_layer_arm64.zip

echo -e "${BLUE}🎯 Creating ARM64 Layer 1: Ultra-Fast JSON (orjson)${NC}"

# Use linux/arm64 platform for Graviton2
docker run --rm --platform linux/arm64 \
  -v $(pwd):/workspace \
  -w /workspace \
  python:${PYTHON_VERSION}-slim \
  bash -c "
    echo '🏗️  Building on ARM64 architecture for Graviton2'

    apt-get update > /dev/null 2>&1
    apt-get install -y zip > /dev/null 2>&1

    mkdir -p lambda_layers/json_layer_arm64/python

    echo '📦 Installing orjson for ARM64...'
    pip install orjson==3.9.15 \
        --target lambda_layers/json_layer_arm64/python \
        --no-cache-dir \
        --quiet

    # Verify orjson was installed
    if [ -d lambda_layers/json_layer_arm64/python/orjson ]; then
        echo '✅ orjson ARM64 installed successfully'
        file lambda_layers/json_layer_arm64/python/orjson/*.so | head -3
    else
        echo '❌ orjson ARM64 installation failed'
    fi

    # Cleanup
    find lambda_layers/json_layer_arm64/python -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/json_layer_arm64/python -name '*.pyc' -delete 2>/dev/null || true
    find lambda_layers/json_layer_arm64/python -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true

    echo 'JSON ARM64 Layer size:'
    du -sh lambda_layers/json_layer_arm64/python

    cd lambda_layers/json_layer_arm64
    zip -r9 ../../lambda_packages/json_layer_arm64.zip python/ > /dev/null
  "

echo -e "${BLUE}🎯 Creating ARM64 Layer 2: Data Processing (Polars)${NC}"

docker run --rm --platform linux/arm64 \
  -v $(pwd):/workspace \
  -w /workspace \
  python:${PYTHON_VERSION}-slim \
  bash -c "
    echo '🏗️  Building Polars on ARM64 architecture for Graviton2'

    apt-get update > /dev/null 2>&1
    apt-get install -y zip gcc g++ > /dev/null 2>&1

    mkdir -p lambda_layers/polars_layer_arm64/python

    echo '📦 Installing Polars for ARM64...'
    pip install polars==0.20.31 \
        --target lambda_layers/polars_layer_arm64/python \
        --no-cache-dir \
        --compile \
        --quiet

    # Verify polars was installed
    if [ -d lambda_layers/polars_layer_arm64/python/polars ]; then
        echo '✅ Polars ARM64 installed successfully'
        file lambda_layers/polars_layer_arm64/python/polars/*.so | head -3
    else
        echo '❌ Polars ARM64 installation failed'
    fi

    # Cleanup
    find lambda_layers/polars_layer_arm64/python -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/polars_layer_arm64/python -name '*.pyc' -delete 2>/dev/null || true
    find lambda_layers/polars_layer_arm64/python -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/polars_layer_arm64/python -name 'tests' -type d -exec rm -rf {} + 2>/dev/null || true

    echo 'Polars ARM64 Layer size:'
    du -sh lambda_layers/polars_layer_arm64/python

    cd lambda_layers/polars_layer_arm64
    zip -r9 ../../lambda_packages/polars_layer_arm64.zip python/ > /dev/null
  "

# Final statistics
echo -e "${GREEN}📊 GRAVITON2 LAYERS STATISTICS${NC}"
echo "=============================="

for layer in json_layer_arm64 polars_layer_arm64; do
    if [ -f lambda_packages/${layer}.zip ]; then
        LAYER_SIZE=$(stat -f%z lambda_packages/${layer}.zip 2>/dev/null || stat -c%s lambda_packages/${layer}.zip)
        LAYER_SIZE_MB=$((LAYER_SIZE / 1024 / 1024))

        echo -e "${layer}: ${GREEN}${LAYER_SIZE_MB}MB${NC} ($(du -h lambda_packages/${layer}.zip | cut -f1))"

        if [ $LAYER_SIZE -lt 70000000 ]; then
            echo -e "  Status: ${GREEN}✅ FITS IN AWS LAMBDA${NC}"
        else
            echo -e "  Status: ${RED}❌ Still too large${NC}"
        fi
    fi
done

# Architecture verification
echo -e "${YELLOW}🔍 Architecture Verification:${NC}"
for layer in json_layer_arm64 polars_layer_arm64; do
    if [ -f lambda_packages/${layer}.zip ]; then
        echo "Checking ${layer} architecture:"
        unzip -l lambda_packages/${layer}.zip | grep '\.so$' | head -2
    fi
done

# Cleanup
rm -rf lambda_layers/

echo -e "\n${GREEN}🎯 GRAVITON2 LAYERS READY!${NC}"
echo "Next steps for Graviton2 migration:"
echo "1. Update lambda_layer.tf to use *_arm64.zip files"
echo "2. Change Lambda runtime to python3.9 (arm64 compatible)"
echo "3. Update architecture in Terraform to 'arm64'"
echo ""
echo "💰 Expected benefits:"
echo "✅ 20% better price-performance"
echo "✅ Better energy efficiency"
echo "✅ Potentially faster data processing"