#!/bin/bash

# Enhanced Docker image building script for WebWunder
# Supports multi-stage builds and different deployment targets

set -e

# Configuration
REGISTRY="${REGISTRY:-ghcr.io}"
REPOSITORY="${REPOSITORY:-webwunder}"
TAG="${TAG:-latest}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
BUILD_CONTEXT="${BUILD_CONTEXT:-.}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 Enhanced Docker Image Building${NC}"
echo "=================================="

# Build arguments
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF="${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null || echo 'unknown')}"
VERSION="${GITHUB_REF_NAME:-$(git branch --show-current 2>/dev/null || echo 'unknown')}"

echo -e "${YELLOW}📋 Build Configuration:${NC}"
echo "  Registry: $REGISTRY"
echo "  Repository: $REPOSITORY"
echo "  Tag: $TAG"
echo "  Platforms: $PLATFORMS"
echo "  Build Date: $BUILD_DATE"
echo "  VCS Ref: $VCS_REF"
echo "  Version: $VERSION"

# Function to build Docker image
build_docker_image() {
    local image_name="$1"
    local dockerfile="$2"
    local target="${3:-}"
    local additional_tags="${4:-}"
    
    echo -e "${BLUE}🏗️ Building $image_name...${NC}"
    
    # Prepare tags
    local tags=("$REGISTRY/$REPOSITORY/$image_name:$TAG")
    
    # Add additional tags if provided
    if [ -n "$additional_tags" ]; then
        IFS=',' read -ra ADDR <<< "$additional_tags"
        for tag in "${ADDR[@]}"; do
            tags+=("$REGISTRY/$REPOSITORY/$image_name:$tag")
        done
    fi
    
    # Build tag arguments
    local tag_args=""
    for tag in "${tags[@]}"; do
        tag_args="$tag_args -t $tag"
    done
    
    # Build target argument
    local target_arg=""
    if [ -n "$target" ]; then
        target_arg="--target $target"
    fi
    
    # Build the image
    docker buildx build \
        --platform "$PLATFORMS" \
        --file "$dockerfile" \
        $target_arg \
        $tag_args \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VCS_REF="$VCS_REF" \
        --build-arg VERSION="$VERSION" \
        --cache-from type=gha \
        --cache-to type=gha,mode=max \
        --push \
        "$BUILD_CONTEXT"
    
    echo -e "${GREEN}✅ $image_name built successfully${NC}"
    
    # Return the primary tag for manifest generation
    echo "${tags[0]}"
}

# Setup Docker Buildx
echo -e "${YELLOW}🔧 Setting up Docker Buildx...${NC}"
docker buildx create --use --name webwunder-builder 2>/dev/null || docker buildx use webwunder-builder

# Build main application image
echo -e "${BLUE}📦 Building main application image...${NC}"
main_image=$(build_docker_image "app" "Dockerfile" "" "$VCS_REF,latest")

# Build WebSocket-specific image (if different Dockerfile exists)
if [ -f "Dockerfile.websocket" ]; then
    echo -e "${BLUE}📦 Building WebSocket-specific image...${NC}"
    websocket_image=$(build_docker_image "websocket" "Dockerfile.websocket" "" "$VCS_REF")
else
    echo -e "${YELLOW}ℹ️ Using main image for WebSocket service${NC}"
    websocket_image="$main_image"
fi

# Build HTTP-specific image (if different Dockerfile exists)
if [ -f "Dockerfile.http" ]; then
    echo -e "${BLUE}📦 Building HTTP-specific image...${NC}"
    http_image=$(build_docker_image "http" "Dockerfile.http" "" "$VCS_REF")
else
    echo -e "${YELLOW}ℹ️ Using main image for HTTP service${NC}"
    http_image="$main_image"
fi

# Generate Docker manifest
echo -e "${BLUE}📋 Generating Docker manifest...${NC}"
cat > docker-manifest.json << EOF
{
  "build_info": {
    "timestamp": "$BUILD_DATE",
    "vcs_ref": "$VCS_REF",
    "version": "$VERSION",
    "platforms": "$PLATFORMS"
  },
  "registry": {
    "url": "$REGISTRY",
    "repository": "$REPOSITORY"
  },
  "images": [
    {
      "name": "app",
      "tag": "$TAG",
      "full_name": "$main_image",
      "purpose": "Main application image",
      "services": ["http", "websocket"]
    }
EOF

if [ "$websocket_image" != "$main_image" ]; then
    cat >> docker-manifest.json << EOF
    ,
    {
      "name": "websocket",
      "tag": "$TAG",
      "full_name": "$websocket_image",
      "purpose": "WebSocket-specific image",
      "services": ["websocket"]
    }
EOF
fi

if [ "$http_image" != "$main_image" ]; then
    cat >> docker-manifest.json << EOF
    ,
    {
      "name": "http",
      "tag": "$TAG",
      "full_name": "$http_image",
      "purpose": "HTTP-specific image",
      "services": ["http"]
    }
EOF
fi

cat >> docker-manifest.json << EOF

  ]
}
EOF

# Generate docker-compose override for built images
echo -e "${BLUE}📝 Generating docker-compose override...${NC}"
cat > docker-compose.built.yml << EOF
# Generated docker-compose override for built images
# Use with: docker-compose -f docker-compose.yml -f docker-compose.built.yml up

version: '3.8'

services:
  webwunder-api:
    image: $http_image
    build: null

  webwunder-websocket:
    image: $websocket_image
    build: null
EOF

# Test images locally (if not in CI)
if [ -z "$CI" ]; then
    echo -e "${YELLOW}🧪 Testing images locally...${NC}"
    
    # Pull and test main image
    docker pull "$main_image"
    
    # Quick health check
    echo -e "${BLUE}🏥 Running health check...${NC}"
    docker run --rm "$main_image" python -c "
import sys
sys.path.append('/app')
try:
    from src.shared.dependency_injection.container import DIContainer
    container = DIContainer()
    print('✅ DI Container loads successfully')
except Exception as e:
    print(f'❌ DI Container failed: {e}')
    sys.exit(1)
"
fi

# Final statistics
echo -e "${GREEN}📊 DOCKER BUILD STATISTICS${NC}"
echo "=========================="
echo -e "Main Image: ${GREEN}$main_image${NC}"
if [ "$websocket_image" != "$main_image" ]; then
    echo -e "WebSocket Image: ${GREEN}$websocket_image${NC}"
fi
if [ "$http_image" != "$main_image" ]; then
    echo -e "HTTP Image: ${GREEN}$http_image${NC}"
fi
echo -e "Platforms: ${BLUE}$PLATFORMS${NC}"
echo -e "Registry: ${BLUE}$REGISTRY${NC}"

echo -e "\n${GREEN}🎯 Docker build complete!${NC}"
echo "Manifest file: docker-manifest.json"
echo "Compose override: docker-compose.built.yml"

# Cleanup
docker buildx rm webwunder-builder 2>/dev/null || true