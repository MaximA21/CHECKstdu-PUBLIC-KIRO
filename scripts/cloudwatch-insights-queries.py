#!/usr/bin/env python3
"""
CloudWatch Logs Insights query runner for cost-effective log analysis.
This replaces expensive Kinesis streams with CloudWatch Logs Insights queries.
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse


class CloudWatchInsightsRunner:
    """Run CloudWatch Logs Insights queries for monitoring and analysis."""

    def __init__(self, region: str = "eu-central-1"):
        self.client = boto3.client("logs", region_name=region)
        self.region = region

    def run_query(self, query: str, log_groups: List[str], start_time: datetime, end_time: datetime) -> Dict:
        """Run a CloudWatch Logs Insights query."""
        try:
            response = self.client.start_query(
                logGroupNames=log_groups,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query,
            )

            query_id = response["queryId"]

            # Wait for query to complete
            while True:
                result = self.client.get_query_results(queryId=query_id)
                status = result["status"]

                if status == "Complete":
                    return {"status": "success", "results": result["results"], "statistics": result.get("statistics", {})}
                elif status == "Failed":
                    return {"status": "failed", "error": "Query failed"}

                time.sleep(2)  # Wait 2 seconds before checking again

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_connection_metrics(self, hours_back: int = 1) -> Dict:
        """Get WebSocket connection metrics."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        query = """
        fields @timestamp, @message, @requestId
        | filter @message like /connection/ or @message like /connect/ or @message like /disconnect/
        | stats count() by bin(5m)
        | sort @timestamp desc
        """

        log_groups = ["/aws/lambda/provider-comparison-connect-handler", "/aws/lambda/provider-comparison-results-handler"]

        return self.run_query(query, log_groups, start_time, end_time)

    def get_error_analysis(self, hours_back: int = 1) -> Dict:
        """Get error analysis from logs."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        query = """
        fields @timestamp, @message, @requestId, @type
        | filter @type = "ERROR" or @message like /ERROR/ or @message like /Exception/
        | stats count() by bin(5m), @message
        | sort @timestamp desc
        | limit 50
        """

        log_groups = [
            "/aws/lambda/provider-comparison-connect-handler",
            "/aws/lambda/provider-comparison-results-handler",
            "/aws/lambda/provider-comparison-search-handler",
            "/aws/lambda/provider-comparison-authorizer",
        ]

        return self.run_query(query, log_groups, start_time, end_time)

    def get_performance_metrics(self, hours_back: int = 1) -> Dict:
        """Get performance metrics from Lambda logs."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        query = """
        fields @timestamp, @duration, @billedDuration, @requestId, @maxMemoryUsed
        | filter @type = "REPORT"
        | stats avg(@duration), max(@duration), min(@duration), avg(@maxMemoryUsed) by bin(5m)
        | sort @timestamp desc
        """

        log_groups = [
            "/aws/lambda/provider-comparison-connect-handler",
            "/aws/lambda/provider-comparison-results-handler",
            "/aws/lambda/provider-comparison-search-handler",
        ]

        return self.run_query(query, log_groups, start_time, end_time)

    def get_traffic_distribution(self, hours_back: int = 1) -> Dict:
        """Get traffic distribution between old and new implementations."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        query = """
        fields @timestamp, @message
        | filter @message like /implementation/ or @message like /routing/
        | parse @message /implementation=(?<impl>\w+)/
        | stats count() by impl, bin(5m)
        | sort @timestamp desc
        """

        log_groups = ["/aws/lambda/provider-comparison-connect-handler", "/aws/lambda/provider-comparison-results-handler"]

        return self.run_query(query, log_groups, start_time, end_time)

    def get_connection_limits_analysis(self, hours_back: int = 1) -> Dict:
        """Analyze connection limit enforcement."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        query = """
        fields @timestamp, @message, @requestId
        | filter @message like /timeout/ or @message like /limit/ or @message like /disconnect/
        | parse @message /reason=(?<reason>\w+)/
        | stats count() by reason, bin(5m)
        | sort @timestamp desc
        """

        log_groups = ["/aws/lambda/provider-comparison-results-handler", "/aws/lambda/provider-comparison-connect-handler"]

        return self.run_query(query, log_groups, start_time, end_time)


def main():
    parser = argparse.ArgumentParser(description="Run CloudWatch Logs Insights queries")
    parser.add_argument(
        "--query-type",
        choices=["connections", "errors", "performance", "traffic", "limits"],
        required=True,
        help="Type of query to run",
    )
    parser.add_argument("--hours", type=int, default=1, help="Hours back to query (default: 1)")
    parser.add_argument("--region", default="eu-central-1", help="AWS region")
    parser.add_argument("--output", choices=["json", "table"], default="table", help="Output format")

    args = parser.parse_args()

    runner = CloudWatchInsightsRunner(region=args.region)

    # Run the appropriate query
    if args.query_type == "connections":
        result = runner.get_connection_metrics(args.hours)
    elif args.query_type == "errors":
        result = runner.get_error_analysis(args.hours)
    elif args.query_type == "performance":
        result = runner.get_performance_metrics(args.hours)
    elif args.query_type == "traffic":
        result = runner.get_traffic_distribution(args.hours)
    elif args.query_type == "limits":
        result = runner.get_connection_limits_analysis(args.hours)

        # Output results
    if args.output == "json":
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n=== {args.query_type.upper()} ANALYSIS ===")
        print(f"Time range: Last {args.hours} hour(s)")
        print(f"Status: {result.get('status', 'unknown')}")

        if result.get("status") == "success":
            results = result.get("results", [])
            print(f"Results: {len(results)} entries")

            if results:
                print("\nTop results:")
                for i, row in enumerate(results[:10]):  # Show top 10
                    # Fix: Use different quote types to avoid nesting issues
                    field_strings = [f"{field['field']}: {field['value']}" for field in row]
                    print(f"{i + 1}. {' | '.join(field_strings)}")
            else:
                print("No results found")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
