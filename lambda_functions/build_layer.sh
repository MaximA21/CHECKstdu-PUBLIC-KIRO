#!/bin/bash

echo "🚀 Enhanced Lambda Layers for New DI Architecture"
echo "================================================="

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
echo -e "${YELLOW}🧹 Cleaning up previous build artifacts...${NC}"
rm -rf lambda_layers/
rm -f lambda_packages/*_layer*.zip

echo -e "${BLUE}🎯 Creating Layer 1: Ultra-Fast JSON (orjson)${NC}"

docker run --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  python:${PYTHON_VERSION}-slim \
  bash -c "
    apt-get update > /dev/null 2>&1
    apt-get install -y zip > /dev/null 2>&1

    mkdir -p lambda_layers/json_layer/python

    pip install 'orjson>=3.8.0' \
        --target lambda_layers/json_layer/python \
        --no-cache-dir --quiet

    # Aggressive cleanup
    find lambda_layers/json_layer/python -name '*.pyc' -delete
    find lambda_layers/json_layer/python -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/json_layer/python -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true

    echo 'JSON Layer size:'
    du -sh lambda_layers/json_layer/python

    cd lambda_layers/json_layer
    zip -r9 ../../lambda_packages/json_layer.zip python/ > /dev/null
  "

echo -e "${BLUE}🎯 Creating Layer 2: Data Processing (Polars only)${NC}"

docker run --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  python:${PYTHON_VERSION}-slim \
  bash -c "
    apt-get update > /dev/null 2>&1
    apt-get install -y zip > /dev/null 2>&1

    mkdir -p lambda_layers/polars_layer/python

    pip install 'polars>=1.0.0' \
        --target lambda_layers/polars_layer/python \
        --no-cache-dir --quiet

    # Ultra-aggressive cleanup for Polars
    find lambda_layers/polars_layer/python -name '*.pyc' -delete
    find lambda_layers/polars_layer/python -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/polars_layer/python -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/polars_layer/python -name 'tests' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/polars_layer/python -name '*test*' -type d -exec rm -rf {} + 2>/dev/null || true
    find lambda_layers/polars_layer/python -name '*.md' -delete 2>/dev/null || true
    find lambda_layers/polars_layer/python -name '*.txt' -delete 2>/dev/null || true
    find lambda_layers/polars_layer/python -name 'LICENSE*' -delete 2>/dev/null || true
    rm -rf lambda_layers/polars_layer/python/bin/ 2>/dev/null || true

    # Strip debug symbols from shared libraries
    find lambda_layers/polars_layer/python -name '*.so' -exec strip {} \; 2>/dev/null || true

    echo 'Polars Layer size:'
    du -sh lambda_layers/polars_layer/python

    cd lambda_layers/polars_layer
    zip -r9 ../../lambda_packages/polars_layer.zip python/ > /dev/null
  "

# Final statistics
echo -e "${GREEN}📊 SPLIT LAYERS STATISTICS${NC}"
echo "=========================="

for layer in json_layer polars_layer; do
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

# Total size check
TOTAL_SIZE=0
for layer in json_layer polars_layer; do
    if [ -f lambda_packages/${layer}.zip ]; then
        LAYER_SIZE=$(stat -f%z lambda_packages/${layer}.zip 2>/dev/null || stat -c%s lambda_packages/${layer}.zip)
        TOTAL_SIZE=$((TOTAL_SIZE + LAYER_SIZE))
    fi
done

TOTAL_SIZE_MB=$((TOTAL_SIZE / 1024 / 1024))
echo -e "Total: ${BLUE}${TOTAL_SIZE_MB}MB${NC} across 2 layers"

# Cleanup
rm -rf lambda_layers/

echo -e "\n${GREEN}🎯 SPLIT LAYERS READY!${NC}"
echo "Update your Terraform with:"
echo "1. json_layer.zip (orjson only)"
echo "2. polars_layer.zip (polars only)"
echo ""
echo "Lambda can use both layers simultaneously (up to 5 layers max)"