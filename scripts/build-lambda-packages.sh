#!/bin/bash

# Enhanced Lambda packaging script for DI-enabled architecture
# This script packages Lambda functions with the complete source code and DI container

set -e

# Configuration
PYTHON_VERSION="3.11"
BUILD_DIR="lambda_build_temp"
PACKAGES_DIR="lambda_packages"
SRC_DIR="src"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Enhanced Lambda Packaging with DI Container${NC}"
echo "=================================================="

# Ensure packages directory exists
mkdir -p "$PACKAGES_DIR"

# Clean up any existing build artifacts
echo -e "${YELLOW}🧹 Cleaning up previous build artifacts...${NC}"
rm -rf "$BUILD_DIR"
rm -f "$PACKAGES_DIR"/*.zip

# Lambda functions to package
LAMBDA_FUNCTIONS=(
    "address_normalizer"
    "authorizer"
    "connect_handler"
    "connection_limit_enforcer"
    "disconnect_handler"
    "ping_perfect_signer"
    "requestor_handler"
    "results_handler"
    "search_handler"
    "share_api"
)

# Function to package a Lambda function
package_lambda_function() {
    local func_name=$1
    local func_build_dir="${BUILD_DIR}_${func_name}"
    
    echo -e "${BLUE}📦 Packaging $func_name...${NC}"
    
    # Create function-specific build directory
    mkdir -p "$func_build_dir"
    
    # Copy entire source code (needed for DI container)
    echo "  📁 Copying source code..."
    cp -r "$SRC_DIR" "$func_build_dir/"
    
    # Copy function-specific handler
    if [ -d "lambda_functions/$func_name" ]; then
        echo "  📄 Copying function handler..."
        cp lambda_functions/$func_name/*.py "$func_build_dir/"
        
        # Install function-specific dependencies if requirements.txt exists
        if [ -f "lambda_functions/$func_name/requirements.txt" ]; then
            echo "  📚 Installing function-specific dependencies..."
            pip install -r "lambda_functions/$func_name/requirements.txt" \
                --target "$func_build_dir" \
                --no-deps \
                --quiet
        fi
    else
        echo -e "  ${YELLOW}⚠️ No specific handler found for $func_name${NC}"
    fi
    
    # Install core dependencies
    echo "  📚 Installing core dependencies..."
    pip install -r requirements.txt \
        --target "$func_build_dir" \
        --no-deps \
        --quiet
    
    # Copy configuration files
    if [ -d "config" ]; then
        echo "  ⚙️ Copying configuration files..."
        cp -r config "$func_build_dir/"
    fi
    
    # Optimize package size
    echo "  🗜️ Optimizing package size..."
    
    # Remove Python cache files
    find "$func_build_dir" -name "*.pyc" -delete
    find "$func_build_dir" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Remove distribution info
    find "$func_build_dir" -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$func_build_dir" -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Remove test files and directories
    find "$func_build_dir" -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$func_build_dir" -name "*test*" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$func_build_dir" -name "test_*.py" -delete 2>/dev/null || true
    find "$func_build_dir" -name "*_test.py" -delete 2>/dev/null || true
    
    # Remove documentation and examples
    find "$func_build_dir" -name "*.md" -delete 2>/dev/null || true
    find "$func_build_dir" -name "*.rst" -delete 2>/dev/null || true
    find "$func_build_dir" -name "*.txt" -not -name "requirements.txt" -delete 2>/dev/null || true
    find "$func_build_dir" -name "LICENSE*" -delete 2>/dev/null || true
    find "$func_build_dir" -name "CHANGELOG*" -delete 2>/dev/null || true
    find "$func_build_dir" -name "examples" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$func_build_dir" -name "docs" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Remove binary files that aren't needed
    find "$func_build_dir" -name "bin" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Strip debug symbols from shared libraries
    find "$func_build_dir" -name "*.so" -exec strip {} \; 2>/dev/null || true
    
    # Create ZIP package
    echo "  📦 Creating ZIP package..."
    cd "$func_build_dir"
    zip -r9 "../$PACKAGES_DIR/${func_name}.zip" . > /dev/null 2>&1
    cd - > /dev/null
    
    # Check package size
    local package_file="$PACKAGES_DIR/${func_name}.zip"
    local package_size=$(stat -c%s "$package_file" 2>/dev/null || stat -f%z "$package_file")
    local package_size_mb=$((package_size / 1024 / 1024))
    
    if [ $package_size -lt 50000000 ]; then
        echo -e "  ${GREEN}✅ $func_name: ${package_size_mb}MB (within Lambda limits)${NC}"
    elif [ $package_size -lt 250000000 ]; then
        echo -e "  ${YELLOW}⚠️ $func_name: ${package_size_mb}MB (large but acceptable)${NC}"
    else
        echo -e "  ${RED}❌ $func_name: ${package_size_mb}MB (exceeds Lambda limits)${NC}"
    fi
    
    # Cleanup build directory
    rm -rf "$func_build_dir"
}

# Package all Lambda functions
for func_name in "${LAMBDA_FUNCTIONS[@]}"; do
    package_lambda_function "$func_name"
done

# Generate package manifest
echo -e "${BLUE}📋 Generating package manifest...${NC}"
cat > "$PACKAGES_DIR/manifest.json" << EOF
{
  "build_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "python_version": "$PYTHON_VERSION",
  "architecture": "DI-enabled",
  "packages": [
EOF

first=true
for zip_file in "$PACKAGES_DIR"/*.zip; do
    if [ -f "$zip_file" ]; then
        filename=$(basename "$zip_file")
        func_name="${filename%.*}"
        size=$(stat -c%s "$zip_file" 2>/dev/null || stat -f%z "$zip_file")
        
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$PACKAGES_DIR/manifest.json"
        fi
        
        cat >> "$PACKAGES_DIR/manifest.json" << EOF
    {
      "name": "$func_name",
      "filename": "$filename",
      "size_bytes": $size,
      "size_mb": $((size / 1024 / 1024)),
      "handler": "${func_name}.lambda_handler",
      "runtime": "python$PYTHON_VERSION",
      "architecture": "x86_64"
    }
EOF
    fi
done

cat >> "$PACKAGES_DIR/manifest.json" << EOF

  ]
}
EOF

# Final statistics
echo -e "${GREEN}📊 PACKAGING STATISTICS${NC}"
echo "======================="

total_size=0
for zip_file in "$PACKAGES_DIR"/*.zip; do
    if [ -f "$zip_file" ]; then
        filename=$(basename "$zip_file" .zip)
        size=$(stat -c%s "$zip_file" 2>/dev/null || stat -f%z "$zip_file")
        size_mb=$((size / 1024 / 1024))
        total_size=$((total_size + size))
        
        if [ $size -lt 50000000 ]; then
            status="${GREEN}✅ OK${NC}"
        elif [ $size -lt 250000000 ]; then
            status="${YELLOW}⚠️ Large${NC}"
        else
            status="${RED}❌ Too Large${NC}"
        fi
        
        echo -e "$filename: ${size_mb}MB $status"
    fi
done

total_size_mb=$((total_size / 1024 / 1024))
echo -e "\nTotal size: ${BLUE}${total_size_mb}MB${NC}"
echo -e "Packages created: ${GREEN}$(ls -1 "$PACKAGES_DIR"/*.zip 2>/dev/null | wc -l)${NC}"

echo -e "\n${GREEN}🎯 Lambda packaging complete!${NC}"
echo "Packages available in: $PACKAGES_DIR/"
echo "Manifest file: $PACKAGES_DIR/manifest.json"