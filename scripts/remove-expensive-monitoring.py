#!/usr/bin/env python3
"""
Script to remove expensive monitoring features for cost optimization.
This script helps identify and remove costly monitoring resources.
"""

import boto3
import json
import argparse
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExpensiveMonitoringRemover:
    """Remove expensive monitoring features to reduce costs."""
    
    def __init__(self, region: str = 'eu-central-1', dry_run: bool = True):
        self.region = region
        self.dry_run = dry_run
        
        # Initialize AWS clients
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.logs = boto3.client('logs', region_name=region)
        self.kinesis = boto3.client('kinesis', region_name=region)
        self.xray = boto3.client('xray', region_name=region)
        
        logger.info(f"Initialized for region: {region}, dry_run: {dry_run}")
    
    def identify_expensive_resources(self) -> Dict[str, List[Dict]]:
        """Identify expensive monitoring resources."""
        expensive_resources = {
            'kinesis_streams': [],
            'excessive_alarms': [],
            'long_retention_logs': [],
            'xray_traces': [],
            'detailed_monitoring': []
        }
        
        # Find Kinesis streams (expensive)
        try:
            streams = self.kinesis.list_streams()
            for stream_name in streams['StreamNames']:
                stream_details = self.kinesis.describe_stream(StreamName=stream_name)
                expensive_resources['kinesis_streams'].append({
                    'name': stream_name,
                    'status': stream_details['StreamDescription']['StreamStatus'],
                    'shards': len(stream_details['StreamDescription']['Shards']),
                    'estimated_monthly_cost': len(stream_details['StreamDescription']['Shards']) * 28  # ~$28/shard/month
                })
        except Exception as e:
            logger.warning(f"Error listing Kinesis streams: {e}")
        
        # Find excessive CloudWatch alarms
        try:
            paginator = self.cloudwatch.get_paginator('describe_alarms')
            alarm_count = 0
            for page in paginator.paginate():
                alarm_count += len(page['MetricAlarms'])
                for alarm in page['MetricAlarms']:
                    if alarm_count > 10:  # More than 10 alarms might be excessive for student budget
                        expensive_resources['excessive_alarms'].append({
                            'name': alarm['AlarmName'],
                            'state': alarm['StateValue'],
                            'estimated_monthly_cost': 0.10  # $0.10 per alarm per month
                        })
        except Exception as e:
            logger.warning(f"Error listing CloudWatch alarms: {e}")
        
        # Find log groups with long retention
        try:
            paginator = self.logs.get_paginator('describe_log_groups')
            for page in paginator.paginate():
                for log_group in page['logGroups']:
                    retention_days = log_group.get('retentionInDays', 'Never expire')
                    if isinstance(retention_days, int) and retention_days > 14:
                        expensive_resources['long_retention_logs'].append({
                            'name': log_group['logGroupName'],
                            'retention_days': retention_days,
                            'size_bytes': log_group.get('storedBytes', 0),
                            'estimated_monthly_cost': (log_group.get('storedBytes', 0) / 1024**3) * 0.50  # ~$0.50/GB/month
                        })
        except Exception as e:
            logger.warning(f"Error listing log groups: {e}")
        
        # Check X-Ray tracing (can be expensive)
        try:
            traces = self.xray.get_trace_summaries(
                TimeRangeType='TimeRangeByStartTime',
                StartTime=boto3.session.Session().region_name
            )
            if traces.get('TraceSummaries'):
                expensive_resources['xray_traces'].append({
                    'count': len(traces['TraceSummaries']),
                    'estimated_monthly_cost': len(traces['TraceSummaries']) * 0.000005  # $5 per million traces
                })
        except Exception as e:
            logger.warning(f"Error checking X-Ray traces: {e}")
        
        return expensive_resources
    
    def remove_kinesis_streams(self, streams: List[Dict]) -> List[str]:
        """Remove Kinesis streams to save ~$28/month per shard."""
        actions = []
        
        for stream in streams:
            stream_name = stream['name']
            estimated_savings = stream['estimated_monthly_cost']
            
            if self.dry_run:
                actions.append(f"DRY RUN: Would delete Kinesis stream '{stream_name}' (saves ~${estimated_savings}/month)")
            else:
                try:
                    self.kinesis.delete_stream(StreamName=stream_name)
                    actions.append(f"Deleted Kinesis stream '{stream_name}' (saves ~${estimated_savings}/month)")
                    logger.info(f"Deleted Kinesis stream: {stream_name}")
                except Exception as e:
                    actions.append(f"Failed to delete Kinesis stream '{stream_name}': {e}")
                    logger.error(f"Error deleting stream {stream_name}: {e}")
        
        return actions
    
    def reduce_alarm_count(self, alarms: List[Dict], keep_count: int = 10) -> List[str]:
        """Reduce number of CloudWatch alarms to save ~$0.10/alarm/month."""
        actions = []
        
        # Sort alarms by importance (keep critical ones)
        critical_keywords = ['error', 'critical', 'high', 'failure', 'cost']
        
        alarms_to_keep = []
        alarms_to_remove = []
        
        for alarm in alarms:
            alarm_name = alarm['name'].lower()
            if any(keyword in alarm_name for keyword in critical_keywords):
                alarms_to_keep.append(alarm)
            else:
                alarms_to_remove.append(alarm)
        
        # Keep critical alarms + some others up to the limit
        final_keep = alarms_to_keep[:keep_count]
        final_remove = alarms_to_remove + alarms_to_keep[keep_count:]
        
        for alarm in final_remove:
            alarm_name = alarm['name']
            
            if self.dry_run:
                actions.append(f"DRY RUN: Would delete alarm '{alarm_name}' (saves $0.10/month)")
            else:
                try:
                    self.cloudwatch.delete_alarms(AlarmNames=[alarm_name])
                    actions.append(f"Deleted alarm '{alarm_name}' (saves $0.10/month)")
                    logger.info(f"Deleted alarm: {alarm_name}")
                except Exception as e:
                    actions.append(f"Failed to delete alarm '{alarm_name}': {e}")
                    logger.error(f"Error deleting alarm {alarm_name}: {e}")
        
        return actions
    
    def reduce_log_retention(self, log_groups: List[Dict], target_retention: int = 7) -> List[str]:
        """Reduce log retention to save storage costs."""
        actions = []
        
        for log_group in log_groups:
            log_group_name = log_group['name']
            current_retention = log_group['retention_days']
            estimated_savings = log_group['estimated_monthly_cost'] * 0.7  # Estimate 70% savings
            
            if self.dry_run:
                actions.append(
                    f"DRY RUN: Would reduce retention for '{log_group_name}' "
                    f"from {current_retention} to {target_retention} days (saves ~${estimated_savings:.2f}/month)"
                )
            else:
                try:
                    self.logs.put_retention_policy(
                        logGroupName=log_group_name,
                        retentionInDays=target_retention
                    )
                    actions.append(
                        f"Reduced retention for '{log_group_name}' "
                        f"from {current_retention} to {target_retention} days (saves ~${estimated_savings:.2f}/month)"
                    )
                    logger.info(f"Updated retention for log group: {log_group_name}")
                except Exception as e:
                    actions.append(f"Failed to update retention for '{log_group_name}': {e}")
                    logger.error(f"Error updating log group {log_group_name}: {e}")
        
        return actions
    
    def generate_cost_optimization_report(self, expensive_resources: Dict) -> str:
        """Generate a cost optimization report."""
        report = "# Cost Optimization Report\n\n"
        
        total_potential_savings = 0
        
        # Kinesis streams
        if expensive_resources['kinesis_streams']:
            report += "## Kinesis Streams (High Cost)\n"
            kinesis_savings = sum(stream['estimated_monthly_cost'] for stream in expensive_resources['kinesis_streams'])
            total_potential_savings += kinesis_savings
            report += f"- Found {len(expensive_resources['kinesis_streams'])} Kinesis streams\n"
            report += f"- Estimated monthly cost: ${kinesis_savings:.2f}\n"
            report += "- Recommendation: Replace with CloudWatch Logs Insights for log analysis\n\n"
        
        # Excessive alarms
        if expensive_resources['excessive_alarms']:
            report += "## CloudWatch Alarms\n"
            alarm_count = len(expensive_resources['excessive_alarms'])
            alarm_savings = alarm_count * 0.10
            total_potential_savings += alarm_savings
            report += f"- Found {alarm_count} alarms (recommended max: 10 for student budget)\n"
            report += f"- Estimated monthly cost: ${alarm_savings:.2f}\n"
            report += "- Recommendation: Keep only critical alarms (error rates, cost alerts)\n\n"
        
        # Long retention logs
        if expensive_resources['long_retention_logs']:
            report += "## Log Groups with Long Retention\n"
            log_savings = sum(log['estimated_monthly_cost'] for log in expensive_resources['long_retention_logs'])
            total_potential_savings += log_savings * 0.7  # Estimate 70% savings
            report += f"- Found {len(expensive_resources['long_retention_logs'])} log groups with >14 days retention\n"
            report += f"- Estimated monthly cost: ${log_savings:.2f}\n"
            report += "- Recommendation: Reduce retention to 7 days (saves ~70%)\n\n"
        
        report += f"## Total Potential Monthly Savings: ${total_potential_savings:.2f}\n\n"
        
        report += "## Recommended Actions:\n"
        report += "1. Remove Kinesis streams and use CloudWatch Logs Insights\n"
        report += "2. Keep only critical CloudWatch alarms\n"
        report += "3. Reduce log retention to 7 days\n"
        report += "4. Use AWS managed KMS keys instead of custom keys\n"
        report += "5. Disable detailed monitoring where not essential\n"
        
        return report
    
    def optimize_costs(self) -> Dict[str, Any]:
        """Run complete cost optimization."""
        logger.info("Starting cost optimization analysis...")
        
        # Identify expensive resources
        expensive_resources = self.identify_expensive_resources()
        
        # Generate report
        report = self.generate_cost_optimization_report(expensive_resources)
        
        # Perform optimizations
        actions = []
        
        # Remove Kinesis streams
        if expensive_resources['kinesis_streams']:
            actions.extend(self.remove_kinesis_streams(expensive_resources['kinesis_streams']))
        
        # Reduce alarms
        if expensive_resources['excessive_alarms']:
            actions.extend(self.reduce_alarm_count(expensive_resources['excessive_alarms']))
        
        # Reduce log retention
        if expensive_resources['long_retention_logs']:
            actions.extend(self.reduce_log_retention(expensive_resources['long_retention_logs']))
        
        return {
            'expensive_resources': expensive_resources,
            'optimization_report': report,
            'actions_taken': actions,
            'dry_run': self.dry_run
        }


def main():
    parser = argparse.ArgumentParser(description='Remove expensive monitoring features')
    parser.add_argument('--region', default='eu-central-1', help='AWS region')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--execute', action='store_true', help='Actually perform the optimizations')
    parser.add_argument('--output', choices=['json', 'report'], default='report', help='Output format')
    
    args = parser.parse_args()
    
    # Default to dry run unless explicitly told to execute
    dry_run = not args.execute
    
    optimizer = ExpensiveMonitoringRemover(region=args.region, dry_run=dry_run)
    result = optimizer.optimize_costs()
    
    if args.output == 'json':
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result['optimization_report'])
        print("\n" + "="*50)
        print("ACTIONS TAKEN:")
        for action in result['actions_taken']:
            print(f"- {action}")
        
        if dry_run:
            print(f"\n⚠️  This was a DRY RUN. Use --execute to actually perform optimizations.")


if __name__ == '__main__':
    main()