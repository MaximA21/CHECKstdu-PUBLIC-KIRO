#!/usr/bin/env python3
"""Configuration validation and testing utility."""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.loader import ConfigLoader, ConfigurationError, ConfigurationValidationError
from src.infrastructure.config.validator import ConfigValidator
from src.infrastructure.config.service_selector import ServiceSelector


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Configuration validation and testing utility")
    parser.add_argument("--environment", "-e", help="Environment to test (development, testing, staging, production)")
    parser.add_argument("--validate", "-v", action="store_true", help="Run validation checks")
    parser.add_argument("--summary", "-s", action="store_true", help="Show environment summary")
    parser.add_argument("--test-services", "-t", action="store_true", help="Test service creation")
    
    args = parser.parse_args()
    
    # Set environment if provided
    if args.environment:
        os.environ['APP_ENVIRONMENT'] = args.environment
    
    try:
        # Load configuration
        loader = ConfigLoader()
        config = loader.load_config()
        
        print(f"✅ Configuration loaded successfully")
        print(f"Environment: {config.environment.value}")
        print(f"Database: {config.database.provider.value}")
        print(f"Messaging: {config.messaging.provider.value}")
        print(f"Logging: {config.logging.provider.value}")
        print(f"Debug: {config.debug}")
        print()
        
        # Run validation if requested
        if args.validate:
            print("🔍 Running validation checks...")
            results = ConfigValidator.get_all_validation_results(config)
            
            total_issues = 0
            for category, issues in results.items():
                if issues:
                    print(f"\n{category.replace('_', ' ').title()}:")
                    for issue in issues:
                        print(f"  ⚠️  {issue}")
                    total_issues += len(issues)
            
            if total_issues == 0:
                print("✅ No validation issues found")
            else:
                print(f"\n⚠️  Found {total_issues} validation issues")
            print()
        
        # Show environment summary if requested
        if args.summary:
            print("📊 Environment Summary:")
            selector = ServiceSelector(config)
            summary = selector.get_environment_summary()
            
            for key, value in summary.items():
                print(f"  {key}: {value}")
            
            print(f"  Mock Environment: {selector.is_mock_environment()}")
            print(f"  AWS Environment: {selector.is_aws_environment()}")
            print()
        
        # Test service creation if requested
        if args.test_services:
            print("🧪 Testing service creation...")
            selector = ServiceSelector(config)
            
            try:
                repo = selector.get_search_result_repository()
                print("  ✅ Search result repository created")
                
                queue = selector.get_message_queue()
                print("  ✅ Message queue created")
                
                logger_factory = selector.get_logger_factory()
                print("  ✅ Logger factory created")
                
                connection_manager = selector.get_connection_manager()
                print("  ✅ Connection manager created")
                
                print("✅ All services created successfully")
                
            except Exception as e:
                print(f"  ❌ Service creation failed: {e}")
                return 1
        
        return 0
        
    except ConfigurationValidationError as e:
        print(f"❌ Configuration validation failed: {e}")
        print("\nValidation errors:")
        for error in e.errors:
            print(f"  - {error}")
        return 1
        
    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
        return 1
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())