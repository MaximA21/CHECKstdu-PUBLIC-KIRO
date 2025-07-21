"""Example demonstrating comprehensive error handling system."""

import asyncio
import json
from typing import Dict, Any

# Import our error handling components
from src.shared.exceptions import (
    InvalidAddressException,
    ProviderUnavailableException,
    ExternalServiceException,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext
)
from src.shared.middleware.error_integration import (
    ComprehensiveErrorHandler,
    initialize_error_handler
)
from src.shared.monitoring import (
    DatabaseHealthCheck,
    ExternalServiceHealthCheck,
    MemoryHealthCheck
)
from src.infrastructure.logging.console_logger import ConsoleLogger


async def simulate_database_connection():
    """Simulate database connection test."""
    # Simulate occasional failures
    import random
    if random.random() < 0.1:  # 10% failure rate
        raise Exception("Database connection timeout")
    return True


async def simulate_external_service_call():
    """Simulate external service call."""
    import random
    await asyncio.sleep(random.uniform(0.1, 2.0))  # Variable response time
    
    if random.random() < 0.2:  # 20% failure rate
        raise Exception("External service unavailable")
    
    return {"status": "success", "data": "mock_data"}


async def simulate_provider_service(provider_name: str):
    """Simulate provider service call that might fail."""
    import random
    
    # Simulate different types of failures
    failure_type = random.random()
    
    if failure_type < 0.1:  # 10% critical failures
        raise ExternalServiceException(
            f"Critical failure in {provider_name}",
            service_name=provider_name,
            status_code=500,
            severity=ErrorSeverity.CRITICAL
        )
    elif failure_type < 0.3:  # 20% recoverable failures
        raise ProviderUnavailableException(
            f"Provider {provider_name} temporarily unavailable",
            provider_name=provider_name
        )
    elif failure_type < 0.4:  # 10% validation errors
        raise InvalidAddressException(
            "Invalid address format",
            address="123 Invalid St"
        )
    
    # Success case
    return {
        "provider": provider_name,
        "offers": [
            {"speed": "100Mbps", "price": 29.99},
            {"speed": "500Mbps", "price": 49.99}
        ]
    }


async def fallback_provider_service(provider_name: str):
    """Fallback service that returns cached or default data."""
    return {
        "provider": f"{provider_name}_fallback",
        "offers": [
            {"speed": "50Mbps", "price": 19.99, "note": "Fallback offer"}
        ]
    }


async def main():
    """Main example function."""
    print("=== Comprehensive Error Handling Example ===\n")
    
    # Initialize logger
    logger = ConsoleLogger("error_handling_example")
    
    # Initialize comprehensive error handler
    error_handler = initialize_error_handler(
        logger=logger,
        enable_monitoring=True,
        enable_circuit_breakers=True,
        enable_retry=True,
        enable_health_checks=True
    )
    
    # Register health checks
    if error_handler.health_check_registry:
        # Database health check
        db_health_check = DatabaseHealthCheck(
            "database",
            simulate_database_connection,
            timeout_seconds=3.0,
            logger=logger
        )
        error_handler.health_check_registry.register(db_health_check)
        
        # External service health check
        service_health_check = ExternalServiceHealthCheck(
            "external_api",
            simulate_external_service_call,
            degraded_threshold_ms=1000.0,
            timeout_seconds=5.0,
            logger=logger
        )
        error_handler.health_check_registry.register(service_health_check)
        
        # Memory health check
        memory_health_check = MemoryHealthCheck(
            "memory",
            warning_threshold_percent=70.0,
            critical_threshold_percent=90.0,
            logger=logger
        )
        error_handler.health_check_registry.register(memory_health_check)
    
    # Register fallback functions
    error_handler.register_fallback("byteme_provider", fallback_provider_service)
    error_handler.register_fallback("webwunder_provider", fallback_provider_service)
    
    # Add alert callback
    def alert_callback(alert_data: Dict[str, Any]):
        print(f"🚨 ALERT: {alert_data['title']}")
        print(f"   Severity: {alert_data['severity']}")
        print(f"   Message: {alert_data['message']}")
        print(f"   Error Count: {alert_data['error_count']}")
        print()
    
    error_handler.add_alert_callback(alert_callback)
    
    print("1. Performing initial health checks...")
    health_summary = await error_handler.perform_health_checks()
    print(f"Overall Health: {health_summary['overall_status']}")
    print()
    
    print("2. Testing provider services with error handling...")
    providers = ["byteme_provider", "webwunder_provider", "verbyndich_provider"]
    
    for i in range(10):  # Simulate multiple requests
        print(f"\n--- Request {i+1} ---")
        
        for provider in providers:
            try:
                # Execute with comprehensive protection
                result = await error_handler.execute_with_protection(
                    simulate_provider_service,
                    service_name=provider,
                    context={
                        'request_id': f'req_{i+1}_{provider}',
                        'user_id': 'user_123'
                    },
                    enable_retry=True,
                    enable_circuit_breaker=True,
                    enable_fallback=True,
                    fallback_func=fallback_provider_service,
                    provider_name=provider  # argument for the function
                )
                
                print(f"✅ {provider}: {len(result['offers'])} offers")
                
            except Exception as e:
                # Handle any remaining errors
                error_response = error_handler.handle_error(
                    e,
                    context={
                        'request_id': f'req_{i+1}_{provider}',
                        'user_id': 'user_123'
                    },
                    service_name=provider
                )
                
                print(f"❌ {provider}: {json.loads(error_response['body'])['message']}")
        
        # Small delay between requests
        await asyncio.sleep(0.5)
    
    print("\n3. System health summary...")
    system_health = error_handler.get_system_health()
    
    # Print error monitoring summary
    if system_health['error_monitoring']:
        metrics = system_health['error_monitoring']['metrics']
        print(f"Total Errors: {metrics['total_errors']}")
        print(f"Error Rate: {metrics['error_rate_per_minute']:.2f}/min")
        print(f"Active Alerts: {len(system_health['error_monitoring']['active_alerts'])}")
    
    # Print circuit breaker states
    if system_health['circuit_breakers']:
        print("\nCircuit Breaker States:")
        for service, state in system_health['circuit_breakers'].items():
            print(f"  {service}: {state}")
    
    # Print health check results
    if system_health['health_checks']:
        print(f"\nOverall Health: {system_health['health_checks']['overall_status']}")
        for name, component in system_health['health_checks']['components'].items():
            status_emoji = {
                'healthy': '✅',
                'degraded': '⚠️',
                'unhealthy': '❌',
                'unknown': '❓'
            }.get(component['status'], '❓')
            
            print(f"  {status_emoji} {name}: {component['status']} - {component['message']}")
    
    print("\n4. Testing direct error handling...")
    
    # Test different types of errors
    test_errors = [
        InvalidAddressException("Test invalid address", address="123 Test St"),
        ProviderUnavailableException("Test provider unavailable", provider_name="test_provider"),
        ExternalServiceException(
            "Test external service error",
            service_name="test_service",
            status_code=503
        ),
        Exception("Test unexpected error")
    ]
    
    for error in test_errors:
        response = error_handler.handle_error(
            error,
            context={'request_id': 'test_req', 'operation': 'test_operation'}
        )
        
        response_body = json.loads(response['body'])
        print(f"Error: {type(error).__name__}")
        print(f"  Status: {response['statusCode']}")
        print(f"  Message: {response_body['message']}")
        print(f"  Error Code: {response_body['error_code']}")
        print()
    
    print("=== Example completed ===")


if __name__ == "__main__":
    asyncio.run(main())