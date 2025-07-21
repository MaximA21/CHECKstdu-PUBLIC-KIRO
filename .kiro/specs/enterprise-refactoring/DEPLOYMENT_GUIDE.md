# Enterprise Refactoring Deployment Guide

This guide covers deployment strategies for the refactored enterprise architecture, supporting Lambda, container, and traditional server deployment patterns.

## Overview

The refactored architecture supports multiple deployment patterns through dependency injection and clean architecture principles:

- **AWS Lambda Deployment**: Serverless functions with AWS-specific adapters
- **Container Deployment**: Docker containers with HTTP/WebSocket servers
- **Traditional Server Deployment**: Standard server deployment with process management

## Prerequisites

### Common Requirements
- Python 3.9+
- Access to configuration files in `config/` directory
- Environment-specific configuration (development, staging, production)

### AWS Lambda Requirements
- AWS CLI configured with appropriate permissions
- Terraform for infrastructure provisioning
- Lambda deployment packages built with `lambda_functions/build.sh`

### Container Requirements
- Docker and Docker Compose
- Container registry access (if deploying to cloud)
- Load balancer configuration (for production)

### Traditional Server Requirements
- Process manager (systemd, supervisor, or PM2)
- Reverse proxy (nginx, Apache)
- SSL certificates for HTTPS

## AWS Lambda Deployment

### 1. Build Lambda Packages

```bash
# Build all Lambda functions
cd lambda_functions
./build.sh

# Build specific function
cd lambda_functions/search_handler
zip -r ../../lambda_packages/search_handler.zip .
```

### 2. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply
```

### 3. Configuration

Lambda functions automatically use AWS-specific adapters based on environment detection:

```json
{
  "environment": "production",
  "database": {
    "provider": "aws_dynamodb",
    "region": "us-east-1",
    "table_prefix": "prod_"
  },
  "messaging": {
    "provider": "aws_sqs",
    "region": "us-east-1",
    "queue_prefix": "prod_"
  },
  "logging": {
    "provider": "aws_cloudwatch",
    "level": "INFO",
    "structured": true
  }
}
```

### 4. Environment Variables

Set these environment variables for Lambda functions:

```bash
CONFIG_ENV=production
AWS_REGION=us-east-1
LOG_LEVEL=INFO
```

### 5. Testing Lambda Deployment

```bash
# Test individual Lambda function
aws lambda invoke --function-name search_handler \
  --payload '{"address": {"street": "Main St", "city": "Berlin"}}' \
  response.json

# Run comprehensive tests
python run_comprehensive_tests.py --environment production
```

## Container Deployment

### 1. Build Container Images

```bash
# Build application image
docker build -t enterprise-app:latest .

# Build with specific tag
docker build -t enterprise-app:v1.0.0 .
```

### 2. Configuration

Container deployment uses environment-specific configuration:

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    image: enterprise-app:latest
    environment:
      - CONFIG_ENV=production
      - DATABASE_PROVIDER=aws_dynamodb
      - MESSAGING_PROVIDER=aws_sqs
      - LOGGING_PROVIDER=aws_cloudwatch
    ports:
      - "8000:8000"
      - "8001:8001"
```

### 3. Deploy with Docker Compose

```bash
# Development deployment
docker-compose up -d

# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 4. Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: enterprise-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: enterprise-app
  template:
    metadata:
      labels:
        app: enterprise-app
    spec:
      containers:
      - name: app
        image: enterprise-app:v1.0.0
        ports:
        - containerPort: 8000
        - containerPort: 8001
        env:
        - name: CONFIG_ENV
          value: "production"
        - name: DATABASE_PROVIDER
          value: "aws_dynamodb"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### 5. Health Checks

The application includes health check endpoints:

```bash
# HTTP health check
curl http://localhost:8000/health

# WebSocket health check
curl http://localhost:8001/health
```

## Traditional Server Deployment

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install nginx supervisor
```

### 2. Application Configuration

```bash
# Create application user
sudo useradd -r -s /bin/false enterprise-app

# Create directories
sudo mkdir -p /opt/enterprise-app
sudo mkdir -p /var/log/enterprise-app
sudo chown enterprise-app:enterprise-app /var/log/enterprise-app
```

### 3. Process Management with Supervisor

```ini
# /etc/supervisor/conf.d/enterprise-app.conf
[program:enterprise-http]
command=/opt/enterprise-app/venv/bin/python -m src.presentation.http_server
directory=/opt/enterprise-app
user=enterprise-app
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/enterprise-app/http.log

[program:enterprise-websocket]
command=/opt/enterprise-app/venv/bin/python -m src.presentation.websocket_server
directory=/opt/enterprise-app
user=enterprise-app
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/enterprise-app/websocket.log
```

### 4. Nginx Configuration

```nginx
# /etc/nginx/sites-available/enterprise-app
upstream http_backend {
    server 127.0.0.1:8000;
}

upstream websocket_backend {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://http_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws {
        proxy_pass http://websocket_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 5. SSL Configuration

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Environment-Specific Configurations

### Development Environment

```json
{
  "environment": "development",
  "database": {
    "provider": "mock",
    "connection_string": null
  },
  "messaging": {
    "provider": "mock",
    "connection_string": null
  },
  "logging": {
    "provider": "console",
    "level": "DEBUG",
    "structured": false
  },
  "provider_configs": {
    "mock_providers": true,
    "response_delay": 0.1
  }
}
```

### Staging Environment

```json
{
  "environment": "staging",
  "database": {
    "provider": "aws_dynamodb",
    "region": "us-east-1",
    "table_prefix": "staging_"
  },
  "messaging": {
    "provider": "aws_sqs",
    "region": "us-east-1",
    "queue_prefix": "staging_"
  },
  "logging": {
    "provider": "aws_cloudwatch",
    "level": "DEBUG",
    "structured": true
  }
}
```

### Production Environment

```json
{
  "environment": "production",
  "database": {
    "provider": "aws_dynamodb",
    "region": "us-east-1",
    "table_prefix": "prod_"
  },
  "messaging": {
    "provider": "aws_sqs",
    "region": "us-east-1",
    "queue_prefix": "prod_"
  },
  "logging": {
    "provider": "aws_cloudwatch",
    "level": "INFO",
    "structured": true
  }
}
```

## Monitoring and Observability

### Application Metrics

```python
# Health check endpoints provide metrics
GET /health
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "dependencies": {
    "database": "connected",
    "messaging": "connected",
    "external_providers": "healthy"
  }
}
```

### Logging Configuration

```python
# Structured logging in production
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "search_handler",
  "request_id": "req_123",
  "message": "Search completed successfully",
  "context": {
    "address": "Berlin, Germany",
    "providers_count": 4,
    "response_time_ms": 250
  }
}
```

### Error Monitoring

The application includes comprehensive error monitoring:

```python
# Error tracking with context
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "ERROR",
  "service": "provider_adapter",
  "error_type": "ProviderUnavailableException",
  "message": "ByteMe provider timeout",
  "context": {
    "provider": "byteme",
    "timeout_seconds": 30,
    "retry_count": 3
  },
  "stack_trace": "..."
}
```

## Performance Considerations

### Lambda Deployment
- Cold start optimization through dependency injection container caching
- Memory allocation based on function complexity (256MB - 1GB)
- Concurrent execution limits to prevent resource exhaustion

### Container Deployment
- Resource limits based on expected load
- Horizontal scaling with load balancers
- Connection pooling for database and external services

### Traditional Server Deployment
- Process management with automatic restarts
- Resource monitoring and alerting
- Log rotation and cleanup

## Security Considerations

### Network Security
- VPC configuration for AWS resources
- Security groups and NACLs
- SSL/TLS encryption for all communications

### Application Security
- Input validation at all entry points
- Secure configuration management
- Regular dependency updates

### Access Control
- IAM roles and policies for AWS resources
- Service-to-service authentication
- API rate limiting and throttling

## Backup and Recovery

### Data Backup
- DynamoDB point-in-time recovery
- Configuration backup to version control
- Log archival to long-term storage

### Disaster Recovery
- Multi-region deployment for critical services
- Automated failover procedures
- Recovery time objectives (RTO) and recovery point objectives (RPO)

## Next Steps

1. Choose appropriate deployment pattern based on requirements
2. Configure environment-specific settings
3. Set up monitoring and alerting
4. Implement backup and recovery procedures
5. Establish deployment pipelines and CI/CD

For troubleshooting common issues, see the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md).
For migration from the old architecture, see the [Migration Guide](MIGRATION_GUIDE.md).