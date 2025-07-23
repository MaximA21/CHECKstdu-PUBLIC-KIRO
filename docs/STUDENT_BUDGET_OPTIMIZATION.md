# Student Budget Cost Optimization Guide

This guide provides step-by-step instructions to optimize AWS costs for a student budget of **15-20 EUR/month**.

## 🎯 Target Cost: 15-20 EUR/month

The default configuration costs approximately **$47-141/month**. This optimization reduces costs by **~$60-80/month** to achieve the student budget target.

## 📊 Cost Optimization Summary

| Optimization | Monthly Savings | Implementation |
|-------------|----------------|----------------|
| **Remove Kinesis stream** | $28 | `enable_kinesis_stream = false` |
| **Disable AWS Backup** | $20-50 | `enable_aws_backup = false` |
| **Reduce log retention to 7 days** | $10-15 | `log_retention_days = 7` |
| **Use AWS managed KMS keys** | $2 | `enable_custom_kms_keys = false` |
| **Minimal CloudWatch alarms** | $3-5 | `minimal_cloudwatch_alarms = true` |
| **Total Savings** | **$63-100** | **All optimizations combined** |

## 🚀 Quick Implementation

### Step 1: Use Student Budget Configuration

```bash
# Copy the pre-configured student budget settings
cp terraform/terraform.tfvars.student-budget terraform/terraform.tfvars
```

### Step 2: Review Configuration

The student budget configuration includes:

```hcl
# Student Budget Cost-Optimized Terraform Variables
# Target: 15-20 EUR/month total AWS costs

# AGGRESSIVE cost optimization for student budget
log_retention_days                = 7     # Reduced from 30 days
lambda_log_retention_days         = 7     # Reduced from 14 days
step_functions_log_retention_days = 7     # Reduced from 7 days

# Disable expensive services
enable_kinesis_stream     = false  # Saves ~$28/month
enable_custom_kms_keys    = false  # Saves ~$2/month
enable_aws_backup         = false  # Saves ~$20-50/month
minimal_cloudwatch_alarms = true   # Saves ~$3-5/month

# Cost monitoring thresholds for student budget
monthly_cost_alert_threshold = 15   # Alert at 15 EUR/month
monthly_cost_limit_threshold = 20   # Hard limit at 20 EUR/month
```

### Step 3: Apply Changes

```bash
cd terraform
terraform plan
terraform apply
```

### Step 4: Monitor Costs

```bash
# Check optimization results
python3 scripts/cost-optimization.py --student-budget

# Monitor actual costs
python3 scripts/cost-optimization.py --format summary
```

## 📋 Detailed Optimizations

### 1. Remove Kinesis Stream (Saves $28/month)

**What it does:**
- Removes the expensive Kinesis data stream used for log analysis
- Kinesis costs ~$28/month for 1 shard with 24-hour retention

**Alternative:**
- Use CloudWatch Logs Insights for log analysis instead
- CloudWatch Logs Insights charges only $0.005 per GB scanned

**Implementation:**
```hcl
enable_kinesis_stream = false
```

**Impact:**
- ✅ Major cost reduction
- ⚠️ No real-time log streaming (use CloudWatch Logs Insights for queries)

### 2. Disable AWS Backup Service (Saves $20-50/month)

**What it does:**
- Disables the AWS Backup service for DynamoDB tables
- Removes backup vault, backup plans, and automated backups

**Alternative:**
- Use DynamoDB point-in-time recovery (PITR) only
- PITR costs only ~20% of table storage cost

**Implementation:**
```hcl
enable_aws_backup = false
```

**Impact:**
- ✅ Significant cost reduction
- ✅ Still have point-in-time recovery for DynamoDB
- ⚠️ No automated cross-service backups

### 3. Reduce Log Retention to 7 Days (Saves $10-15/month)

**What it does:**
- Reduces CloudWatch log retention from 30 days to 7 days
- Reduces Lambda log retention from 14 days to 7 days

**Implementation:**
```hcl
log_retention_days        = 7  # API Gateway logs
lambda_log_retention_days = 7  # Lambda function logs
```

**Impact:**
- ✅ Reduced log storage costs
- ⚠️ Shorter log history for debugging

### 4. Use AWS Managed KMS Keys (Saves $2/month)

**What it does:**
- Removes custom KMS keys ($1/month each)
- Uses AWS managed keys for encryption instead

**Implementation:**
```hcl
enable_custom_kms_keys = false
```

**Impact:**
- ✅ Small cost reduction
- ✅ Still encrypted at rest
- ⚠️ Less control over key rotation and policies

### 5. Minimal CloudWatch Alarms (Saves $3-5/month)

**What it does:**
- Reduces the number of CloudWatch alarms
- Keeps only essential failure monitoring

**Implementation:**
```hcl
minimal_cloudwatch_alarms = true
```

**Impact:**
- ✅ Reduced monitoring costs
- ⚠️ Less detailed monitoring and alerting

## 🔍 Cost Monitoring

### Set Up Cost Alerts

The student budget configuration automatically sets up cost alerts:

```hcl
monthly_cost_alert_threshold = 15   # Alert at 15 EUR/month
monthly_cost_limit_threshold = 20   # Hard limit at 20 EUR/month
```

### Monitor with Scripts

```bash
# Show student budget optimization summary
python3 scripts/cost-optimization.py --student-budget

# Analyze current costs
python3 scripts/cost-optimization.py --format summary

# Generate detailed cost report
python3 scripts/cost-optimization.py --output cost-report.json
```

### AWS Cost Explorer

Monitor costs in the AWS Console:
1. Go to AWS Cost Management → Cost Explorer
2. Set up cost budgets with $20/month threshold
3. Enable cost anomaly detection

## ⚠️ Trade-offs and Limitations

### What You Keep:
- ✅ Full application functionality
- ✅ DynamoDB with point-in-time recovery
- ✅ Essential monitoring and alerting
- ✅ Data encryption at rest and in transit
- ✅ Auto-scaling and serverless architecture

### What You Lose:
- ❌ Real-time log streaming (use CloudWatch Logs Insights instead)
- ❌ Automated cross-service backups (DynamoDB PITR still available)
- ❌ Extended log history (7 days instead of 30)
- ❌ Custom KMS key management
- ❌ Detailed monitoring for all services

## 🎓 Student-Specific Recommendations

### For Development/Learning:
- The optimized configuration is perfect for learning and development
- All core functionality remains intact
- Costs are predictable and within student budget

### For Production (Later):
- When moving to production, consider re-enabling some features:
  - Increase log retention to 30 days
  - Enable AWS Backup for critical data
  - Add more comprehensive monitoring

### Cost Management Tips:
1. **Set up billing alerts** at $15 and $20 thresholds
2. **Review costs weekly** using the cost optimization script
3. **Use AWS Free Tier** services where possible
4. **Clean up unused resources** regularly
5. **Consider AWS Educate** credits if available

## 🔧 Troubleshooting

### If Costs Are Still Too High:

1. **Check for unexpected resources:**
   ```bash
   aws ce get-cost-and-usage --time-period Start=2025-01-01,End=2025-01-31 \
     --granularity MONTHLY --metrics BlendedCost
   ```

2. **Review DynamoDB usage:**
   - Ensure tables are using on-demand billing
   - Check for unexpected data growth

3. **Verify log retention:**
   ```bash
   aws logs describe-log-groups --query 'logGroups[*].[logGroupName,retentionInDays]'
   ```

4. **Check for orphaned resources:**
   - Unused Lambda functions
   - Orphaned CloudWatch alarms
   - Unused API Gateway stages

### If You Need More Features:

Consider a **hybrid approach**:
- Keep most optimizations
- Selectively re-enable critical features
- Target 25-30 EUR/month instead of 15-20 EUR/month

## 📈 Expected Results

After implementing all optimizations:

- **Monthly cost:** 15-20 EUR
- **Savings:** 60-80 EUR/month
- **Functionality:** 95% of original features
- **Reliability:** Maintained with essential monitoring

The student budget optimization provides an excellent balance of cost savings while maintaining a fully functional serverless application suitable for learning, development, and small-scale production use.