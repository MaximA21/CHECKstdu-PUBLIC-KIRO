# Deployment Guide

This guide covers deploying the application across different environments and platforms.

## Overview

The application supports multiple deployment patterns:
- AWS Lambda (serverless)
- Container deployment (Docker)
- Traditional server deployment
- Local development

Each deployment method uses the same configuration system with environment-specific settings.

## Environment Setup

### Prerequisites

- Python 3.9+
- AWS CLI (for AWS deployments)
- Docker (for container deployments)
- Terraform (for infrastructure)

### Environment Variables

Set these environment variables for each deployment:

```bash
# Required
export APP_ENVIRONMENT=production  # development, testing, staging, production

# AWS Configuration (if using AWS services)
export AWS_REGION=eu-central-1
export AWS_PROFILE=your-profile

# Optional Overrides
export DB_PROVIDER=aws_dynamodb
export MSG_PROVIDER=aws_sqs
export LOG_PROVIDER=aws_cloudwatch
export LOG_LEVEL=INFO
export DEBUG=false
```

## AWS Lambda Deployment

### 1. Infrastructure Setup

Deploy AWS infrastructure using Terraform:

```bash
cd terraform
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply
```

### 2. Lambda Package Preparation

Build Lambda packages:

```bash
# Build all Lambda functions
./lambda_functions/build.sh

# Build specific function
cd lambda_functions/search_handler
zip -r ../lambda_packages/search_handler.zip .
```

### 3. Configuration

Create environment-specific configuration:

```bash
# Production Lambda environment variables
export APP_ENVIRONMENT=production
export DB_PROVIDER=aws_dynamodb
export DB_REGION=eu-central-1
export DB_TABLE_PREFIX=prod_
export MSG_PROVIDER=aws_sqs
export MSG_REGION=eu-central-1
export MSG_QUEUE_PREFIX=prod_
export LOG_PROVIDER=aws_cloudwatch
export LOG_LEVEL=INFO
export LOG_GROUP=/aws/lambda/webwunder-prod
```

### 4. Deployment

Deploy using AWS CLI or Terraform:

```bash
# Update function code
aws lambda update-function-code \
  --function-name search_handler \
  --zip-file fileb://lambda_packages/search_handler.zip

# Update environment variables
aws lambda update-function-configuration \
  --function-name search_handler \
  --environment Variables='{
    "APP_ENVIRONMENT":"production",
    "DB_PROVIDER":"aws_dynamodb",
    "DB_REGION":"eu-central-1"
  }'
```

### 5. Verification

Test Lambda functions:

```bash
# Test search handler
aws lambda invoke \
  --function-name search_handler \
  --payload '{"address": {"street": "Test St", "city": "Berlin"}}' \
  response.json
```

## Container Deployment

### 1. Build Container

Build Docker image:

```bash
# Build production image
docker build -t webwunder-app:latest .

# Build with specific environment
docker build --build-arg APP_ENVIRONMENT=production -t webwunder-app:prod .
```

### 2. Configuration

Create environment file:

```bash
# .env.production
APP_ENVIRONMENT=production
DB_PROVIDER=aws_dynamodb
DB_REGION=eu-central-1
DB_TABLE_PREFIX=prod_
MSG_PROVIDER=aws_sqs
MSG_REGION=eu-central-1
LOG_PROVIDER=aws_cloudwatch
LOG_LEVEL=INFO
```

### 3. Run Container

Run with Docker:

```bash
# Run with environment file
docker run --env-file .env.production -p 8080:8080 -p 8081:8081 webwunder-app:prod

# Run with inline environment variables
docker run \
  -e APP_ENVIRONMENT=production \
  -e DB_PROVIDER=aws_dynamodb \
  -e DB_REGION=eu-central-1 \
  -p 8080:8080 -p 8081:8081 \
  webwunder-app:prod
```

### 4. Docker Compose

Use Docker Compose for multi-service deployment:

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  app:
    build: .
    environment:
      - APP_ENVIRONMENT=production
      - DB_PROVIDER=aws_dynamodb
      - DB_REGION=eu-central-1
    ports:
      - "8080:8080"
      - "8081:8081"
    restart: unless-stopped
  
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - app
```

Deploy with:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 5. Health Checks

Configure health checks:

```dockerfile
# In Dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

## Kubernetes Deployment

### 1. Configuration

Create ConfigMap and Secret:

```yaml
# config-map.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: webwunder-config
data:
  APP_ENVIRONMENT: "production"
  DB_PROVIDER: "aws_dynamodb"
  DB_REGION: "eu-central-1"
  LOG_PROVIDER: "aws_cloudwatch"
  LOG_LEVEL: "INFO"

---
apiVersion: v1
kind: Secret
metadata:
  name: webwunder-secrets
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: "your-access-key"
  AWS_SECRET_ACCESS_KEY: "your-secret-key"
```

### 2. Deployment

Create deployment:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webwunder-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: webwunder-app
  template:
    metadata:
      labels:
        app: webwunder-app
    spec:
      containers:
      - name: app
        image: webwunder-app:latest
        ports:
        - containerPort: 8080
        - containerPort: 8081
        envFrom:
        - configMapRef:
            name: webwunder-config
        - secretRef:
            name: webwunder-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 3. Service

Create service:

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: webwunder-service
spec:
  selector:
    app: webwunder-app
  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: websocket
    port: 8081
    targetPort: 8081
  type: LoadBalancer
```

Deploy:

```bash
kubectl apply -f config-map.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

## Development Deployment

### 1. Local Setup

Set up development environment:

```bash
# Install dependencies
pip install -r requirements.txt

# Set development environment
export APP_ENVIRONMENT=development
export DEBUG=true
```

### 2. Run Services

Start development servers:

```bash
# HTTP server
python -m src.presentation.http_server

# WebSocket server
python -m src.presentation.websocket_server

# Or use the start scripts
./scripts/start-http-server.sh
./scripts/start-websocket-server.sh
```

### 3. Testing

Run tests with different configurations:

```bash
# Unit tests with mock services
APP_ENVIRONMENT=testing python -m pytest tests/

# Integration tests with AWS services
APP_ENVIRONMENT=staging python -m pytest tests/integration/

# End-to-end tests
python run_comprehensive_tests.py
```

## Environment-Specific Deployments

### Development

```bash
# Configuration
export APP_ENVIRONMENT=development
export DB_PROVIDER=mock
export MSG_PROVIDER=mock
export LOG_PROVIDER=console
export LOG_LEVEL=DEBUG
export DEBUG=true

# Run locally
python -m src.presentation.http_server
```

### Testing

```bash
# Configuration
export APP_ENVIRONMENT=testing
export DB_PROVIDER=mock
export MSG_PROVIDER=mock
export LOG_PROVIDER=console

# Run tests
python -m pytest
```

### Staging

```bash
# Configuration
export APP_ENVIRONMENT=staging
export DB_PROVIDER=aws_dynamodb
export DB_REGION=eu-central-1
export DB_TABLE_PREFIX=staging_
export MSG_PROVIDER=aws_sqs
export LOG_PROVIDER=aws_cloudwatch
export LOG_GROUP=/aws/lambda/webwunder-staging

# Deploy to staging
terraform workspace select staging
terraform apply -var-file="staging.tfvars"
```

### Production

```bash
# Configuration
export APP_ENVIRONMENT=production
export DB_PROVIDER=aws_dynamodb
export DB_REGION=eu-central-1
export DB_TABLE_PREFIX=prod_
export MSG_PROVIDER=aws_sqs
export LOG_PROVIDER=aws_cloudwatch
export LOG_GROUP=/aws/lambda/webwunder-prod

# Deploy to production
terraform workspace select production
terraform apply -var-file="production.tfvars"
```

## Monitoring and Logging

### CloudWatch Integration

For AWS deployments:

```bash
# View logs
aws logs tail /aws/lambda/webwunder-prod --follow

# Create log insights query
aws logs start-query \
  --log-group-name /aws/lambda/webwunder-prod \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/'
```

### Application Metrics

Monitor application health:

```bash
# Health check endpoint
curl http://localhost:8080/health

# Metrics endpoint
curl http://localhost:8080/metrics

# Configuration endpoint
curl http://localhost:8080/config
```

## Troubleshooting

### Common Issues

**Configuration Loading Errors**
```bash
# Check configuration
python -c "
from src.infrastructure.config.loader import ConfigLoader
loader = ConfigLoader()
try:
    config = loader.load_config()
    print('Configuration loaded successfully')
    print(f'Environment: {config.environment.value}')
except Exception as e:
    print(f'Error: {e}')
"
```

**Service Connection Issues**
```bash
# Test AWS connectivity
aws sts get-caller-identity

# Test DynamoDB access
aws dynamodb list-tables --region eu-central-1

# Test SQS access
aws sqs list-queues --region eu-central-1
```

**Container Issues**
```bash
# Check container logs
docker logs webwunder-app

# Check container health
docker inspect webwunder-app | grep Health

# Debug container
docker exec -it webwunder-app /bin/bash
```

### Validation

Validate deployment:

```bash
# Check configuration
python -c "
from src.infrastructure.config.loader import ConfigLoader
from src.infrastructure.config.validator import ConfigValidator

loader = ConfigLoader()
config = loader.load_config()
results = ConfigValidator.get_all_validation_results(config)

for category, issues in results.items():
    if issues:
        print(f'{category}: {issues}')
"
```

## Security Considerations

### Secrets Management

- Use AWS Secrets Manager for production secrets
- Use environment variables for configuration
- Never commit secrets to version control
- Rotate credentials regularly

### Network Security

- Use VPC for AWS deployments
- Configure security groups properly
- Use HTTPS/WSS in production
- Implement rate limiting

### Access Control

- Use IAM roles for AWS services
- Implement least privilege access
- Monitor access logs
- Use service accounts for Kubernetes

## Performance Optimization

### Lambda Optimization

- Use provisioned concurrency for critical functions
- Optimize package size
- Configure appropriate memory settings
- Monitor cold start metrics

### Container Optimization

- Use multi-stage builds
- Optimize image size
- Configure resource limits
- Use horizontal pod autoscaling

### Database Optimization

- Configure appropriate read/write capacity
- Use DynamoDB auto-scaling
- Monitor performance metrics
- Implement caching where appropriate