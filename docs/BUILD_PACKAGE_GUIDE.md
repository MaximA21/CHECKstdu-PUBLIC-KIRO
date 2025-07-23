# Build and Package Guide

This guide covers the build and packaging workflow for the WebWunder application, including Lambda functions, Docker images, and Terraform infrastructure.

## Overview

The build and packaging workflow consists of four main components:

1. **Lambda Function Packaging** - Creates deployment packages for all Lambda functions with DI container
2. **Docker Image Building** - Builds multi-platform container images for HTTP and WebSocket servers
3. **Terraform Validation** - Validates infrastructure code and generates deployment plans
4. **Artifact Storage** - Manages versioned artifacts and deployment packages

## Workflow Triggers

The build and package workflow is triggered by:

- Push to `kiro-rewrite` branch
- Pull requests to `kiro-rewrite` branch
- Manual workflow dispatch with build type selection

## Components

### 1. Lambda Function Packaging

#### Features
- **DI Container Integration**: Packages complete source code with dependency injection
- **Size Optimization**: Removes unnecessary files to minimize package size
- **Multi-Function Support**: Packages all Lambda functions in parallel
- **Manifest Generation**: Creates detailed package manifest with metadata

#### Supported Functions
- `address_normalizer` - German character normalization
- `authorizer` - API authorization handler
- `connect_handler` - WebSocket connection handler
- `connection_limit_enforcer` - Connection limit enforcement
- `disconnect_handler` - WebSocket disconnection handler
- `ping_perfect_signer` - HMAC signing for API calls
- `requestor_handler` - Request processing handler
- `results_handler` - Results processing and storage
- `search_handler` - Search request handler
- `share_api` - Results sharing API

#### Package Structure
Each Lambda package includes:
```
package.zip
├── src/                    # Complete source code
│   ├── application/        # Application layer
│   ├── domain/            # Domain layer
│   ├── infrastructure/    # Infrastructure layer
│   ├── presentation/      # Presentation layer
│   └── shared/           # Shared utilities
├── config/               # Configuration files
├── function_handler.py   # Function-specific handler
└── dependencies/         # Python dependencies
```

#### Size Optimization
- Removes Python cache files (`*.pyc`, `__pycache__`)
- Removes distribution info (`*.dist-info`, `*.egg-info`)
- Removes test files and directories
- Removes documentation and examples
- Strips debug symbols from shared libraries

### 2. Docker Image Building

#### Features
- **Multi-Platform Support**: Builds for `linux/amd64` and `linux/arm64`
- **Multi-Stage Builds**: Optimized build process with separate build and runtime stages
- **Container Registry**: Pushes to GitHub Container Registry (GHCR)
- **Build Caching**: Uses GitHub Actions cache for faster builds
- **Metadata Labels**: Includes build information and VCS references

#### Image Tags
- `latest` - Latest build from default branch
- `{branch}` - Branch-specific tags
- `{branch}-{sha}` - Commit-specific tags
- `{sha}` - Short commit SHA tags

#### Build Arguments
- `BUILD_DATE` - ISO 8601 build timestamp
- `VCS_REF` - Git commit SHA
- `VERSION` - Git branch or tag name

### 3. Terraform Validation

#### Features
- **Format Checking**: Validates Terraform code formatting
- **Configuration Validation**: Ensures Terraform syntax is correct
- **Security Scanning**: Optional security analysis with tfsec
- **Plan Generation**: Creates deployment plans for validation
- **Cost Estimation**: Optional cost analysis with infracost

#### Validation Steps
1. **Format Check** - `terraform fmt -check -recursive`
2. **Initialization** - `terraform init -backend=false`
3. **Validation** - `terraform validate`
4. **Security Scan** - `tfsec .` (if available)
5. **Plan Generation** - `terraform plan -out=tfplan`
6. **Plan Analysis** - Extract resource statistics and changes

#### Generated Files
- `tfplan` - Binary Terraform plan file
- `tfplan.json` - JSON representation of the plan
- `terraform-summary.json` - Validation summary and statistics
- `deployment-checklist.md` - Deployment guide and checklist
- `terraform.tfvars.validation` - Validation variables
- `tfsec-report.json` - Security scan results (optional)
- `infracost-report.json` - Cost estimation (optional)

### 4. Artifact Storage

#### Features
- **Versioned Storage**: Artifacts tagged with commit SHA
- **Comprehensive Manifests**: Detailed metadata for all artifacts
- **Release Archives**: Combined deployment packages
- **Long-term Retention**: 90-day retention for release artifacts

#### Artifact Types
- **Lambda Packages** - Individual function ZIP files
- **Docker Manifests** - Container image metadata
- **Terraform Plans** - Infrastructure deployment plans
- **Build Manifests** - Comprehensive build information

## Usage

### Manual Workflow Dispatch

You can trigger the workflow manually with specific build types:

```bash
# Trigger via GitHub CLI
gh workflow run build-package.yml -f build_type=all
gh workflow run build-package.yml -f build_type=lambda
gh workflow run build-package.yml -f build_type=docker
gh workflow run build-package.yml -f build_type=terraform
```

### Local Development

#### Lambda Packaging
```bash
# Package all Lambda functions
./scripts/build-lambda-packages.sh

# Check generated packages
ls -la lambda_packages/
cat lambda_packages/manifest.json
```

#### Docker Building
```bash
# Build Docker images locally
./scripts/build-docker-images.sh

# Use with docker-compose
docker-compose -f docker-compose.yml -f docker-compose.built.yml up
```

#### Terraform Validation
```bash
# Validate Terraform configuration
./scripts/terraform-validate.sh

# Check validation results
cat terraform/terraform-summary.json
cat terraform/deployment-checklist.md
```

## Configuration

### Environment Variables

#### GitHub Actions
- `REGISTRY` - Container registry URL (default: `ghcr.io`)
- `IMAGE_NAME` - Container image name (default: repository name)
- `AWS_REGION` - AWS region for Terraform validation (default: `eu-central-1`)

#### Local Development
- `TERRAFORM_DIR` - Terraform directory path (default: `terraform`)
- `ENVIRONMENT` - Deployment environment (default: `staging`)
- `PLAN_FILE` - Terraform plan file name (default: `tfplan`)

### Build Scripts Configuration

#### Lambda Packaging (`scripts/build-lambda-packages.sh`)
- `PYTHON_VERSION` - Python runtime version (default: `3.11`)
- `BUILD_DIR` - Temporary build directory prefix
- `PACKAGES_DIR` - Output directory for packages (default: `lambda_packages`)
- `SRC_DIR` - Source code directory (default: `src`)

#### Docker Building (`scripts/build-docker-images.sh`)
- `REGISTRY` - Container registry URL
- `REPOSITORY` - Repository name
- `TAG` - Image tag (default: `latest`)
- `PLATFORMS` - Target platforms (default: `linux/amd64,linux/arm64`)
- `BUILD_CONTEXT` - Docker build context (default: `.`)

## Quality Gates

The workflow includes several quality gates:

### Lambda Packaging Quality Gate
- ✅ All functions packaged successfully
- ✅ Package sizes within Lambda limits (< 50MB)
- ✅ Manifest generation successful

### Docker Build Quality Gate
- ✅ Multi-platform build successful
- ✅ Images pushed to registry
- ✅ Manifest generation successful

### Terraform Validation Quality Gate
- ✅ Configuration validation passed
- ✅ Plan generation successful
- ⚠️ Format check (warning only)
- ⚠️ Security scan (warning only)

### Overall Build Quality Gate
- ✅ Lambda packaging successful
- ✅ Terraform validation successful
- ✅ Artifact storage successful
- ⚠️ Docker build (allowed to fail for forks)

## Troubleshooting

### Common Issues

#### Lambda Package Size Too Large
```bash
# Check package contents
unzip -l lambda_packages/function_name.zip | head -20

# Optimize by removing unnecessary files
find build_dir -name "*.pyc" -delete
find build_dir -name "__pycache__" -type d -exec rm -rf {} +
```

#### Docker Build Failures
```bash
# Check Docker daemon
docker info

# Clear build cache
docker builder prune

# Build with verbose output
docker buildx build --progress=plain .
```

#### Terraform Validation Errors
```bash
# Check Terraform version
terraform version

# Validate specific files
terraform validate terraform/

# Format code
terraform fmt -recursive terraform/
```

### Debug Mode

Enable debug output in scripts:
```bash
# Lambda packaging with debug
DEBUG=1 ./scripts/build-lambda-packages.sh

# Docker building with debug
DEBUG=1 ./scripts/build-docker-images.sh

# Terraform validation with debug
DEBUG=1 ./scripts/terraform-validate.sh
```

## Integration

### CI/CD Pipeline Integration

The build and package workflow integrates with other workflows:

1. **Code Quality** - Must pass before build
2. **Comprehensive Testing** - Must pass before build
3. **Deployment** - Uses build artifacts for deployment

### Deployment Integration

Build artifacts are used by deployment workflows:

```yaml
# Example deployment workflow
- name: Download build artifacts
  uses: actions/download-artifact@v3
  with:
    name: webwunder-release-${{ github.sha }}

- name: Deploy Lambda functions
  run: |
    # Use packaged Lambda functions
    aws lambda update-function-code \
      --function-name my-function \
      --zip-file fileb://lambda_packages/my-function.zip
```

## Security Considerations

### Secrets Management
- No secrets in build artifacts
- Use AWS Secrets Manager for runtime secrets
- GitHub OIDC for AWS authentication

### Container Security
- Multi-stage builds to minimize attack surface
- Non-root user in containers
- Regular base image updates

### Infrastructure Security
- Terraform state stored securely
- IAM roles with least privilege
- Security scanning with tfsec

## Performance Optimization

### Build Performance
- Parallel job execution
- Build caching with GitHub Actions
- Optimized Docker layer caching

### Package Optimization
- Aggressive file cleanup
- Dependency optimization
- Layer sharing for Docker images

### Resource Usage
- Efficient resource allocation
- Cleanup of temporary files
- Optimized artifact storage

## Monitoring and Observability

### Build Metrics
- Build duration tracking
- Package size monitoring
- Success/failure rates

### Artifact Metrics
- Storage usage tracking
- Download statistics
- Retention compliance

### Quality Metrics
- Test coverage in packages
- Security scan results
- Performance benchmarks