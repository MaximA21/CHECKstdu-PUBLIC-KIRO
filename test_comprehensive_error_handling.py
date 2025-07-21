#!/usr/bin/env python3
"""Comprehensive test for the error handling system."""

import sys
import os
import asyncio
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.shared.exceptions import (
    InvalidAddressException,
    ProviderUnavailableException,
    ExternalServiceException,
    ErrorSeverity,
    ErrorCategory
)
from src.shared.middleware.error_handler import LambdaErrorHandler
from src.shared.monitoring.error_monitor import ErrorMonitor
from src.infrastructure.logging.console_logger import ConsoleLogger


async def test_error_monitoring():
    """Test error monitoring system."""
    print("=== Testing Error Monitoring ===")
    
    logger = ConsoleLogger("test_monitor")
    monitor = ErrorMonitor(logger=logger, time_window_minutes=1)
    
    # Add alert callback
    alerts_received = []
    def alert_callback(alert):
        alerts_received.append(alert)
        print(f"🚨 Alert: {alert.title} - {alert.message}")
    
    monitor.add_alert_callback(alert_callback)
    
    # Record some errors
    errors = [
        InvalidAddressException("Invalid address 1", address="123 Test St"),
        ProviderUnavailableException("Provider down", provider_name="test_provider"),
        ExternalServiceException("Service error", service_name="test_service", status_code=500),
        Exception("Unexpected error")
    ]
    
    for error in errors:
        monitor.record_error(error, {'request_id': f'req_{errors.index(error)}'})
    
    # Get metrics
    metrics = monitor.get_metrics()
    print(f"Total errors: {metrics.total_errors}")
    print(f"Error rate: {metrics.error_rate_per_minute:.2f}/min")
    print(f"Errors by category: {metrics.errors_by_category}")
    print(f"Errors by severity: {metrics.errors_by_severity}")
    
    # Check alerts
    active_alerts = monitor.get_active_alerts()
    print(f"Active alerts: {len(active_alerts)}")
    
    print("✅ Error monitoring test completed\n")


def test_lambda_error_handler():
    """Test Lambda error handler."""
    print("=== Testing Lambda Error Handler ===")
    
    logger = ConsoleLogger("test_handler")
    handler = LambdaErrorHandler(logger=logger)
    
    # Test different error types
    test_cases = [
        InvalidAddressException("Invalid address", address="123 Test St"),
        ProviderUnavailableException("Provider unavailable", provider_name="test_provider"),
        ExternalServiceException("External service error", service_name="test_service", status_code=503),
        Exception("Unexpected system error")
    ]
    
    for error in test_cases:
        context = {
            'request_id': f'req_{test_cases.index(error)}',
            'operation': 'test_operation'
        }
        
        response = handler.handle_error(error, context)
        response_body = json.loads(response['body'])
        
        print(f"Error: {type(error).__name__}")
        print(f"  Status Code: {response['statusCode']}")
        print(f"  Error Code: {response_body.get('error_code', 'N/A')}")
        print(f"  Message: {response_body.get('message', 'N/A')}")
        print()
    
    print("✅ Lambda error handler test completed\n")


def test_error_serialization():
    """Test error serialization to dictionary."""
    print("=== Testing Error Serialization ===")
    
    error = ProviderUnavailableException(
        "Test provider error",
        provider_name="test_provider"
    )
    
    error_dict = error.to_dict()
    
    print("Error dictionary:")
    for key, value in error_dict.items():
        print(f"  {key}: {value}")
    
    # Verify all required fields are present
    required_fields = [
        'error_code', 'message', 'user_message', 'severity', 'category',
        'recoverable', 'timestamp', 'request_id'
    ]
    
    for field in required_fields:
        assert field in error_dict, f"Missing required field: {field}"
    
    print("✅ Error serialization test completed\n")


async def main():
    """Run all tests."""
    print("Starting comprehensive error handling tests...\n")
    
    try:
        await test_error_monitoring()
        test_lambda_error_handler()
        test_error_serialization()
        
        print("🎉 All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())