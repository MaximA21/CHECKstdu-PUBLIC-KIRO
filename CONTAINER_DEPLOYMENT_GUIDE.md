# Container Deployment Guide

This guide explains how to deploy the WebWunder application using containers with the new enterprise architecture.

## Overview

The container deployment supports multiple deployment patterns:
- **HTTP Server**: REST API endpoints using the same use cases as Lambda handlers
- **WebSocket Server**: Real-time communication using abstracted connection management
- **Combined Deployment**: Both HTTP and WebSocket in a single container
- **Microservices**: Separate containers for different services

## Quick Start

### 1. Development Environment

```bash
# Start all services in development mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 2. Production Environment

```bash
# Build and start production services
APP_ENVIRONMENT=production docker-compose -f docker-compose.yml up -d

# Scale services
docker-compose up -d --scale webwunder-api=3 --scale webwunder-websocket=2
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENVIRONMENT` | Application environment (development/production) | `development` |
| `PORT` | HTTP server port | `8080` |
| `WS_PORT` | WebSocket server port | `8081` |
| `CONFIG_DIR` | Configuration directory path | `config` |
| `DB_PROVIDER` | Database provider (aws_dynamodb/mock) | `mock` |
| `MSG_PROVIDER` | Messaging provider (aws_sqs/mock) | `mock` |
| `LOG_PROVIDER` | Logging provider (aws_cloudwatch/console) | `console` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Configuration Files

Configuration files are located in the `config/` directory:

- `development.json` - Development environment settings
- `production.json` - Production environment settings
- `container.json` - Container-specific settings
- `testing.json` - Testing environment settings

## Deployment Patterns

### 1. Single Container (HTTP + WebSocket)

```yaml
# docker-compose.single.yml
version: '3.8'
services:
  webwunder:
    build: .
    ports:
      - "8080:8080"
      - "8081:8081"
    environment:
      - APP_ENVIRONMENT=production
    command: ["sh", "-c", "python -m src.presentation.http_server & python -m src.presentation.websocket_server & wait"]
```

### 2. Microservices Architecture

```yaml
# docker-compose.microservices.yml
version: '3.8'
services:
  api-gateway:
    build: .
    ports:
      - "8080:8080"
    command: ["python", "-m", "src.presentation.http_server"]
    
  websocket-service:
    build: .
    ports:
      - "8081:8081"
    command: ["python", "-m", "src.presentation.websocket_server"]
    
  search-service:
    build: .
    command: ["python", "-m", "src.services.search_service"]
    
  share-service:
    build: .
    command: ["python", "-m", "src.services.share_service"]
```

### 3. Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webwunder-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: webwunder-api
  template:
    metadata:
      labels:
        app: webwunder-api
    spec:
      containers:
      - name: webwunder-api
        image: webwunder:latest
        ports:
        - containerPort: 8080
        env:
        - name: APP_ENVIRONMENT
          value: "production"
        - name: DB_PROVIDER
          value: "aws_dynamodb"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

## Service Endpoints

### HTTP API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/search` | POST | Start search |
| `/api/search/{request_id}/status` | GET | Get search status |
| `/api/share/{share_token}` | GET | Get shared results |
| `/api/share/{share_token}/stats` | GET | Get share statistics |
| `/api/share/{share_token}/extend` | POST | Extend share expiration |

### WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `/ws` | WebSocket connection |

### WebSocket Message Types

```json
// Ping message
{
  "type": "ping",
  "data": {}
}

// Subscribe to updates
{
  "type": "subscribe",
  "data": {
    "topic": "search_updates"
  }
}

// Status update request
{
  "type": "status_update",
  "data": {}
}
```

## Monitoring and Health Checks

### Health Check Endpoint

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "environment": "production"
}
```

### Docker Health Checks

The containers include built-in health checks:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1
```

### Prometheus Metrics

Metrics are available at `/metrics` endpoint (if enabled):

```bash
curl http://localhost:8080/metrics
```

## Scaling and Load Balancing

### Horizontal Scaling

```bash
# Scale API service
docker-compose up -d --scale webwunder-api=5

# Scale WebSocket service
docker-compose up -d --scale webwunder-websocket=3
```

### Load Balancer Configuration

Nginx is configured as a reverse proxy with:
- Rate limiting
- Health checks
- WebSocket support
- SSL termination (optional)

## Security

### Container Security

- Non-root user execution
- Minimal base image (Python slim)
- Security headers in Nginx
- Network isolation

### Environment Variables

Sensitive configuration should use environment variables:

```bash
# AWS credentials (for production)
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=eu-central-1

# Database credentials
export DB_CONNECTION_STRING=your_connection_string
```

## Troubleshooting

### Common Issues

1. **Port conflicts**
   ```bash
   # Check port usage
   netstat -tulpn | grep :8080
   
   # Use different ports
   PORT=8090 WS_PORT=8091 docker-compose up
   ```

2. **Configuration not loading**
   ```bash
   # Check config directory
   docker-compose exec webwunder-api ls -la /app/config/
   
   # Check environment variables
   docker-compose exec webwunder-api env | grep APP_
   ```

3. **WebSocket connection issues**
   ```bash
   # Test WebSocket connection
   wscat -c ws://localhost:8081/ws
   
   # Check WebSocket logs
   docker-compose logs webwunder-websocket
   ```

### Debugging

Enable debug mode:

```bash
DEBUG=true LOG_LEVEL=DEBUG docker-compose up
```

View detailed logs:

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f webwunder-api

# Follow logs with timestamps
docker-compose logs -f -t
```

## Performance Tuning

### Container Resources

```yaml
services:
  webwunder-api:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

### Connection Limits

Adjust connection limits in configuration:

```json
{
  "container": {
    "max_connections": 1000,
    "request_timeout_seconds": 30,
    "keepalive_timeout": 65
  }
}
```

## Migration from Lambda

### Key Differences

1. **Persistent connections**: Containers maintain state between requests
2. **Resource management**: Manual scaling vs automatic Lambda scaling
3. **Cold starts**: Eliminated in container deployment
4. **Cost model**: Fixed costs vs pay-per-request

### Migration Steps

1. Update configuration to use container-specific settings
2. Test with mock providers first
3. Gradually migrate traffic using load balancer
4. Monitor performance and adjust resources
5. Update monitoring and alerting

## Best Practices

1. **Use multi-stage builds** to minimize image size
2. **Implement proper health checks** for container orchestration
3. **Use environment-specific configurations**
4. **Monitor resource usage** and scale accordingly
5. **Implement graceful shutdown** handling
6. **Use secrets management** for sensitive data
7. **Regular security updates** for base images
8. **Implement proper logging** and monitoring