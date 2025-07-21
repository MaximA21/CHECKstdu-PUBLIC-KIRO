# Design Document

## Overview

This design outlines the systematic optimization of logging levels across all Lambda functions to improve production monitoring, debugging capabilities, and operational visibility. The solution will establish consistent logging patterns, appropriate log levels, and configurable logging behavior while maintaining backward compatibility.

## Architecture

### Current State Analysis

All Lambda functions currently use a hardcoded `logging.INFO` level with inconsistent logging patterns:
- Event details logged at INFO level (should be DEBUG)
- Performance metrics mixed between INFO and no logging
- Error handling varies in verbosity and level usage
- No environment-based log level configuration

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Logging Architecture                      │
├─────────────────────────────────────────────────────────────┤
│  Environment Variable: LOG_LEVEL (DEBUG|INFO|WARNING|ERROR) │
│                           ↓                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │            Centralized Logger Configuration             │ │
│  │  - Environment-based level setting                     │ │
│  │  - Consistent formatter across all functions           │ │
│  │  - Structured logging patterns                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           ↓                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Function-Specific Loggers                 │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │ │
│  │  │   Lambda    │ │   Lambda    │ │   Lambda    │  ...  │ │
│  │  │ Function 1  │ │ Function 2  │ │ Function N  │       │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘       │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Logger Configuration Module

**Purpose**: Centralized logging configuration with environment-based level setting

**Interface**:
```python
def configure_logger(logger_name: str = None) -> logging.Logger:
    """Configure logger with appropriate level and formatting"""
    
def get_log_level() -> int:
    """Get log level from environment variable with fallback"""
```

**Implementation Details**:
- Read `LOG_LEVEL` environment variable
- Default to `INFO` for production, `DEBUG` for development
- Apply consistent formatting across all functions
- Support for structured logging patterns

### 2. Logging Level Classification

**DEBUG Level Usage**:
- Detailed event data (`logger.debug(f"Event: {json.dumps(event)}")`)
- Internal processing steps
- Cache hit/miss details
- Request/response payloads
- Performance timing details
- Configuration value logging

**INFO Level Usage**:
- Function startup/completion
- Key business metrics (offer counts, processing times)
- Successful operation summaries
- Important state changes
- External service integration results

**WARNING Level Usage**:
- Recoverable errors with fallback behavior
- Performance degradation indicators
- Missing optional configurations
- Deprecated feature usage

**ERROR Level Usage**:
- Unrecoverable errors
- Critical configuration missing
- External service failures
- Data corruption or validation failures

### 3. Function-Specific Patterns

**Lambda Handler Pattern**:
```python
def lambda_handler(event, context):
    logger.info(f"{function_name} started")
    logger.debug(f"Event received: {json.dumps(event)}")
    
    try:
        # Business logic
        logger.info("Operation completed successfully")
        return result
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        raise
```

**Performance Logging Pattern**:
```python
start_time = time.time()
# ... processing ...
execution_time = (time.time() - start_time) * 1000
logger.info(f"Processing completed in {execution_time:.1f}ms")
logger.debug(f"Detailed timing breakdown: {timing_details}")
```

## Data Models

### Log Level Configuration

```python
@dataclass
class LogConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    enable_structured: bool = False
    
    @classmethod
    def from_environment(cls) -> 'LogConfig':
        return cls(
            level=os.environ.get('LOG_LEVEL', 'INFO'),
            enable_structured=os.environ.get('STRUCTURED_LOGS', 'false').lower() == 'true'
        )
```

### Logging Categories

```python
class LogCategory(Enum):
    STARTUP = "startup"
    BUSINESS_LOGIC = "business"
    PERFORMANCE = "performance"
    EXTERNAL_API = "external"
    ERROR_HANDLING = "error"
    CACHE_OPERATIONS = "cache"
    DATA_PROCESSING = "data"
```

## Error Handling

### Logging Configuration Errors
- If `LOG_LEVEL` environment variable is invalid, fall back to `INFO`
- Log configuration errors at `WARNING` level
- Ensure logging never breaks application functionality

### Runtime Logging Errors
- Catch and handle JSON serialization errors in debug logs
- Implement safe string formatting to prevent logging crashes
- Provide fallback logging for critical error scenarios

### Backward Compatibility
- Maintain existing log message content where appropriate
- Ensure no breaking changes to log parsing systems
- Gradual migration approach for production systems

## Testing Strategy

### Unit Testing
- Test logger configuration with different environment variables
- Verify log level filtering works correctly
- Test log message formatting and content
- Validate error handling in logging scenarios

### Integration Testing
- Test logging behavior across all Lambda functions
- Verify log level changes don't break existing monitoring
- Test performance impact of different log levels
- Validate structured logging output format

### Performance Testing
- Measure logging overhead at different levels
- Test impact of DEBUG level logging on function performance
- Validate log volume management in high-traffic scenarios

### Production Validation
- Gradual rollout with monitoring
- A/B testing of log levels in non-critical functions
- Monitor log volume and CloudWatch costs
- Validate alerting and monitoring systems compatibility

## Implementation Phases

### Phase 1: Core Infrastructure
- Create centralized logger configuration
- Implement environment-based log level setting
- Add logging utility functions

### Phase 2: Function Migration
- Update each Lambda function systematically
- Migrate logging statements to appropriate levels
- Add performance and business metric logging

### Phase 3: Optimization and Monitoring
- Fine-tune log levels based on production feedback
- Implement structured logging where beneficial
- Add monitoring for log volume and performance impact

## Migration Strategy

### Risk Mitigation
- Feature flag for new logging behavior
- Rollback plan for each function
- Monitoring for log volume changes
- Gradual deployment across functions

### Deployment Approach
- Start with least critical functions
- Monitor impact on CloudWatch costs
- Validate monitoring and alerting systems
- Full deployment after validation