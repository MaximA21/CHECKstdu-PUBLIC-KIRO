#!/usr/bin/env python3
"""
Deployment monitoring script for WebWunder.
Monitors deployment health and performance metrics after deployment.
"""

import json
import sys
import time
import boto3
from typing import Dict, List, Optional, Tuple, Any
import argparse
from datetime import datetime, timedelta
import threading
import signal


class DeploymentMonitor:
    """Real-time deployment monitoring for WebWunder application."""

    def __init__(self, environment: str, region: str = "eu-central-1"):
        self.environment = environment
        self.region = region
        self.session = boto3.Session(region_name=region)
        self.cloudwatch = self.session.client("cloudwatch")
        self.logs = self.session.client("logs")
        self.lambda_client = self.session.client("lambda")

        # Monitoring state
        self.monitoring = False
        self.metrics_history = []
        self.alerts = []

        # Thresholds
        self.thresholds = {
            "error_rate": 5.0,  # percentage
            "response_time": 5000,  # milliseconds
            "invocation_rate": 1000,  # per minute
            "memory_utilization": 80,  # percentage
        }

    def get_lambda_metrics(self, minutes: int = 5) -> Dict[str, Any]:
        """Get Lambda function metrics from CloudWatch."""
        functions = [
            "search_handler",
            "results_handler",
            "connect_handler",
            "disconnect_handler",
            "authorizer",
            "requestor_handler",
        ]

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)

        metrics = {
            "timestamp": end_time.isoformat() + "Z",
            "functions": {},
            "summary": {"total_invocations": 0, "total_errors": 0, "avg_duration": 0, "error_rate": 0},
        }

        total_invocations = 0
        total_errors = 0
        total_duration = 0
        duration_count = 0

        for func_name in functions:
            full_name = f"webwunder-{self.environment}-{func_name}"
            func_metrics = {"name": func_name}

            try:
                # Get invocation count
                invocations_response = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Invocations",
                    Dimensions=[{"Name": "FunctionName", "Value": full_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=["Sum"],
                )

                invocations = sum(point["Sum"] for point in invocations_response["Datapoints"])
                func_metrics["invocations"] = invocations
                total_invocations += invocations

                # Get error count
                errors_response = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Errors",
                    Dimensions=[{"Name": "FunctionName", "Value": full_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=["Sum"],
                )

                errors = sum(point["Sum"] for point in errors_response["Datapoints"])
                func_metrics["errors"] = errors
                total_errors += errors

                # Calculate error rate
                error_rate = (errors / invocations * 100) if invocations > 0 else 0
                func_metrics["error_rate"] = error_rate

                # Get duration
                duration_response = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Duration",
                    Dimensions=[{"Name": "FunctionName", "Value": full_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=["Average"],
                )

                if duration_response["Datapoints"]:
                    avg_duration = sum(point["Average"] for point in duration_response["Datapoints"]) / len(
                        duration_response["Datapoints"]
                    )
                    func_metrics["avg_duration"] = avg_duration
                    total_duration += avg_duration
                    duration_count += 1
                else:
                    func_metrics["avg_duration"] = 0

                # Get memory utilization
                memory_response = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="MemoryUtilization",
                    Dimensions=[{"Name": "FunctionName", "Value": full_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=["Average"],
                )

                if memory_response["Datapoints"]:
                    memory_util = sum(point["Average"] for point in memory_response["Datapoints"]) / len(
                        memory_response["Datapoints"]
                    )
                    func_metrics["memory_utilization"] = memory_util
                else:
                    func_metrics["memory_utilization"] = 0

                metrics["functions"][func_name] = func_metrics

            except Exception as e:
                func_metrics["error"] = str(e)
                metrics["functions"][func_name] = func_metrics

        # Calculate summary metrics
        metrics["summary"]["total_invocations"] = total_invocations
        metrics["summary"]["total_errors"] = total_errors
        metrics["summary"]["error_rate"] = (total_errors / total_invocations * 100) if total_invocations > 0 else 0
        metrics["summary"]["avg_duration"] = (total_duration / duration_count) if duration_count > 0 else 0

        return metrics

    def get_api_gateway_metrics(self, minutes: int = 5) -> Dict[str, Any]:
        """Get API Gateway metrics from CloudWatch."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)

        metrics = {
            "timestamp": end_time.isoformat() + "Z",
            "api_calls": 0,
            "errors_4xx": 0,
            "errors_5xx": 0,
            "latency": 0,
            "error_rate": 0,
        }

        try:
            # Get API call count
            count_response = self.cloudwatch.get_metric_statistics(
                Namespace="AWS/ApiGateway",
                MetricName="Count",
                Dimensions=[{"Name": "Stage", "Value": self.environment}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=["Sum"],
            )

            api_calls = sum(point["Sum"] for point in count_response["Datapoints"])
            metrics["api_calls"] = api_calls

            # Get 4XX errors
            errors_4xx_response = self.cloudwatch.get_metric_statistics(
                Namespace="AWS/ApiGateway",
                MetricName="4XXError",
                Dimensions=[{"Name": "Stage", "Value": self.environment}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=["Sum"],
            )

            errors_4xx = sum(point["Sum"] for point in errors_4xx_response["Datapoints"])
            metrics["errors_4xx"] = errors_4xx

            # Get 5XX errors
            errors_5xx_response = self.cloudwatch.get_metric_statistics(
                Namespace="AWS/ApiGateway",
                MetricName="5XXError",
                Dimensions=[{"Name": "Stage", "Value": self.environment}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=["Sum"],
            )

            errors_5xx = sum(point["Sum"] for point in errors_5xx_response["Datapoints"])
            metrics["errors_5xx"] = errors_5xx

            # Calculate error rate
            total_errors = errors_4xx + errors_5xx
            error_rate = (total_errors / api_calls * 100) if api_calls > 0 else 0
            metrics["error_rate"] = error_rate

            # Get latency
            latency_response = self.cloudwatch.get_metric_statistics(
                Namespace="AWS/ApiGateway",
                MetricName="Latency",
                Dimensions=[{"Name": "Stage", "Value": self.environment}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=["Average"],
            )

            if latency_response["Datapoints"]:
                avg_latency = sum(point["Average"] for point in latency_response["Datapoints"]) / len(
                    latency_response["Datapoints"]
                )
                metrics["latency"] = avg_latency

        except Exception as e:
            metrics["error"] = str(e)

        return metrics

    def check_recent_errors(self, minutes: int = 5) -> Dict[str, Any]:
        """Check for recent errors in CloudWatch logs."""
        functions = ["search_handler", "results_handler", "connect_handler"]

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)

        error_summary = {"timestamp": end_time.isoformat() + "Z", "total_errors": 0, "functions": {}, "recent_errors": []}

        for func_name in functions:
            log_group = f"/aws/lambda/webwunder-{self.environment}-{func_name}"

            try:
                response = self.logs.filter_log_events(
                    logGroupName=log_group,
                    startTime=int(start_time.timestamp() * 1000),
                    endTime=int(end_time.timestamp() * 1000),
                    filterPattern="ERROR",
                )

                error_count = len(response["events"])
                error_summary["functions"][func_name] = error_count
                error_summary["total_errors"] += error_count

                # Collect recent error messages
                for event in response["events"][-5:]:  # Last 5 errors
                    error_summary["recent_errors"].append(
                        {
                            "function": func_name,
                            "timestamp": datetime.fromtimestamp(event["timestamp"] / 1000).isoformat(),
                            "message": event["message"][:200],  # Truncate long messages
                        }
                    )

            except Exception as e:
                error_summary["functions"][func_name] = f"Error: {str(e)}"

        return error_summary

    def analyze_metrics(self, lambda_metrics: Dict, api_metrics: Dict, error_summary: Dict) -> List[Dict]:
        """Analyze metrics and generate alerts."""
        alerts = []

        # Check Lambda error rate
        if lambda_metrics["summary"]["error_rate"] > self.thresholds["error_rate"]:
            alerts.append(
                {
                    "type": "error_rate",
                    "severity": "high",
                    "message": f"Lambda error rate is {lambda_metrics['summary']['error_rate']:.1f}% (threshold: {self.thresholds['error_rate']}%)",
                    "value": lambda_metrics["summary"]["error_rate"],
                    "threshold": self.thresholds["error_rate"],
                }
            )

        # Check API Gateway error rate
        if api_metrics.get("error_rate", 0) > self.thresholds["error_rate"]:
            alerts.append(
                {
                    "type": "api_error_rate",
                    "severity": "high",
                    "message": f"API Gateway error rate is {api_metrics['error_rate']:.1f}% (threshold: {self.thresholds['error_rate']}%)",
                    "value": api_metrics["error_rate"],
                    "threshold": self.thresholds["error_rate"],
                }
            )

        # Check response time
        if lambda_metrics["summary"]["avg_duration"] > self.thresholds["response_time"]:
            alerts.append(
                {
                    "type": "response_time",
                    "severity": "medium",
                    "message": f"Average response time is {lambda_metrics['summary']['avg_duration']:.0f}ms (threshold: {self.thresholds['response_time']}ms)",
                    "value": lambda_metrics["summary"]["avg_duration"],
                    "threshold": self.thresholds["response_time"],
                }
            )

        # Check individual function performance
        for func_name, func_metrics in lambda_metrics["functions"].items():
            if isinstance(func_metrics, dict) and "error_rate" in func_metrics:
                if func_metrics["error_rate"] > self.thresholds["error_rate"]:
                    alerts.append(
                        {
                            "type": "function_error_rate",
                            "severity": "medium",
                            "message": f"Function {func_name} error rate is {func_metrics['error_rate']:.1f}%",
                            "function": func_name,
                            "value": func_metrics["error_rate"],
                            "threshold": self.thresholds["error_rate"],
                        }
                    )

                if func_metrics.get("memory_utilization", 0) > self.thresholds["memory_utilization"]:
                    alerts.append(
                        {
                            "type": "memory_utilization",
                            "severity": "low",
                            "message": f"Function {func_name} memory utilization is {func_metrics['memory_utilization']:.1f}%",
                            "function": func_name,
                            "value": func_metrics["memory_utilization"],
                            "threshold": self.thresholds["memory_utilization"],
                        }
                    )

        # Check for error spikes
        if error_summary["total_errors"] > 20:  # More than 20 errors in 5 minutes
            alerts.append(
                {
                    "type": "error_spike",
                    "severity": "high",
                    "message": f"Error spike detected: {error_summary['total_errors']} errors in last 5 minutes",
                    "value": error_summary["total_errors"],
                }
            )

        return alerts

    def print_metrics_summary(self, lambda_metrics: Dict, api_metrics: Dict, error_summary: Dict, alerts: List):
        """Print a formatted summary of current metrics."""
        print(f"\n📊 Deployment Metrics Summary - {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 60)

        # Lambda metrics
        print("⚡ Lambda Functions:")
        print(f"  Total Invocations: {lambda_metrics['summary']['total_invocations']}")
        print(f"  Total Errors: {lambda_metrics['summary']['total_errors']}")
        print(f"  Error Rate: {lambda_metrics['summary']['error_rate']:.1f}%")
        print(f"  Avg Duration: {lambda_metrics['summary']['avg_duration']:.0f}ms")

        # API Gateway metrics
        print("\n🌐 API Gateway:")
        print(f"  API Calls: {api_metrics.get('api_calls', 0)}")
        print(f"  4XX Errors: {api_metrics.get('errors_4xx', 0)}")
        print(f"  5XX Errors: {api_metrics.get('errors_5xx', 0)}")
        print(f"  Error Rate: {api_metrics.get('error_rate', 0):.1f}%")
        print(f"  Avg Latency: {api_metrics.get('latency', 0):.0f}ms")

        # Error summary
        print(f"\n🚨 Recent Errors: {error_summary['total_errors']} in last 5 minutes")

        # Alerts
        if alerts:
            print(f"\n⚠️ Active Alerts ({len(alerts)}):")
            for alert in alerts:
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert["severity"], "⚪")
                print(f"  {severity_icon} {alert['message']}")
        else:
            print("\n✅ No alerts - system healthy")

        print("-" * 60)

    def monitor_deployment(self, duration: int = 600, interval: int = 60) -> Dict[str, Any]:
        """Monitor deployment for specified duration."""
        print(f"🔍 Starting deployment monitoring for {duration} seconds...")
        print(f"Environment: {self.environment}")
        print(f"Region: {self.region}")
        print(f"Monitoring interval: {interval} seconds")
        print("Press Ctrl+C to stop monitoring early")

        self.monitoring = True
        start_time = time.time()
        monitoring_results = {
            "environment": self.environment,
            "start_time": datetime.utcnow().isoformat() + "Z",
            "duration": duration,
            "interval": interval,
            "snapshots": [],
            "alerts_history": [],
            "summary": {},
        }

        # Set up signal handler for graceful shutdown
        def signal_handler(signum, frame):
            print("\n⚠️ Monitoring interrupted by user")
            self.monitoring = False

        signal.signal(signal.SIGINT, signal_handler)

        try:
            while self.monitoring and (time.time() - start_time) < duration:
                snapshot_start = time.time()

                # Collect metrics
                lambda_metrics = self.get_lambda_metrics()
                api_metrics = self.get_api_gateway_metrics()
                error_summary = self.check_recent_errors()

                # Analyze metrics and generate alerts
                alerts = self.analyze_metrics(lambda_metrics, api_metrics, error_summary)

                # Store snapshot
                snapshot = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "lambda_metrics": lambda_metrics,
                    "api_metrics": api_metrics,
                    "error_summary": error_summary,
                    "alerts": alerts,
                }
                monitoring_results["snapshots"].append(snapshot)

                # Store alerts in history
                if alerts:
                    monitoring_results["alerts_history"].extend(alerts)

                # Print summary
                self.print_metrics_summary(lambda_metrics, api_metrics, error_summary, alerts)

                # Wait for next interval
                elapsed = time.time() - snapshot_start
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0 and self.monitoring:
                    time.sleep(sleep_time)

        except Exception as e:
            print(f"❌ Monitoring error: {str(e)}")
            monitoring_results["error"] = str(e)

        finally:
            self.monitoring = False
            monitoring_results["end_time"] = datetime.utcnow().isoformat() + "Z"
            monitoring_results["actual_duration"] = time.time() - start_time

            # Generate summary
            self._generate_monitoring_summary(monitoring_results)

        return monitoring_results

    def _generate_monitoring_summary(self, results: Dict):
        """Generate monitoring summary."""
        print("\n" + "=" * 60)
        print("📋 DEPLOYMENT MONITORING SUMMARY")
        print("=" * 60)

        if results["snapshots"]:
            # Calculate averages
            total_invocations = sum(s["lambda_metrics"]["summary"]["total_invocations"] for s in results["snapshots"])
            total_errors = sum(s["lambda_metrics"]["summary"]["total_errors"] for s in results["snapshots"])
            avg_error_rate = sum(s["lambda_metrics"]["summary"]["error_rate"] for s in results["snapshots"]) / len(
                results["snapshots"]
            )
            avg_duration = sum(s["lambda_metrics"]["summary"]["avg_duration"] for s in results["snapshots"]) / len(
                results["snapshots"]
            )

            print(f"Duration: {results['actual_duration']:.0f} seconds")
            print(f"Snapshots: {len(results['snapshots'])}")
            print(f"Total Invocations: {total_invocations}")
            print(f"Total Errors: {total_errors}")
            print(f"Average Error Rate: {avg_error_rate:.1f}%")
            print(f"Average Response Time: {avg_duration:.0f}ms")

            # Alert summary
            unique_alerts = set()
            for alert in results["alerts_history"]:
                unique_alerts.add(alert["type"])

            if unique_alerts:
                print(f"\nAlert Types Triggered: {len(unique_alerts)}")
                for alert_type in unique_alerts:
                    count = sum(1 for a in results["alerts_history"] if a["type"] == alert_type)
                    print(f"  {alert_type}: {count} times")
            else:
                print("\n✅ No alerts triggered during monitoring")

            # Health assessment
            if avg_error_rate < self.thresholds["error_rate"] and avg_duration < self.thresholds["response_time"]:
                print(f"\n🎯 DEPLOYMENT HEALTH: ✅ HEALTHY")
            else:
                print(f"\n🎯 DEPLOYMENT HEALTH: ⚠️ NEEDS ATTENTION")

        results["summary"] = {
            "health_status": "healthy" if avg_error_rate < self.thresholds["error_rate"] else "unhealthy",
            "total_invocations": total_invocations,
            "total_errors": total_errors,
            "avg_error_rate": avg_error_rate,
            "avg_duration": avg_duration,
            "alert_types": list(unique_alerts),
        }

        print("=" * 60)


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Monitor deployment health and performance")
    parser.add_argument("environment", choices=["staging", "production"], help="Environment to monitor")
    parser.add_argument("--region", default="eu-central-1", help="AWS region (default: eu-central-1)")
    parser.add_argument("--duration", type=int, default=600, help="Monitoring duration in seconds (default: 600)")
    parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds (default: 60)")
    parser.add_argument("--output", help="Output file for JSON results")
    parser.add_argument("--error-threshold", type=float, default=5.0, help="Error rate threshold percentage (default: 5.0)")
    parser.add_argument("--response-threshold", type=int, default=5000, help="Response time threshold in ms (default: 5000)")

    args = parser.parse_args()

    # Create monitor
    monitor = DeploymentMonitor(args.environment, args.region)

    # Update thresholds if provided
    monitor.thresholds["error_rate"] = args.error_threshold
    monitor.thresholds["response_time"] = args.response_threshold

    try:
        # Start monitoring
        results = monitor.monitor_deployment(args.duration, args.interval)

        # Save results to file if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\n📄 Results saved to: {args.output}")

        # Exit with appropriate code based on health
        if results.get("summary", {}).get("health_status") == "healthy":
            print("\n✅ Deployment monitoring completed - system healthy")
            sys.exit(0)
        else:
            print("\n⚠️ Deployment monitoring completed - system needs attention")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ Monitoring interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n💥 Monitoring failed with error: {str(e)}")
        sys.exit(3)


if __name__ == "__main__":
    main()
