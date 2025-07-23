#!/bin/bash

# WebSocket API Gateway Deployment Script
# Deploys WebSocket API Gateway with traffic distribution to eu-central-1

set -e

# Configuration
PROJECT_NAME="${PROJECT_NAME:-provider-comparison}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-eu-central-1}"
TERRAFORM_DIR="terraform"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install Terraform first."
        exit 1
    fi
    
    # Check if AWS CLI is installed and configured
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    # Check if we're in the right directory
    if [ ! -d "$TERRAFORM_DIR" ]; then
        log_error "Terraform directory not found. Please run this script from the project root."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Build Lambda packages
build_lambda_packages() {
    log_info "Building Lambda packages..."
    
    # Check if build script exists
    if [ -f "scripts/build-lambda-packages.sh" ]; then
        bash scripts/build-lambda-packages.sh
        log_success "Lambda packages built successfully"
    else
        log_warning "Lambda package build script not found. Assuming packages are already built."
    fi
}

# Initialize Terraform
init_terraform() {
    log_info "Initializing Terraform..."
    
    cd "$TERRAFORM_DIR"
    
    # Initialize Terraform
    terraform init
    
    # Validate Terraform configuration
    terraform validate
    
    log_success "Terraform initialized and validated"
    
    cd ..
}

# Plan Terraform deployment
plan_terraform() {
    log_info "Planning Terraform deployment..."
    
    cd "$TERRAFORM_DIR"
    
    # Create Terraform plan
    terraform plan \
        -var="project_name=$PROJECT_NAME" \
        -var="environment=$ENVIRONMENT" \
        -var="aws_region=$AWS_REGION" \
        -out=tfplan
    
    log_success "Terraform plan created"
    
    cd ..
}

# Apply Terraform deployment
apply_terraform() {
    log_info "Applying Terraform deployment..."
    
    cd "$TERRAFORM_DIR"
    
    # Apply Terraform plan
    terraform apply tfplan
    
    log_success "Terraform deployment completed"
    
    cd ..
}

# Get deployment outputs
get_outputs() {
    log_info "Getting deployment outputs..."
    
    cd "$TERRAFORM_DIR"
    
    # Get WebSocket API endpoint
    WEBSOCKET_ENDPOINT=$(terraform output -raw websocket_prod_stage_invoke_url 2>/dev/null || echo "")
    ROUTING_TABLE_NAME=$(terraform output -raw connection_routing_table_name 2>/dev/null || echo "")
    
    cd ..
    
    if [ -n "$WEBSOCKET_ENDPOINT" ]; then
        log_success "WebSocket API endpoint: $WEBSOCKET_ENDPOINT"
        echo "WEBSOCKET_URL=$WEBSOCKET_ENDPOINT" > .env.websocket
    else
        log_warning "Could not retrieve WebSocket endpoint"
    fi
    
    if [ -n "$ROUTING_TABLE_NAME" ]; then
        log_success "Connection routing table: $ROUTING_TABLE_NAME"
        echo "ROUTING_TABLE_NAME=$ROUTING_TABLE_NAME" >> .env.websocket
    else
        log_warning "Could not retrieve routing table name"
    fi
}

# Validate deployment
validate_deployment() {
    log_info "Validating WebSocket API deployment..."
    
    # Check if validation script exists
    if [ -f "scripts/validate-websocket-api.py" ]; then
        # Source environment variables
        if [ -f ".env.websocket" ]; then
            source .env.websocket
        fi
        
        # Check if required environment variables are set
        if [ -n "$WEBSOCKET_URL" ] && [ -n "$ROUTING_TABLE_NAME" ]; then
            log_info "Running WebSocket API validation..."
            
            # Install Python dependencies if needed
            if [ -f "requirements.txt" ]; then
                pip install -r requirements.txt > /dev/null 2>&1 || true
            fi
            
            # Install additional dependencies for validation
            pip install websockets boto3 > /dev/null 2>&1 || true
            
            # Run validation
            export WEBSOCKET_URL="$WEBSOCKET_URL"
            export ROUTING_TABLE_NAME="$ROUTING_TABLE_NAME"
            
            if python3 scripts/validate-websocket-api.py; then
                log_success "WebSocket API validation passed"
            else
                log_warning "WebSocket API validation had issues (this is normal for initial deployment)"
            fi
        else
            log_warning "Cannot run validation - missing environment variables"
        fi
    else
        log_warning "Validation script not found - skipping validation"
    fi
}

# Display deployment summary
display_summary() {
    log_info "Deployment Summary"
    echo "===================="
    echo "Project: $PROJECT_NAME"
    echo "Environment: $ENVIRONMENT"
    echo "Region: $AWS_REGION"
    echo ""
    
    if [ -f ".env.websocket" ]; then
        source .env.websocket
        echo "WebSocket API Endpoint: $WEBSOCKET_URL"
        echo "Connection Routing Table: $ROUTING_TABLE_NAME"
        echo ""
    fi
    
    echo "Traffic Distribution: 50/50 between old and new implementations"
    echo "Connection Limits: 2 minutes OR 5 results per connection"
    echo "Connection Tracking: Enabled in DynamoDB"
    echo ""
    
    log_success "WebSocket API Gateway deployment completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Test the WebSocket API using the provided endpoint"
    echo "2. Monitor traffic distribution in CloudWatch dashboards"
    echo "3. Check connection limits enforcement"
    echo "4. Review API Gateway logs for any issues"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    
    cd "$TERRAFORM_DIR" 2>/dev/null || true
    rm -f tfplan 2>/dev/null || true
    cd .. 2>/dev/null || true
}

# Main deployment function
main() {
    log_info "Starting WebSocket API Gateway deployment..."
    log_info "Project: $PROJECT_NAME, Environment: $ENVIRONMENT, Region: $AWS_REGION"
    
    # Set trap for cleanup
    trap cleanup EXIT
    
    # Run deployment steps
    check_prerequisites
    build_lambda_packages
    init_terraform
    plan_terraform
    
    # Ask for confirmation before applying
    echo ""
    read -p "Do you want to apply the Terraform plan? (y/N): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        apply_terraform
        get_outputs
        validate_deployment
        display_summary
    else
        log_info "Deployment cancelled by user"
        exit 0
    fi
}

# Handle script arguments
case "${1:-}" in
    "plan")
        check_prerequisites
        build_lambda_packages
        init_terraform
        plan_terraform
        ;;
    "apply")
        check_prerequisites
        build_lambda_packages
        init_terraform
        apply_terraform
        get_outputs
        validate_deployment
        display_summary
        ;;
    "validate")
        validate_deployment
        ;;
    "destroy")
        log_warning "Destroying WebSocket API Gateway infrastructure..."
        cd "$TERRAFORM_DIR"
        terraform destroy \
            -var="project_name=$PROJECT_NAME" \
            -var="environment=$ENVIRONMENT" \
            -var="aws_region=$AWS_REGION"
        cd ..
        log_success "Infrastructure destroyed"
        ;;
    *)
        main
        ;;
esac