#!/bin/bash

# Terraform validation and planning script
# Validates Terraform configuration and generates deployment plans

set -e

# Configuration
TERRAFORM_DIR="${TERRAFORM_DIR:-terraform}"
AWS_REGION="${AWS_REGION:-eu-central-1}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
PLAN_FILE="${PLAN_FILE:-tfplan}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🏗️ Terraform Validation and Planning${NC}"
echo "====================================="

# Change to Terraform directory
cd "$TERRAFORM_DIR"

echo -e "${YELLOW}📋 Configuration:${NC}"
echo "  Terraform Directory: $TERRAFORM_DIR"
echo "  AWS Region: $AWS_REGION"
echo "  Environment: $ENVIRONMENT"
echo "  Plan File: $PLAN_FILE"

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform is not installed${NC}"
    exit 1
fi

# Get Terraform version
TERRAFORM_VERSION=$(terraform version -json | jq -r '.terraform_version')
echo -e "  Terraform Version: ${BLUE}$TERRAFORM_VERSION${NC}"

# Step 1: Format Check
echo -e "\n${BLUE}🎨 Step 1: Format Check${NC}"
if terraform fmt -check -recursive; then
    echo -e "${GREEN}✅ Terraform files are properly formatted${NC}"
    FORMAT_STATUS="passed"
else
    echo -e "${YELLOW}⚠️ Terraform files need formatting${NC}"
    echo -e "${YELLOW}Run 'terraform fmt -recursive' to fix formatting${NC}"
    FORMAT_STATUS="needs_formatting"
fi

# Step 2: Initialize Terraform
echo -e "\n${BLUE}🚀 Step 2: Initialize Terraform${NC}"
terraform init -backend=false -input=false

# Step 3: Validate Configuration
echo -e "\n${BLUE}✅ Step 3: Validate Configuration${NC}"
if terraform validate; then
    echo -e "${GREEN}✅ Terraform configuration is valid${NC}"
    VALIDATION_STATUS="passed"
else
    echo -e "${RED}❌ Terraform configuration validation failed${NC}"
    VALIDATION_STATUS="failed"
    exit 1
fi

# Step 4: Security Scan (if tfsec is available)
echo -e "\n${BLUE}🔒 Step 4: Security Scan${NC}"
if command -v tfsec &> /dev/null; then
    echo "Running tfsec security scan..."
    if tfsec . --format json --out tfsec-report.json; then
        echo -e "${GREEN}✅ Security scan completed${NC}"
        SECURITY_STATUS="passed"
    else
        echo -e "${YELLOW}⚠️ Security scan found issues - check tfsec-report.json${NC}"
        SECURITY_STATUS="warnings"
    fi
else
    echo -e "${YELLOW}ℹ️ tfsec not available, skipping security scan${NC}"
    SECURITY_STATUS="skipped"
fi

# Step 5: Create Validation Variables
echo -e "\n${BLUE}⚙️ Step 5: Create Validation Variables${NC}"
cat > terraform.tfvars.validation << EOF
# Generated validation variables
aws_region = "$AWS_REGION"
environment = "$ENVIRONMENT"
project_name = "webwunder"

# Lambda configuration
lambda_timeout = 30
lambda_memory_size = 512
lambda_runtime = "python3.11"

# API Gateway configuration
api_gateway_stage_name = "$ENVIRONMENT"

# DynamoDB configuration
dynamodb_billing_mode = "PAY_PER_REQUEST"

# Monitoring configuration
cloudwatch_log_retention_days = 14

# Tags
common_tags = {
  Environment = "$ENVIRONMENT"
  Project     = "webwunder"
  ManagedBy   = "terraform"
  Repository  = "webwunder"
}
EOF

echo -e "${GREEN}✅ Validation variables created${NC}"

# Step 6: Generate Terraform Plan
echo -e "\n${BLUE}📋 Step 6: Generate Terraform Plan${NC}"

# Set fake AWS credentials for validation
export AWS_ACCESS_KEY_ID="fake"
export AWS_SECRET_ACCESS_KEY="fake"
export AWS_DEFAULT_REGION="$AWS_REGION"

if terraform plan -var-file=terraform.tfvars.validation -out="$PLAN_FILE" -input=false; then
    echo -e "${GREEN}✅ Terraform plan generated successfully${NC}"
    PLAN_STATUS="success"
else
    echo -e "${RED}❌ Terraform plan generation failed${NC}"
    PLAN_STATUS="failed"
    exit 1
fi

# Step 7: Analyze Plan
echo -e "\n${BLUE}📊 Step 7: Analyze Plan${NC}"
terraform show -json "$PLAN_FILE" > tfplan.json

# Extract plan statistics
RESOURCES_TO_ADD=$(jq -r '.planned_values.root_module.resources // [] | length' tfplan.json)
RESOURCES_TO_CHANGE=$(jq -r '.resource_changes // [] | map(select(.change.actions[] == "update")) | length' tfplan.json)
RESOURCES_TO_DESTROY=$(jq -r '.resource_changes // [] | map(select(.change.actions[] == "delete")) | length' tfplan.json)

echo -e "  Resources to add: ${GREEN}$RESOURCES_TO_ADD${NC}"
echo -e "  Resources to change: ${YELLOW}$RESOURCES_TO_CHANGE${NC}"
echo -e "  Resources to destroy: ${RED}$RESOURCES_TO_DESTROY${NC}"

# Step 8: Generate Resource Summary
echo -e "\n${BLUE}📝 Step 8: Generate Resource Summary${NC}"
cat > terraform-summary.json << EOF
{
  "validation_info": {
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "terraform_version": "$TERRAFORM_VERSION",
    "aws_region": "$AWS_REGION",
    "environment": "$ENVIRONMENT"
  },
  "validation_results": {
    "format_check": "$FORMAT_STATUS",
    "configuration_validation": "$VALIDATION_STATUS",
    "security_scan": "$SECURITY_STATUS",
    "plan_generation": "$PLAN_STATUS"
  },
  "plan_statistics": {
    "resources_to_add": $RESOURCES_TO_ADD,
    "resources_to_change": $RESOURCES_TO_CHANGE,
    "resources_to_destroy": $RESOURCES_TO_DESTROY
  },
  "resource_types": $(jq -r '.planned_values.root_module.resources // [] | group_by(.type) | map({type: .[0].type, count: length}) | sort_by(.type)' tfplan.json)
}
EOF

# Step 9: Generate Deployment Checklist
echo -e "\n${BLUE}📋 Step 9: Generate Deployment Checklist${NC}"
cat > deployment-checklist.md << EOF
# Terraform Deployment Checklist

## Pre-deployment Validation
- [x] Terraform format check: $FORMAT_STATUS
- [x] Configuration validation: $VALIDATION_STATUS
- [x] Security scan: $SECURITY_STATUS
- [x] Plan generation: $PLAN_STATUS

## Resource Changes Summary
- **Resources to add:** $RESOURCES_TO_ADD
- **Resources to change:** $RESOURCES_TO_CHANGE
- **Resources to destroy:** $RESOURCES_TO_DESTROY

## Deployment Steps
1. Review the generated plan file: \`$PLAN_FILE\`
2. Verify resource changes in: \`tfplan.json\`
3. Check security scan results: \`tfsec-report.json\` (if available)
4. Apply the plan: \`terraform apply $PLAN_FILE\`

## Post-deployment Verification
- [ ] Verify all resources are created successfully
- [ ] Test Lambda function deployments
- [ ] Validate API Gateway endpoints
- [ ] Check CloudWatch logs and monitoring
- [ ] Run integration tests against deployed infrastructure

## Rollback Plan
- Keep previous Terraform state backup
- Use \`terraform plan -destroy\` to generate destruction plan if needed
- Monitor CloudWatch alarms for any issues

Generated on: $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

# Step 10: Cost Estimation (if infracost is available)
echo -e "\n${BLUE}💰 Step 10: Cost Estimation${NC}"
if command -v infracost &> /dev/null; then
    echo "Running cost estimation..."
    if infracost breakdown --path . --format json --out infracost-report.json; then
        echo -e "${GREEN}✅ Cost estimation completed${NC}"
        COST_STATUS="completed"
    else
        echo -e "${YELLOW}⚠️ Cost estimation failed${NC}"
        COST_STATUS="failed"
    fi
else
    echo -e "${YELLOW}ℹ️ infracost not available, skipping cost estimation${NC}"
    COST_STATUS="skipped"
fi

# Final Summary
echo -e "\n${GREEN}📊 TERRAFORM VALIDATION SUMMARY${NC}"
echo "================================"
echo -e "Format Check: $([ "$FORMAT_STATUS" = "passed" ] && echo "${GREEN}✅ Passed${NC}" || echo "${YELLOW}⚠️ Needs attention${NC}")"
echo -e "Validation: $([ "$VALIDATION_STATUS" = "passed" ] && echo "${GREEN}✅ Passed${NC}" || echo "${RED}❌ Failed${NC}")"
echo -e "Security Scan: $([ "$SECURITY_STATUS" = "passed" ] && echo "${GREEN}✅ Passed${NC}" || echo "${YELLOW}⚠️ $SECURITY_STATUS${NC}")"
echo -e "Plan Generation: $([ "$PLAN_STATUS" = "success" ] && echo "${GREEN}✅ Success${NC}" || echo "${RED}❌ Failed${NC}")"
echo -e "Cost Estimation: $([ "$COST_STATUS" = "completed" ] && echo "${GREEN}✅ Completed${NC}" || echo "${YELLOW}ℹ️ $COST_STATUS${NC}")"

echo -e "\n${BLUE}📁 Generated Files:${NC}"
echo "  - $PLAN_FILE (Terraform plan)"
echo "  - tfplan.json (Plan in JSON format)"
echo "  - terraform-summary.json (Validation summary)"
echo "  - deployment-checklist.md (Deployment guide)"
echo "  - terraform.tfvars.validation (Validation variables)"
if [ -f "tfsec-report.json" ]; then
    echo "  - tfsec-report.json (Security scan results)"
fi
if [ -f "infracost-report.json" ]; then
    echo "  - infracost-report.json (Cost estimation)"
fi

echo -e "\n${GREEN}🎯 Terraform validation complete!${NC}"

# Return to original directory
cd - > /dev/null