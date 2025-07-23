#!/usr/bin/env python3
"""
Script to manage REST API Gateway canary deployments and traffic shifting.
This script allows gradual traffic shifting between old and new implementations.
"""

import argparse
import boto3
import json
import time
import sys
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError, BotoCoreError


class CanaryDeploymentManager:
    """Manages API Gateway canary deployments for gradual traffic shifting."""
    
    def __init__(self, region: str = 'eu-central-1'):
        """Initialize the canary deployment manager."""
        self.region = region
        self.apigateway = boto3.client('apigateway', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        
    def get_api_info(self, api_name: str) -> Optional[Dict[str, Any]]:
        """Get API Gateway information by name."""
        try:
            response = self.apigateway.get_rest_apis()
            for api in response['items']:
                if api['name'] == api_name:
                    return api
            return None
        except (ClientError, BotoCoreError) as e:
            print(f"Error getting API info: {e}")
            return None
    
    def get_stage_info(self, api_id: str, stage_name: str) -> Optional[Dict[str, Any]]:
        """Get stage information including canary settings."""
        try:
            response = self.apigateway.get_stage(
                restApiId=api_id,
                stageName=stage_name
            )
            return response
        except (ClientError, BotoCoreError) as e:
            print(f"Error getting stage info: {e}")
            return None
    
    def update_canary_traffic(self, api_id: str, stage_name: str, percent_traffic: int) -> bool:
        """Update canary traffic percentage by updating stage variables."""
        try:
            # Update stage variables for traffic split tracking
            self.apigateway.update_stage(
                restApiId=api_id,
                stageName=stage_name,
                patchOps=[
                    {
                        'op': 'replace',
                        'path': '/variables/traffic_split',
                        'value': str(percent_traffic)
                    }
                ]
            )
            
            # Also update canary stage if it exists
            try:
                self.apigateway.update_stage(
                    restApiId=api_id,
                    stageName='canary',
                    patchOps=[
                        {
                            'op': 'replace',
                            'path': '/variables/traffic_split',
                            'value': str(percent_traffic)
                        }
                    ]
                )
            except (ClientError, BotoCoreError):
                # Canary stage might not exist, which is fine
                pass
                
            print(f"Successfully updated canary traffic to {percent_traffic}%")
            print("Note: This implementation uses separate stages for canary deployment.")
            print("Traffic distribution should be managed at the load balancer or application level.")
            return True
        except (ClientError, BotoCoreError) as e:
            print(f"Error updating canary traffic: {e}")
            return False
    
    def get_metrics(self, api_name: str, stage_name: str, minutes: int = 10) -> Dict[str, float]:
        """Get CloudWatch metrics for the API."""
        end_time = time.time()
        start_time = end_time - (minutes * 60)
        
        metrics = {}
        
        try:
            # Get error rate
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='4XXError',
                Dimensions=[
                    {'Name': 'ApiName', 'Value': api_name},
                    {'Name': 'Stage', 'Value': stage_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum']
            )
            
            error_sum = sum(point['Sum'] for point in response['Datapoints'])
            
            # Get total requests
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='Count',
                Dimensions=[
                    {'Name': 'ApiName', 'Value': api_name},
                    {'Name': 'Stage', 'Value': stage_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum']
            )
            
            request_sum = sum(point['Sum'] for point in response['Datapoints'])
            
            # Calculate error rate
            error_rate = (error_sum / request_sum * 100) if request_sum > 0 else 0
            metrics['error_rate'] = error_rate
            metrics['total_requests'] = request_sum
            metrics['total_errors'] = error_sum
            
            # Get average latency
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='Latency',
                Dimensions=[
                    {'Name': 'ApiName', 'Value': api_name},
                    {'Name': 'Stage', 'Value': stage_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )
            
            if response['Datapoints']:
                avg_latency = sum(point['Average'] for point in response['Datapoints']) / len(response['Datapoints'])
                metrics['avg_latency'] = avg_latency
            else:
                metrics['avg_latency'] = 0
                
        except (ClientError, BotoCoreError) as e:
            print(f"Error getting metrics: {e}")
            
        return metrics
    
    def check_health(self, api_name: str, stage_name: str) -> bool:
        """Check if the API is healthy based on metrics."""
        metrics = self.get_metrics(api_name, stage_name)
        
        # Health criteria
        max_error_rate = 5.0  # 5%
        max_latency = 5000    # 5 seconds
        
        if metrics.get('error_rate', 0) > max_error_rate:
            print(f"❌ High error rate: {metrics['error_rate']:.2f}% (threshold: {max_error_rate}%)")
            return False
            
        if metrics.get('avg_latency', 0) > max_latency:
            print(f"❌ High latency: {metrics['avg_latency']:.2f}ms (threshold: {max_latency}ms)")
            return False
            
        print(f"✅ Health check passed - Error rate: {metrics.get('error_rate', 0):.2f}%, Latency: {metrics.get('avg_latency', 0):.2f}ms")
        return True
    
    def gradual_traffic_shift(self, api_name: str, stage_name: str, target_percent: int, step_size: int = 10, wait_minutes: int = 5) -> bool:
        """Gradually shift traffic to canary deployment."""
        api_info = self.get_api_info(api_name)
        if not api_info:
            print(f"API '{api_name}' not found")
            return False
            
        api_id = api_info['id']
        stage_info = self.get_stage_info(api_id, stage_name)
        
        if not stage_info:
            print(f"Stage '{stage_name}' not found")
            return False
            
        current_percent = 0
        if 'canarySettings' in stage_info:
            current_percent = int(stage_info['canarySettings'].get('percentTraffic', 0))
            
        print(f"Current canary traffic: {current_percent}%")
        print(f"Target canary traffic: {target_percent}%")
        
        # Gradually increase traffic
        while current_percent < target_percent:
            next_percent = min(current_percent + step_size, target_percent)
            
            print(f"\n🔄 Shifting traffic to {next_percent}%...")
            if not self.update_canary_traffic(api_id, stage_name, next_percent):
                return False
                
            # Wait for metrics to stabilize
            print(f"⏳ Waiting {wait_minutes} minutes for metrics to stabilize...")
            time.sleep(wait_minutes * 60)
            
            # Check health
            if not self.check_health(api_name, stage_name):
                print("❌ Health check failed, rolling back...")
                self.update_canary_traffic(api_id, stage_name, current_percent)
                return False
                
            current_percent = next_percent
            
        print(f"✅ Successfully shifted traffic to {target_percent}%")
        return True
    
    def rollback_canary(self, api_name: str, stage_name: str) -> bool:
        """Rollback canary deployment to 0% traffic."""
        print("🔄 Rolling back canary deployment...")
        api_info = self.get_api_info(api_name)
        if not api_info:
            print(f"API '{api_name}' not found")
            return False
            
        return self.update_canary_traffic(api_info['id'], stage_name, 0)
    
    def promote_canary(self, api_name: str, stage_name: str) -> bool:
        """Promote canary to 100% traffic (full deployment)."""
        print("🚀 Promoting canary to full deployment...")
        api_info = self.get_api_info(api_name)
        if not api_info:
            print(f"API '{api_name}' not found")
            return False
            
        return self.update_canary_traffic(api_info['id'], stage_name, 100)
    
    def status(self, api_name: str, stage_name: str) -> None:
        """Show current canary deployment status."""
        api_info = self.get_api_info(api_name)
        if not api_info:
            print(f"API '{api_name}' not found")
            return
            
        stage_info = self.get_stage_info(api_info['id'], stage_name)
        if not stage_info:
            print(f"Stage '{stage_name}' not found")
            return
            
        print(f"\n📊 Canary Deployment Status for {api_name}/{stage_name}")
        print("=" * 60)
        
        # Check stage variables for canary configuration
        stage_variables = stage_info.get('variables', {})
        traffic_split = stage_variables.get('traffic_split', '0')
        implementation = stage_variables.get('implementation', 'unknown')
        
        print(f"Implementation: {implementation}")
        print(f"Traffic Split: {traffic_split}%")
        print(f"Deployment ID: {stage_info.get('deploymentId', 'N/A')}")
        
        if stage_variables:
            print("Stage Variables:")
            for key, value in stage_variables.items():
                print(f"  {key}: {value}")
        
        # Check if canary stage exists
        try:
            canary_stage_info = self.get_stage_info(api_info['id'], 'canary')
            if canary_stage_info:
                print(f"\nCanary Stage Found:")
                canary_variables = canary_stage_info.get('variables', {})
                print(f"  Canary Traffic Split: {canary_variables.get('traffic_split', '0')}%")
                print(f"  Canary Implementation: {canary_variables.get('implementation', 'unknown')}")
        except:
            print("\nNo separate canary stage found")
            
        # Show recent metrics
        metrics = self.get_metrics(api_name, stage_name)
        if metrics:
            print(f"\n📈 Recent Metrics (last 10 minutes):")
            print(f"Total Requests: {metrics.get('total_requests', 0)}")
            print(f"Total Errors: {metrics.get('total_errors', 0)}")
            print(f"Error Rate: {metrics.get('error_rate', 0):.2f}%")
            print(f"Average Latency: {metrics.get('avg_latency', 0):.2f}ms")


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description='Manage REST API Gateway canary deployments')
    parser.add_argument('--api-name', required=True, help='API Gateway name')
    parser.add_argument('--stage', default='prod', help='Stage name (default: prod)')
    parser.add_argument('--region', default='eu-central-1', help='AWS region (default: eu-central-1)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    subparsers.add_parser('status', help='Show current canary deployment status')
    
    # Shift command
    shift_parser = subparsers.add_parser('shift', help='Gradually shift traffic to canary')
    shift_parser.add_argument('--target', type=int, required=True, help='Target traffic percentage (0-100)')
    shift_parser.add_argument('--step', type=int, default=10, help='Step size for gradual shift (default: 10)')
    shift_parser.add_argument('--wait', type=int, default=5, help='Wait time between steps in minutes (default: 5)')
    
    # Rollback command
    subparsers.add_parser('rollback', help='Rollback canary deployment to 0%')
    
    # Promote command
    subparsers.add_parser('promote', help='Promote canary to 100% traffic')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
        
    manager = CanaryDeploymentManager(args.region)
    
    if args.command == 'status':
        manager.status(args.api_name, args.stage)
    elif args.command == 'shift':
        success = manager.gradual_traffic_shift(args.api_name, args.stage, args.target, args.step, args.wait)
        sys.exit(0 if success else 1)
    elif args.command == 'rollback':
        success = manager.rollback_canary(args.api_name, args.stage)
        sys.exit(0 if success else 1)
    elif args.command == 'promote':
        success = manager.promote_canary(args.api_name, args.stage)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()