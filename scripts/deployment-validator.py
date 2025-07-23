#!/usr/bin/env python3
"""
Deployment validation script for WebWunder.
Performs comprehensive validation of deployments including functional tests,
performance checks, and integration validation.
"""

import json
import sys
import time
import requests
import boto3
import websocket
import threading
from typing import Dict, List, Optional, Tuple, Any
import argparse
from datetime import datetime, timedelta
import concurrent.futures
import yaml


class DeploymentValidator:
    """Comprehensive deployment validator for WebWunder application."""
    
    def __init__(self, environment: str, region: str = 'eu-central-1', config_file: str = None):
        self.environment = environment
        self.region = region
        self.session = boto3.Session(region_name=region)
        self.lambda_client = self.session.client('lambda')
        self.apigateway_client = self.session.client('apigateway')
        self.dynamodb_client = self.session.client('dynamodb')
        
        # Load configuration
        self.config = self._load_config(config_file)
        
        # Test results storage
        self.results = {
            'environment': environment,
            'region': region,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'tests': {},
            'overall_status': 'unknown'
        }
    
    def _load_config(self, config_file: str = None) -> Dict:
        """Load deployment configuration."""
        default_config = {
            'timeouts': {'api_test': 30, 'websocket_test': 60, 'load_test': 300},
            'thresholds': {'max_response_time': 5000, 'min_success_rate': 95},
            'test_data': {'search_queries': ['test query', 'sample search']}
        }
        
        if config_file:
            try:
                with open(config_file, 'r') as f:
                    if config_file.endswith('.yml') or config_file.endswith('.yaml'):
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)
                return {**default_config, **config}
            except Exception as e:
                print(f"⚠️ Could not load config file {config_file}: {e}")
        
        return default_config
    
    def validate_api_endpoints(self, base_url: str) -> Dict[str, Any]:
        """Validate REST API endpoints."""
        print("🌐 Validating API endpoints...")
        
        test_results = {
            'status': 'unknown',
            'endpoints': {},
            'response_times': [],
            'errors': []
        }
        
        # Define endpoints to test
        endpoints = [
            {'path': '/health', 'method': 'GET', 'expected_status': 200},
            {'path': '/api/search', 'method': 'POST', 'expected_status': [200, 202], 
             'payload': {'query': 'test search', 'location': 'Berlin'}},
            {'path': '/api/share', 'method': 'POST', 'expected_status': [200, 201],
             'payload': {'results': [], 'metadata': {'test': True}}}
        ]
        
        success_count = 0
        
        for endpoint in endpoints:
            endpoint_name = f"{endpoint['method']} {endpoint['path']}"
            print(f"Testing {endpoint_name}...")
            
            try:
                start_time = time.time()
                
                if endpoint['method'] == 'GET':
                    response = requests.get(
                        f"{base_url}{endpoint['path']}", 
                        timeout=self.config['timeouts']['api_test']
                    )
                elif endpoint['method'] == 'POST':
                    response = requests.post(
                        f"{base_url}{endpoint['path']}", 
                        json=endpoint.get('payload', {}),
                        timeout=self.config['timeouts']['api_test']
                    )
                
                response_time = (time.time() - start_time) * 1000  # milliseconds
                test_results['response_times'].append(response_time)
                
                expected_status = endpoint['expected_status']
                if isinstance(expected_status, list):
                    status_ok = response.status_code in expected_status
                else:
                    status_ok = response.status_code == expected_status
                
                if status_ok and response_time < self.config['thresholds']['max_response_time']:
                    test_results['endpoints'][endpoint_name] = {
                        'status': 'passed',
                        'response_time': response_time,
                        'status_code': response.status_code
                    }
                    success_count += 1
                    print(f"  ✅ {endpoint_name}: {response.status_code} ({response_time:.0f}ms)")
                else:
                    test_results['endpoints'][endpoint_name] = {
                        'status': 'failed',
                        'response_time': response_time,
                        'status_code': response.status_code,
                        'error': f"Status: {response.status_code}, Time: {response_time:.0f}ms"
                    }
                    print(f"  ❌ {endpoint_name}: {response.status_code} ({response_time:.0f}ms)")
                
            except Exception as e:
                test_results['endpoints'][endpoint_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                test_results['errors'].append(f"{endpoint_name}: {str(e)}")
                print(f"  ❌ {endpoint_name}: Error - {str(e)}")
        
        # Calculate overall status
        success_rate = (success_count / len(endpoints)) * 100
        test_results['success_rate'] = success_rate
        test_results['status'] = 'passed' if success_rate >= self.config['thresholds']['min_success_rate'] else 'failed'
        
        if test_results['response_times']:
            test_results['avg_response_time'] = sum(test_results['response_times']) / len(test_results['response_times'])
        
        return test_results
    
    def validate_websocket_connection(self, ws_url: str) -> Dict[str, Any]:
        """Validate WebSocket connectivity and basic functionality."""
        print("🔌 Validating WebSocket connection...")
        
        test_results = {
            'status': 'unknown',
            'connection_test': False,
            'message_test': False,
            'connection_time': 0,
            'errors': []
        }
        
        try:
            # Test WebSocket connection
            start_time = time.time()
            
            def on_message(ws, message):
                print(f"  📨 Received: {message}")
                test_results['message_test'] = True
            
            def on_error(ws, error):
                test_results['errors'].append(str(error))
                print(f"  ❌ WebSocket error: {error}")
            
            def on_open(ws):
                connection_time = (time.time() - start_time) * 1000
                test_results['connection_time'] = connection_time
                test_results['connection_test'] = True
                print(f"  ✅ WebSocket connected ({connection_time:.0f}ms)")
                
                # Send test message
                test_message = json.dumps({
                    'action': 'search',
                    'data': {'query': 'test', 'location': 'Berlin'}
                })
                ws.send(test_message)
                print(f"  📤 Sent test message")
            
            def on_close(ws, close_status_code, close_msg):
                print(f"  🔌 WebSocket closed: {close_status_code}")
            
            # Create WebSocket connection
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # Run WebSocket in a separate thread with timeout
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection and message exchange
            timeout = self.config['timeouts']['websocket_test']
            ws_thread.join(timeout=timeout)
            
            if ws_thread.is_alive():
                ws.close()
                test_results['errors'].append("WebSocket test timed out")
            
            # Determine overall status
            if test_results['connection_test'] and not test_results['errors']:
                test_results['status'] = 'passed'
            else:
                test_results['status'] = 'failed'
                
        except Exception as e:
            test_results['status'] = 'error'
            test_results['errors'].append(str(e))
            print(f"  ❌ WebSocket validation error: {str(e)}")
        
        return test_results
    
    def validate_lambda_functions(self) -> Dict[str, Any]:
        """Validate Lambda function deployments and configurations."""
        print("⚡ Validating Lambda functions...")
        
        functions = [
            'search_handler', 'results_handler', 'connect_handler',
            'disconnect_handler', 'authorizer', 'requestor_handler'
        ]
        
        test_results = {
            'status': 'unknown',
            'functions': {},
            'errors': []
        }
        
        success_count = 0
        
        for func_name in functions:
            full_name = f"webwunder-{self.environment}-{func_name}"
            print(f"  Testing {func_name}...")
            
            try:
                # Get function configuration
                response = self.lambda_client.get_function(FunctionName=full_name)
                config = response['Configuration']
                
                # Check function state
                state = config['State']
                last_update_status = config['LastUpdateStatus']
                runtime = config['Runtime']
                memory = config['MemorySize']
                timeout = config['Timeout']
                
                # Validate function health
                is_healthy = (
                    state == 'Active' and 
                    last_update_status == 'Successful' and
                    runtime.startswith('python3') and
                    memory >= 128 and
                    timeout >= 30
                )
                
                if is_healthy:
                    # Test function invocation (for non-WebSocket functions)
                    if func_name not in ['connect_handler', 'disconnect_handler']:
                        try:
                            test_payload = {'test': True, 'source': 'deployment_validation'}
                            invoke_response = self.lambda_client.invoke(
                                FunctionName=full_name,
                                InvocationType='RequestResponse',
                                Payload=json.dumps(test_payload)
                            )
                            
                            if invoke_response['StatusCode'] == 200:
                                invocation_success = True
                            else:
                                invocation_success = False
                                test_results['errors'].append(f"{func_name} invocation failed")
                        except Exception as e:
                            invocation_success = False
                            test_results['errors'].append(f"{func_name} invocation error: {str(e)}")
                    else:
                        invocation_success = True  # Skip invocation test for WebSocket handlers
                    
                    if invocation_success:
                        test_results['functions'][func_name] = {
                            'status': 'passed',
                            'state': state,
                            'runtime': runtime,
                            'memory': memory,
                            'timeout': timeout
                        }
                        success_count += 1
                        print(f"    ✅ {func_name}: {state} ({runtime}, {memory}MB)")
                    else:
                        test_results['functions'][func_name] = {
                            'status': 'failed',
                            'state': state,
                            'error': 'Invocation failed'
                        }
                        print(f"    ❌ {func_name}: Invocation failed")
                else:
                    test_results['functions'][func_name] = {
                        'status': 'failed',
                        'state': state,
                        'last_update_status': last_update_status,
                        'error': f"Unhealthy state: {state}/{last_update_status}"
                    }
                    print(f"    ❌ {func_name}: {state} ({last_update_status})")
                    
            except Exception as e:
                test_results['functions'][func_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                test_results['errors'].append(f"{func_name}: {str(e)}")
                print(f"    ❌ {func_name}: Error - {str(e)}")
        
        # Calculate overall status
        success_rate = (success_count / len(functions)) * 100
        test_results['success_rate'] = success_rate
        test_results['status'] = 'passed' if success_rate >= self.config['thresholds']['min_success_rate'] else 'failed'
        
        return test_results
    
    def validate_data_persistence(self) -> Dict[str, Any]:
        """Validate DynamoDB tables and data persistence."""
        print("💾 Validating data persistence...")
        
        test_results = {
            'status': 'unknown',
            'tables': {},
            'errors': []
        }
        
        # Expected DynamoDB tables
        expected_tables = [
            f"webwunder-{self.environment}-connections",
            f"webwunder-{self.environment}-search-results",
            f"webwunder-{self.environment}-user-sessions"
        ]
        
        success_count = 0
        
        for table_name in expected_tables:
            print(f"  Testing table {table_name}...")
            
            try:
                # Check table status
                response = self.dynamodb_client.describe_table(TableName=table_name)
                table_status = response['Table']['TableStatus']
                
                if table_status == 'ACTIVE':
                    # Test basic read/write operations
                    test_item = {
                        'id': {'S': f'test-{int(time.time())}'},
                        'test_data': {'S': 'deployment_validation'},
                        'timestamp': {'S': datetime.utcnow().isoformat()}
                    }
                    
                    # Write test item
                    self.dynamodb_client.put_item(
                        TableName=table_name,
                        Item=test_item
                    )
                    
                    # Read test item
                    get_response = self.dynamodb_client.get_item(
                        TableName=table_name,
                        Key={'id': test_item['id']}
                    )
                    
                    if 'Item' in get_response:
                        # Clean up test item
                        self.dynamodb_client.delete_item(
                            TableName=table_name,
                            Key={'id': test_item['id']}
                        )
                        
                        test_results['tables'][table_name] = {
                            'status': 'passed',
                            'table_status': table_status
                        }
                        success_count += 1
                        print(f"    ✅ {table_name}: {table_status}")
                    else:
                        test_results['tables'][table_name] = {
                            'status': 'failed',
                            'error': 'Read operation failed'
                        }
                        print(f"    ❌ {table_name}: Read operation failed")
                else:
                    test_results['tables'][table_name] = {
                        'status': 'failed',
                        'table_status': table_status,
                        'error': f'Table not active: {table_status}'
                    }
                    print(f"    ❌ {table_name}: {table_status}")
                    
            except Exception as e:
                test_results['tables'][table_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                test_results['errors'].append(f"{table_name}: {str(e)}")
                print(f"    ❌ {table_name}: Error - {str(e)}")
        
        # Calculate overall status
        success_rate = (success_count / len(expected_tables)) * 100
        test_results['success_rate'] = success_rate
        test_results['status'] = 'passed' if success_rate >= self.config['thresholds']['min_success_rate'] else 'failed'
        
        return test_results
    
    def run_load_test(self, api_url: str, duration: int = 60) -> Dict[str, Any]:
        """Run basic load test against the API."""
        print(f"🚀 Running load test for {duration} seconds...")
        
        test_results = {
            'status': 'unknown',
            'duration': duration,
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0,
            'max_response_time': 0,
            'min_response_time': float('inf'),
            'errors': []
        }
        
        def make_request():
            """Make a single API request."""
            try:
                start_time = time.time()
                response = requests.post(
                    f"{api_url}/api/search",
                    json={'query': 'load test', 'location': 'Berlin'},
                    timeout=10
                )
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'success': response.status_code in [200, 202],
                    'response_time': response_time,
                    'status_code': response.status_code
                }
            except Exception as e:
                return {
                    'success': False,
                    'response_time': 0,
                    'error': str(e)
                }
        
        # Run load test with concurrent requests
        start_time = time.time()
        response_times = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            while time.time() - start_time < duration:
                future = executor.submit(make_request)
                futures.append(future)
                time.sleep(0.1)  # 10 requests per second
            
            # Collect results
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                test_results['total_requests'] += 1
                
                if result['success']:
                    test_results['successful_requests'] += 1
                    response_times.append(result['response_time'])
                else:
                    test_results['failed_requests'] += 1
                    if 'error' in result:
                        test_results['errors'].append(result['error'])
        
        # Calculate statistics
        if response_times:
            test_results['avg_response_time'] = sum(response_times) / len(response_times)
            test_results['max_response_time'] = max(response_times)
            test_results['min_response_time'] = min(response_times)
        
        success_rate = (test_results['successful_requests'] / test_results['total_requests']) * 100 if test_results['total_requests'] > 0 else 0
        test_results['success_rate'] = success_rate
        
        # Determine status
        if success_rate >= self.config['thresholds']['min_success_rate'] and test_results['avg_response_time'] < self.config['thresholds']['max_response_time']:
            test_results['status'] = 'passed'
        else:
            test_results['status'] = 'failed'
        
        print(f"  📊 Load test results:")
        print(f"    Total requests: {test_results['total_requests']}")
        print(f"    Success rate: {success_rate:.1f}%")
        print(f"    Avg response time: {test_results['avg_response_time']:.0f}ms")
        
        return test_results
    
    def run_comprehensive_validation(self, api_url: str = None, ws_url: str = None, 
                                   include_load_test: bool = False) -> Tuple[bool, Dict]:
        """Run comprehensive deployment validation."""
        print(f"🔍 Running comprehensive deployment validation for {self.environment}...")
        print(f"Region: {self.region}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print("-" * 60)
        
        # Run all validation tests
        if api_url:
            print("\n1. API Endpoint Validation")
            self.results['tests']['api_endpoints'] = self.validate_api_endpoints(api_url)
        
        if ws_url:
            print("\n2. WebSocket Validation")
            self.results['tests']['websocket'] = self.validate_websocket_connection(ws_url)
        
        print("\n3. Lambda Function Validation")
        self.results['tests']['lambda_functions'] = self.validate_lambda_functions()
        
        print("\n4. Data Persistence Validation")
        self.results['tests']['data_persistence'] = self.validate_data_persistence()
        
        if include_load_test and api_url:
            print("\n5. Load Test")
            self.results['tests']['load_test'] = self.run_load_test(api_url)
        
        # Calculate overall status
        print("\n" + "=" * 60)
        print("📋 DEPLOYMENT VALIDATION SUMMARY")
        print("=" * 60)
        
        all_passed = True
        for test_name, test_result in self.results['tests'].items():
            status = test_result.get('status', 'unknown')
            if status == 'passed':
                print(f"{test_name}: ✅ PASSED")
            elif status == 'failed':
                print(f"{test_name}: ❌ FAILED")
                all_passed = False
            else:
                print(f"{test_name}: ⚠️ {status.upper()}")
                all_passed = False
        
        self.results['overall_status'] = 'passed' if all_passed else 'failed'
        self.results['validation_complete'] = True
        
        print(f"\n🎯 OVERALL VALIDATION: {'✅ PASSED' if all_passed else '❌ FAILED'}")
        print("=" * 60)
        
        return all_passed, self.results


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Comprehensive deployment validation')
    parser.add_argument('environment', choices=['staging', 'production'], 
                       help='Environment to validate')
    parser.add_argument('--region', default='eu-central-1',
                       help='AWS region (default: eu-central-1)')
    parser.add_argument('--api-url', 
                       help='API Gateway base URL')
    parser.add_argument('--ws-url',
                       help='WebSocket Gateway URL')
    parser.add_argument('--config', 
                       help='Configuration file path')
    parser.add_argument('--include-load-test', action='store_true',
                       help='Include load testing')
    parser.add_argument('--output', 
                       help='Output file for JSON results')
    parser.add_argument('--timeout', type=int, default=600,
                       help='Overall timeout in seconds (default: 600)')
    
    args = parser.parse_args()
    
    # Create validator
    validator = DeploymentValidator(args.environment, args.region, args.config)
    
    try:
        # Run validation
        is_valid, results = validator.run_comprehensive_validation(
            api_url=args.api_url,
            ws_url=args.ws_url,
            include_load_test=args.include_load_test
        )
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n📄 Results saved to: {args.output}")
        
        # Exit with appropriate code
        if is_valid:
            print("\n✅ Deployment validation PASSED")
            sys.exit(0)
        else:
            print("\n❌ Deployment validation FAILED")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Validation interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n💥 Validation failed with error: {str(e)}")
        sys.exit(3)


if __name__ == '__main__':
    main()