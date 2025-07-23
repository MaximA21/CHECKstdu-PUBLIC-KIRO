#!/usr/bin/env python3
"""
Health check script for deployment validation.
Used by the deployment pipeline to verify system health after deployments.
"""

import json
import sys
import time
import requests
import boto3
from typing import Dict, List, Optional, Tuple
import argparse
from datetime import datetime, timedelta


class HealthChecker:
    """Comprehensive health checker for the WebWunder application."""
    
    def __init__(self, environment: str, region: str = 'eu-central-1'):
        self.environment = environment
        self.region = region
        self.session = boto3.Session(region_name=region)
        self.lambda_client = self.session.client('lambda')
        self.logs_client = self.session.client('logs')
        self.apigateway_client = self.session.client('apigateway')
        self.cloudwatch_client = self.session.client('cloudwatch')
        
    def check_lambda_functions(self) -> Dict[str, bool]:
        """Check health of all Lambda functions."""
        functions = [
            'search_handler',
            'results_handler', 
            'connect_handler',
            'disconnect_handler',
            'authorizer',
            'requestor_handler',
            'address_normalizer',
            'share_api'
        ]
        
        results = {}
        
        for func_name in functions:
            full_name = f"webwunder-{self.environment}-{func_name}"
            try:
                response = self.lambda_client.get_function(FunctionName=full_name)
                state = response['Configuration']['State']
                last_update_status = response['Configuration']['LastUpdateStatus']
                
                is_healthy = (state == 'Active' and last_update_status == 'Successful')
                results[func_name] = is_healthy
                
                if is_healthy:
                    print(f"✅ Lambda {func_name}: {state}")
                else:
                    print(f"❌ Lambda {func_name}: {state} (Update: {last_update_status})")
                    
            except Exception as e:
                print(f"❌ Lambda {func_name}: Error - {str(e)}")
                results[func_name] = False
                
        return results
    
    def check_api_gateway(self, api_endpoint: Optional[str] = None) -> bool:
        """Check API Gateway health."""
        if not api_endpoint:
            # Try to discover API Gateway endpoint
            try:
                apis = self.apigateway_client.get_rest_apis()
                for api in apis['items']:
                    if f"webwunder-{self.environment}" in api['name']:
                        api_endpoint = f"https://{api['id']}.execute-api.{self.region}.amazonaws.com/{self.environment}"
                        break
            except Exception as e:
                print(f"❌ Could not discover API Gateway endpoint: {e}")
                return False
        
        if not api_endpoint:
            print("❌ API Gateway endpoint not provided or discovered")
            return False
            
        try:
            # Check health endpoint
            health_url = f"{api_endpoint}/health"
            response = requests.get(health_url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ API Gateway health check passed: {health_url}")
                return True
            else:
                print(f"❌ API Gateway health check failed: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ API Gateway health check error: {str(e)}")
            return False
    
    def check_websocket_gateway(self, ws_endpoint: Optional[str] = None) -> bool:
        """Check WebSocket API Gateway health."""
        # WebSocket health is harder to check directly, so we check the Lambda functions
        # that handle WebSocket connections
        ws_functions = ['connect_handler', 'disconnect_handler']
        
        all_healthy = True
        for func_name in ws_functions:
            full_name = f"webwunder-{self.environment}-{func_name}"
            try:
                response = self.lambda_client.get_function(FunctionName=full_name)
                state = response['Configuration']['State']
                
                if state == 'Active':
                    print(f"✅ WebSocket {func_name}: {state}")
                else:
                    print(f"❌ WebSocket {func_name}: {state}")
                    all_healthy = False
                    
            except Exception as e:
                print(f"❌ WebSocket {func_name}: Error - {str(e)}")
                all_healthy = False
        
        return all_healthy
    
    def check_error_rates(self, minutes: int = 10) -> Dict[str, int]:
        """Check error rates in CloudWatch logs."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)
        
        functions = ['search_handler', 'results_handler', 'connect_handler']
        error_counts = {}
        
        for func_name in functions:
            log_group = f"/aws/lambda/webwunder-{self.environment}-{func_name}"
            
            try:
                response = self.logs_client.filter_log_events(
                    logGroupName=log_group,
                    startTime=int(start_time.timestamp() * 1000),
                    endTime=int(end_time.timestamp() * 1000),
                    filterPattern='ERROR'
                )
                
                error_count = len(response['events'])
                error_counts[func_name] = error_count
                
                if error_count == 0:
                    print(f"✅ {func_name}: No errors in last {minutes} minutes")
                elif error_count <= 5:
                    print(f"⚠️ {func_name}: {error_count} errors in last {minutes} minutes (acceptable)")
                else:
                    print(f"❌ {func_name}: {error_count} errors in last {minutes} minutes (high)")
                    
            except Exception as e:
                print(f"❌ Could not check error rate for {func_name}: {str(e)}")
                error_counts[func_name] = -1  # Indicate check failed
                
        return error_counts
    
    def check_cloudwatch_metrics(self) -> Dict[str, bool]:
        """Check CloudWatch metrics for system health."""
        metrics_healthy = {}
        
        # Check Lambda invocation metrics
        functions = ['search_handler', 'results_handler', 'connect_handler']
        
        for func_name in functions:
            full_name = f"webwunder-{self.environment}-{func_name}"
            
            try:
                # Check invocation count (should be > 0 for active system)
                response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Invocations',
                    Dimensions=[
                        {
                            'Name': 'FunctionName',
                            'Value': full_name
                        }
                    ],
                    StartTime=datetime.utcnow() - timedelta(minutes=15),
                    EndTime=datetime.utcnow(),
                    Period=300,
                    Statistics=['Sum']
                )
                
                total_invocations = sum(point['Sum'] for point in response['Datapoints'])
                
                # Check error rate
                error_response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Errors',
                    Dimensions=[
                        {
                            'Name': 'FunctionName',
                            'Value': full_name
                        }
                    ],
                    StartTime=datetime.utcnow() - timedelta(minutes=15),
                    EndTime=datetime.utcnow(),
                    Period=300,
                    Statistics=['Sum']
                )
                
                total_errors = sum(point['Sum'] for point in error_response['Datapoints'])
                error_rate = (total_errors / total_invocations * 100) if total_invocations > 0 else 0
                
                is_healthy = error_rate < 5.0  # Less than 5% error rate
                metrics_healthy[func_name] = is_healthy
                
                if is_healthy:
                    print(f"✅ {func_name} metrics: {total_invocations} invocations, {error_rate:.1f}% error rate")
                else:
                    print(f"❌ {func_name} metrics: {total_invocations} invocations, {error_rate:.1f}% error rate")
                    
            except Exception as e:
                print(f"❌ Could not check metrics for {func_name}: {str(e)}")
                metrics_healthy[func_name] = False
                
        return metrics_healthy
    
    def run_comprehensive_health_check(self, 
                                     api_endpoint: Optional[str] = None,
                                     ws_endpoint: Optional[str] = None,
                                     check_metrics: bool = True) -> Tuple[bool, Dict]:
        """Run comprehensive health check and return overall status."""
        print(f"🏥 Running comprehensive health check for {self.environment} environment...")
        print(f"Region: {self.region}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print("-" * 60)
        
        results = {
            'environment': self.environment,
            'region': self.region,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'checks': {}
        }
        
        # Check Lambda functions
        print("\n📋 Checking Lambda functions...")
        lambda_results = self.check_lambda_functions()
        results['checks']['lambda_functions'] = lambda_results
        
        # Check API Gateway
        print("\n🌐 Checking API Gateway...")
        api_healthy = self.check_api_gateway(api_endpoint)
        results['checks']['api_gateway'] = api_healthy
        
        # Check WebSocket Gateway
        print("\n🔌 Checking WebSocket Gateway...")
        ws_healthy = self.check_websocket_gateway(ws_endpoint)
        results['checks']['websocket_gateway'] = ws_healthy
        
        # Check error rates
        print("\n📊 Checking error rates...")
        error_rates = self.check_error_rates()
        results['checks']['error_rates'] = error_rates
        
        # Check CloudWatch metrics (optional, can be slow)
        if check_metrics:
            print("\n📈 Checking CloudWatch metrics...")
            metrics_results = self.check_cloudwatch_metrics()
            results['checks']['cloudwatch_metrics'] = metrics_results
        
        # Calculate overall health
        print("\n" + "=" * 60)
        print("📋 HEALTH CHECK SUMMARY")
        print("=" * 60)
        
        # Lambda functions health
        lambda_healthy = all(lambda_results.values())
        print(f"Lambda Functions: {'✅ HEALTHY' if lambda_healthy else '❌ UNHEALTHY'}")
        
        # API health
        print(f"API Gateway: {'✅ HEALTHY' if api_healthy else '❌ UNHEALTHY'}")
        print(f"WebSocket Gateway: {'✅ HEALTHY' if ws_healthy else '❌ UNHEALTHY'}")
        
        # Error rates health
        error_rates_healthy = all(count <= 10 for count in error_rates.values() if count >= 0)
        print(f"Error Rates: {'✅ HEALTHY' if error_rates_healthy else '❌ UNHEALTHY'}")
        
        # Metrics health
        if check_metrics:
            metrics_healthy_overall = all(metrics_results.values())
            print(f"CloudWatch Metrics: {'✅ HEALTHY' if metrics_healthy_overall else '❌ UNHEALTHY'}")
        else:
            metrics_healthy_overall = True
        
        # Overall health
        overall_healthy = (
            lambda_healthy and 
            api_healthy and 
            ws_healthy and 
            error_rates_healthy and 
            metrics_healthy_overall
        )
        
        results['overall_healthy'] = overall_healthy
        results['summary'] = {
            'lambda_functions': lambda_healthy,
            'api_gateway': api_healthy,
            'websocket_gateway': ws_healthy,
            'error_rates': error_rates_healthy,
            'cloudwatch_metrics': metrics_healthy_overall if check_metrics else None
        }
        
        print(f"\n🏥 OVERALL HEALTH: {'✅ HEALTHY' if overall_healthy else '❌ UNHEALTHY'}")
        print("=" * 60)
        
        return overall_healthy, results


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Health check for WebWunder deployment')
    parser.add_argument('environment', choices=['staging', 'production'], 
                       help='Environment to check')
    parser.add_argument('--region', default='eu-central-1',
                       help='AWS region (default: eu-central-1)')
    parser.add_argument('--api-endpoint', 
                       help='API Gateway endpoint URL')
    parser.add_argument('--ws-endpoint',
                       help='WebSocket Gateway endpoint URL')
    parser.add_argument('--no-metrics', action='store_true',
                       help='Skip CloudWatch metrics check (faster)')
    parser.add_argument('--output', 
                       help='Output file for JSON results')
    parser.add_argument('--timeout', type=int, default=300,
                       help='Timeout in seconds (default: 300)')
    
    args = parser.parse_args()
    
    # Create health checker
    checker = HealthChecker(args.environment, args.region)
    
    try:
        # Run health check
        is_healthy, results = checker.run_comprehensive_health_check(
            api_endpoint=args.api_endpoint,
            ws_endpoint=args.ws_endpoint,
            check_metrics=not args.no_metrics
        )
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n📄 Results saved to: {args.output}")
        
        # Exit with appropriate code
        if is_healthy:
            print("\n✅ Health check PASSED")
            sys.exit(0)
        else:
            print("\n❌ Health check FAILED")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Health check interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n💥 Health check failed with error: {str(e)}")
        sys.exit(3)


if __name__ == '__main__':
    main()