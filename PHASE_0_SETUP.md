# Phase 0 Setup Guide - Cost Monitoring Foundation

This guide walks you through setting up Phase 0 of the CTI Scraper system.

**Goal:** Establish cost monitoring and alerting infrastructure before deploying expensive resources.

**Expected Monthly Cost:** $1-2

---

## Prerequisites Checklist

- [ ] AWS Account with admin access
- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] Python 3.11+ installed
- [ ] Terraform 1.5+ installed
- [ ] Git installed (optional)
- [ ] Email address for cost alerts

---

## Step 1: Verify AWS Access

```bash
# Check AWS credentials
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/..."
# }
```

**Note your Account ID** - you'll need it for the `.env` file.

---

## Step 2: Python Environment Setup

### Windows

```powershell
# Navigate to project directory
cd D:\Users\andrew.skatoff\Huntable.AI.Bedrock

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Linux/Mac

```bash
# Navigate to project directory
cd /path/to/Huntable.AI.Bedrock

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

---

## Step 3: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Use notepad, vim, nano, or your preferred editor
notepad .env  # Windows
# nano .env   # Linux
# vim .env    # Advanced users
```

**Required variables:**

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012  # Replace with your account ID
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key

# Cost Monitoring
COST_ALERT_EMAIL=your-email@example.com

# Database (for future phases, use defaults for now)
DATABASE_URL=postgresql+asyncpg://cti_user:password@localhost:5432/cti_scraper
```

---

## Step 4: Test Python Application Locally

```bash
# Ensure virtual environment is activated
# You should see (venv) in your prompt

# Navigate to src directory
cd src

# Run FastAPI application
uvicorn cti_scraper.api.app:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

**Test endpoints:**

Open browser to:
- http://localhost:8000/docs - API documentation
- http://localhost:8000/health - Health check
- http://localhost:8000/costs/dashboard - Cost dashboard (may show zero initially)

**Note:** Cost data may show zero if your AWS account has no recent activity, or due to Cost Explorer's 24-hour delay.

Press `Ctrl+C` to stop the server.

---

## Step 5: Deploy Terraform Infrastructure

### 5.1 Configure Terraform Variables

```bash
# Navigate to terraform directory
cd terraform

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars
notepad terraform.tfvars  # Windows
# nano terraform.tfvars   # Linux
```

**Update these values:**

```hcl
aws_region       = "us-east-1"
project_name     = "cti-scraper"
environment      = "dev"
cost_alert_email = "your-email@example.com"  # IMPORTANT: Use real email

# Budget thresholds
cost_alert_threshold_25 = 25.00
cost_alert_threshold_50 = 50.00
cost_alert_threshold_80 = 80.00
cost_alert_threshold_95 = 95.00
monthly_budget          = 100.00
```

### 5.2 Initialize Terraform

```bash
# Initialize Terraform (downloads providers)
terraform init

# Expected output:
# Terraform has been successfully initialized!
```

### 5.3 Preview Infrastructure Changes

```bash
# See what will be created
terraform plan

# Review the output carefully
# You should see:
# - IAM roles (3)
# - IAM policies (3)
# - SNS topic and subscription
# - CloudWatch log group
# - AWS Budget
# - CloudWatch alarms
# - CloudWatch dashboard
```

### 5.4 Deploy Infrastructure

```bash
# Apply changes
terraform apply

# Type 'yes' when prompted
```

**Expected output:**
```
Apply complete! Resources: 15 added, 0 changed, 0 destroyed.

Outputs:
account_id = "123456789012"
region = "us-east-1"
cost_monitor_role_arn = "arn:aws:iam::123456789012:role/..."
app_role_arn = "arn:aws:iam::123456789012:role/..."
cost_alerts_topic_arn = "arn:aws:sns:us-east-1:123456789012:..."
dashboard_url = "https://console.aws.amazon.com/cloudwatch/..."
```

### 5.5 Confirm SNS Subscription

**CRITICAL STEP:**

1. Check your email inbox for "AWS Notification - Subscription Confirmation"
2. Click "Confirm subscription" link
3. You should see "Subscription confirmed!"

**Without this step, you won't receive cost alerts.**

---

## Step 6: Verify Deployment

### 6.1 Check AWS Console

**CloudWatch Dashboard:**
```
AWS Console → CloudWatch → Dashboards → cti-scraper-dev-cost-monitoring
```

**AWS Budget:**
```
AWS Console → Billing → Budgets → cti-scraper-dev-monthly-budget
```

**SNS Topic:**
```
AWS Console → SNS → Topics → cti-scraper-dev-cost-alerts
```

### 6.2 Test Cost Monitoring API

```bash
# Start the application (from project root)
cd ..  # Back to project root
cd src
uvicorn cti_scraper.api.app:app --reload

# In another terminal, test endpoints:
curl http://localhost:8000/costs/summary | python -m json.tool
curl http://localhost:8000/costs/alerts | python -m json.tool
```

### 6.3 Test Emergency Shutdown (Dry-Run)

```bash
# From project root
cd scripts
python emergency_shutdown.py --dry-run

# Expected output:
# [DRY-RUN] Checking EventBridge rules...
# [DRY-RUN] Checking Lambda event sources...
# [DRY-RUN] Stopping ECS tasks...
# ...
```

---

## Step 7: Monitor Initial Costs

### First 24 Hours

**Important:** AWS Cost Explorer data has a 24-hour delay. Initial cost metrics may be zero.

**What to expect:**
- CloudWatch Logs: ~$0.02/day
- SNS: $0 (free tier covers 1,000 notifications/month)
- AWS Budgets: $0.02/month flat fee

**Total Phase 0 cost: ~$1-2/month**

### Daily Monitoring Routine

1. **Check cost dashboard:**
   ```
   http://localhost:8000/costs/dashboard
   ```

2. **Check email for alerts** (if thresholds exceeded)

3. **Review CloudWatch dashboard** in AWS Console

---

## Step 8: Set Up Daily Cost Checks

### Option A: Manual Daily Check

```bash
# Run FastAPI app
cd src
uvicorn cti_scraper.api.app:app

# Open browser
http://localhost:8000/costs/dashboard
```

### Option B: Scheduled Script (Windows Task Scheduler)

Create a batch file `check_costs.bat`:

```batch
@echo off
cd D:\Users\andrew.skatoff\Huntable.AI.Bedrock
call venv\Scripts\activate
cd src
python -c "from cti_scraper.services import CostMonitorService; import json; print(json.dumps(CostMonitorService().get_cost_summary(), indent=2))"
pause
```

Schedule in Task Scheduler to run daily at 9 AM.

---

## Phase 0 Checklist - Are You Ready for Phase 1?

Before proceeding to Phase 1, verify:

- [ ] Terraform deployed successfully
- [ ] SNS email subscription confirmed
- [ ] Cost dashboard accessible
- [ ] Emergency shutdown script tested (dry-run)
- [ ] AWS Budget shows "cti-scraper-dev-monthly-budget"
- [ ] CloudWatch logs group created
- [ ] IAM roles created (3 roles)
- [ ] Phase 0 costs < $2/month
- [ ] Email alerts working (you can test by manually triggering SNS)

---

## Troubleshooting

### Issue: Cost Dashboard Shows All Zeros

**Cause:** Cost Explorer has 24-hour data delay, or no AWS usage yet.

**Solution:** Wait 24-48 hours for data to appear. Verify AWS credentials are correct.

### Issue: Terraform Apply Fails - "Access Denied"

**Cause:** AWS credentials lack required permissions.

**Solution:**
```bash
# Check current user permissions
aws iam get-user
aws iam list-user-policies --user-name YOUR_USERNAME
aws iam list-attached-user-policies --user-name YOUR_USERNAME
```

Required IAM permissions:
- CloudWatch Full Access
- SNS Full Access
- Budgets Create/Read
- IAM Create/Read (for roles)

### Issue: SNS Email Not Received

**Cause:** Email in spam, or wrong email address.

**Solution:**
1. Check spam/junk folder
2. Verify email in terraform.tfvars
3. Check SNS topic subscriptions in AWS Console
4. Manually resend confirmation:
   ```bash
   aws sns subscribe --topic-arn <TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com
   ```

### Issue: "Module not found" Error

**Cause:** Virtual environment not activated or dependencies not installed.

**Solution:**
```bash
# Activate venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux

# Reinstall dependencies
pip install -r requirements.txt
```

---

## Cost Gate Decision: Phase 0 → Phase 1

**Criteria for proceeding to Phase 1:**

1. ✅ Phase 0 infrastructure deployed successfully
2. ✅ Phase 0 monthly cost < $2
3. ✅ Cost monitoring and alerts functional
4. ✅ Emergency shutdown tested

**Phase 1 will add:**
- RDS PostgreSQL (~$15/month)
- ECS Fargate Spot (~$7/month)
- S3 bucket (~$1/month)

**Projected Phase 0 + Phase 1 cost: ~$25/month**

**Decision:** If Phase 0 costs are within budget, you may proceed to Phase 1.

---

## Next Steps

Once Phase 0 is validated:

1. Review [README.md](README.md) for full project overview
2. Review Phase 1 plan (to be created)
3. Ensure budget is comfortable with $25/month baseline
4. Proceed with Phase 1 deployment

---

## Emergency Contacts

**If costs spike unexpectedly:**

1. Run emergency shutdown:
   ```bash
   python scripts/emergency_shutdown.py
   ```

2. Check AWS Cost Explorer for unexpected charges

3. Review CloudWatch logs for errors

4. Contact AWS Support if needed

---

## Phase 0 Success Criteria ✅

You've successfully completed Phase 0 if:

- ✅ Cost monitoring dashboard accessible and showing data
- ✅ AWS Budget and alerts configured
- ✅ Terraform infrastructure deployed
- ✅ Emergency procedures tested
- ✅ Monthly cost < $2
- ✅ Email alerts confirmed working

**Congratulations! You're ready to evaluate Phase 1 deployment.**
