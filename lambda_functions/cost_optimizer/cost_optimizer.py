"""
Cost optimizer Lambda function for student budget monitoring.
Analyzes costs and provides optimization recommendations.
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
ce_client = boto3.client("ce", region_name="us-east-1")  # Cost Explorer only in us-east-1
sns_client = boto3.client("sns")
budgets_client = boto3.client("budgets")


def lambda_handler(event, context):
    """Main Lambda handler for cost optimization analysis."""
    try:
        # Get current costs
        current_costs = get_current_month_costs()

        # Get cost trends
        cost_trends = get_cost_trends()

        # Generate recommendations
        recommendations = generate_cost_recommendations(current_costs, cost_trends)

        # Check if we're approaching budget limits
        budget_status = check_budget_status()

        # Send alerts if necessary
        if budget_status["alert_needed"]:
            send_cost_alert(current_costs, recommendations, budget_status)

        # Log results
        logger.info(f"Cost analysis completed. Current month: {current_costs['total']:.2f} EUR")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "current_costs": current_costs,
                    "cost_trends": cost_trends,
                    "recommendations": recommendations,
                    "budget_status": budget_status,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error in cost optimizer: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def get_current_month_costs() -> Dict[str, Any]:
    """Get current month's costs by service."""
    try:
        # Get first day of current month
        now = datetime.now()
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["BlendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        costs = {}
        total_cost = 0

        for result in response["ResultsByTime"]:
            for group in result["Groups"]:
                service = group["Keys"][0]
                amount = float(group["Metrics"]["BlendedCost"]["Amount"])
                costs[service] = amount
                total_cost += amount

        return {"total": total_cost, "by_service": costs, "period": f"{start_date} to {end_date}"}

    except Exception as e:
        logger.error(f"Error getting current costs: {str(e)}")
        return {"total": 0, "by_service": {}, "error": str(e)}


def get_cost_trends() -> Dict[str, Any]:
    """Get cost trends for the last 7 days."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date.strftime("%Y-%m-%d"), "End": end_date.strftime("%Y-%m-%d")},
            Granularity="DAILY",
            Metrics=["BlendedCost"],
        )

        daily_costs = []
        for result in response["ResultsByTime"]:
            cost = float(result["Total"]["BlendedCost"]["Amount"])
            daily_costs.append({"date": result["TimePeriod"]["Start"], "cost": cost})

        # Calculate trend
        if len(daily_costs) >= 2:
            recent_avg = sum(day["cost"] for day in daily_costs[-3:]) / 3
            older_avg = sum(day["cost"] for day in daily_costs[:3]) / 3
            trend = "increasing" if recent_avg > older_avg else "decreasing"
        else:
            trend = "stable"

        return {
            "daily_costs": daily_costs,
            "trend": trend,
            "avg_daily_cost": sum(day["cost"] for day in daily_costs) / len(daily_costs) if daily_costs else 0,
        }

    except Exception as e:
        logger.error(f"Error getting cost trends: {str(e)}")
        return {"daily_costs": [], "trend": "unknown", "error": str(e)}


def generate_cost_recommendations(current_costs: Dict, cost_trends: Dict) -> List[str]:
    """Generate cost optimization recommendations."""
    recommendations = []

    # Check total cost against budget
    total_cost = current_costs.get("total", 0)
    budget_threshold = float(os.environ.get("BUDGET_THRESHOLD", "15"))

    if total_cost > budget_threshold * 0.8:  # 80% of budget
        recommendations.append(f"⚠️ Current costs ({total_cost:.2f} EUR) are approaching budget limit ({budget_threshold} EUR)")

    # Service-specific recommendations
    services = current_costs.get("by_service", {})

    # Lambda recommendations
    lambda_cost = services.get("AWS Lambda", 0)
    if lambda_cost > 5:  # More than 5 EUR for Lambda
        recommendations.append(
            f"💡 Lambda costs are high ({lambda_cost:.2f} EUR). Consider optimizing memory allocation and execution time."
        )

    # API Gateway recommendations
    api_cost = services.get("Amazon API Gateway", 0)
    if api_cost > 3:  # More than 3 EUR for API Gateway
        recommendations.append(
            f"💡 API Gateway costs are high ({api_cost:.2f} EUR). Consider implementing caching or reducing request frequency."
        )

    # CloudWatch recommendations
    cloudwatch_cost = services.get("Amazon CloudWatch", 0)
    if cloudwatch_cost > 2:  # More than 2 EUR for CloudWatch
        recommendations.append(
            f"💡 CloudWatch costs are high ({cloudwatch_cost:.2f} EUR). Consider reducing log retention or alarm frequency."
        )

    # DynamoDB recommendations
    dynamodb_cost = services.get("Amazon DynamoDB", 0)
    if dynamodb_cost > 3:  # More than 3 EUR for DynamoDB
        recommendations.append(
            f"💡 DynamoDB costs are high ({dynamodb_cost:.2f} EUR). Consider using on-demand billing or optimizing queries."
        )

    # Trend-based recommendations
    if cost_trends.get("trend") == "increasing":
        avg_daily = cost_trends.get("avg_daily_cost", 0)
        projected_monthly = avg_daily * 30
        if projected_monthly > budget_threshold:
            recommendations.append(
                f"📈 Cost trend is increasing. Projected monthly cost: {projected_monthly:.2f} EUR (exceeds budget)"
            )

    # General recommendations
    if total_cost > budget_threshold * 0.5:  # 50% of budget
        recommendations.extend(
            [
                "🔧 Consider enabling cost optimization features:",
                "  - Reduce CloudWatch log retention to 7 days",
                "  - Use AWS managed KMS keys instead of custom keys",
                "  - Disable expensive monitoring features",
                "  - Use DynamoDB on-demand billing for low usage",
            ]
        )

    return recommendations if recommendations else ["✅ Costs are within acceptable limits"]


def check_budget_status() -> Dict[str, Any]:
    """Check current budget status."""
    try:
        budget_threshold = float(os.environ.get("BUDGET_THRESHOLD", "15"))

        # This is a simplified check - in a real implementation,
        # you would use the AWS Budgets API to get actual budget status
        current_costs = get_current_month_costs()
        total_cost = current_costs.get("total", 0)

        percentage_used = (total_cost / budget_threshold) * 100

        return {
            "budget_limit": budget_threshold,
            "current_spend": total_cost,
            "percentage_used": percentage_used,
            "alert_needed": percentage_used > 80,  # Alert if over 80%
            "critical": percentage_used > 100,
        }

    except Exception as e:
        logger.error(f"Error checking budget status: {str(e)}")
        return {
            "budget_limit": 15,
            "current_spend": 0,
            "percentage_used": 0,
            "alert_needed": False,
            "critical": False,
            "error": str(e),
        }


def send_cost_alert(current_costs: Dict, recommendations: List[str], budget_status: Dict):
    """Send cost alert via SNS."""
    try:
        sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")
        if not sns_topic_arn:
            logger.warning("SNS_TOPIC_ARN not configured")
            return

        total_cost = current_costs.get("total", 0)
        budget_limit = budget_status.get("budget_limit", 15)
        percentage_used = budget_status.get("percentage_used", 0)

        subject = f"🚨 Cost Alert: {percentage_used:.1f}% of budget used"

        message = f"""
Cost Alert - Student Budget Monitoring

Current Status:
- Total spend this month: {total_cost:.2f} EUR
- Budget limit: {budget_limit} EUR
- Percentage used: {percentage_used:.1f}%

Top Services by Cost:
"""

        # Add top 5 services by cost
        services = current_costs.get("by_service", {})
        sorted_services = sorted(services.items(), key=lambda x: x[1], reverse=True)[:5]

        for service, cost in sorted_services:
            if cost > 0.01:  # Only show services with meaningful cost
                message += f"- {service}: {cost:.2f} EUR\n"

        message += f"\nRecommendations:\n"
        for rec in recommendations[:5]:  # Top 5 recommendations
            message += f"- {rec}\n"

        message += f"\nGenerated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"

        sns_client.publish(TopicArn=sns_topic_arn, Subject=subject, Message=message)

        logger.info("Cost alert sent successfully")

    except Exception as e:
        logger.error(f"Error sending cost alert: {str(e)}")


if __name__ == "__main__":
    # For local testing
    test_event = {}
    test_context = {}
    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2))
