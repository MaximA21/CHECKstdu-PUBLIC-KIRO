#!/usr/bin/env python3
"""
Example usage of the centralized logging configuration module.

This demonstrates how Lambda functions should use the logging configuration.
"""

import os
import time
import sys
import os

# Add both src and root directory to path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(root_dir, 'src')
sys.path.insert(0, root_dir)
sys.path.insert(0, src_dir)

from src.infrastructure.logging.logger_factory import LoggerFactory
import logging


def example_lambda_handler(event, context):
    """
    Example Lambda handler showing proper logging usage.
    
    Args:
        event: Lambda event data
        context: Lambda context object
        
    Returns:
        dict: Response data
    """
    # Get configured logger for this function
    logger = get_lambda_logger('example_function')
    
    # Log function start at INFO level
    logger.info("Example Lambda function started")
    
    # Log event details at DEBUG level (won't show in production unless LOG_LEVEL=DEBUG)
    safe_json_log(logger, logging.DEBUG, "Received event", event)
    
    try:
        # Simulate some processing
        start_time = time.time()
        
        # Log processing steps at DEBUG level
        logger.debug("Starting data processing")
        
        # Simulate processing with some business logic
        processed_count = len(event.get('items', []))
        
        # Log business metrics at INFO level
        logger.info(f"Processed {processed_count} items")
        
        # Calculate and log performance metrics
        execution_time = (time.time() - start_time) * 1000
        logger.info(f"Processing completed in {execution_time:.1f}ms")
        
        # Log detailed timing at DEBUG level
        logger.debug(f"Detailed timing - Start: {start_time}, Duration: {execution_time}ms")
        
        # Example of structured logging with context
        log_with_context(
            logger, 
            logging.INFO, 
            "Operation completed successfully",
            {
                "processed_count": processed_count,
                "execution_time_ms": execution_time,
                "function_name": "example_function"
            }
        )
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'Success',
                'processed_count': processed_count,
                'execution_time_ms': execution_time
            }
        }
        
    except Exception as e:
        # Log errors at ERROR level with context
        logger.error(f"Function execution failed: {str(e)}")
        logger.debug(f"Error details", exc_info=True)
        
        return {
            'statusCode': 500,
            'body': {
                'message': 'Internal server error',
                'error': str(e)
            }
        }


def demonstrate_log_levels():
    """Demonstrate different log levels and their usage."""
    print("=== Logging Level Demonstration ===")
    
    # Test with different LOG_LEVEL environment variables
    for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
        print(f"\n--- Testing with LOG_LEVEL={level} ---")
        os.environ['LOG_LEVEL'] = level
        
        # Create fresh logger for each level test
        logger = get_lambda_logger(f'demo_{level.lower()}')
        
        # Test all log levels
        logger.debug("This is a DEBUG message - detailed information")
        logger.info("This is an INFO message - general information")
        logger.warning("This is a WARNING message - something to watch")
        logger.error("This is an ERROR message - something went wrong")
        
        # Clear the logger handlers to avoid conflicts
        logger.handlers.clear()


def demonstrate_structured_logging():
    """Demonstrate structured logging capabilities."""
    print("\n=== Structured Logging Demonstration ===")
    
    # Enable structured logging
    os.environ['STRUCTURED_LOGS'] = 'true'
    os.environ['LOG_LEVEL'] = 'INFO'
    
    logger = get_lambda_logger('structured_demo')
    
    # Regular logging
    logger.info("Regular log message")
    
    # Structured logging with context
    log_with_context(
        logger,
        logging.INFO,
        "User action completed",
        {
            "user_id": "user123",
            "action": "data_processing",
            "duration_ms": 150.5,
            "items_processed": 42
        }
    )
    
    # Safe JSON logging
    sample_data = {
        "request_id": "req-12345",
        "timestamp": "2025-07-19T11:00:00Z",
        "data": {"key": "value", "count": 100}
    }
    safe_json_log(logger, logging.INFO, "Processing request", sample_data)


if __name__ == '__main__':
    # Clean up environment first
    for key in ['LOG_LEVEL', 'STRUCTURED_LOGS']:
        if key in os.environ:
            del os.environ[key]
    
    # Demonstrate basic usage
    print("=== Basic Lambda Handler Example ===")
    sample_event = {
        'items': ['item1', 'item2', 'item3'],
        'source': 'api_gateway'
    }
    
    result = example_lambda_handler(sample_event, None)
    print(f"Handler result: {result}")
    
    # Demonstrate different log levels
    demonstrate_log_levels()
    
    # Demonstrate structured logging
    demonstrate_structured_logging()
    
    print("\n=== Demo Complete ===")