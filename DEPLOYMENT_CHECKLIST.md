# Phase 0 Deployment Checklist

Use this checklist to deploy Phase 0 infrastructure step-by-step.

---

## Pre-Deployment

### 1. Verify Prerequisites
- [ ] AWS Account created
- [ ] AWS CLI installed: `aws --version`
- [ ] AWS CLI configured: `aws configure`
- [ ] Python 3.11+ installed: `python --version`
- [ ] Terraform installed: `terraform --version`
- [ ] Git installed (optional): `git --version`

### 2. Verify AWS Access
```bash
aws sts get-caller-identity
```
- [ ] Command succeeds and shows your account ID
- [ ] Note your Account ID: ________________

### 3. Test AWS Permissions
```bash
# Test Cost Explorer access
aws ce get-cost-and-usage \
  --time-period Start=2025-11-24,End=2025-11-25 \
  --granularity DAILY \
  --metrics UnblendedCost
```
- [ ] Command succeeds (or fails with "no data" - that's okay)

---

## Local Setup

### 4. Create Python Virtual Environment
```bash
cd D:\Users\andrew.skatoff\Huntable.AI.Bedrock
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```
- [ ] Virtual environment created
- [ ] Dependencies installed successfully
- [ ] No error messages

### 5. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env with your values
```
- [ ] `.env` file created
- [ ] `AWS_REGION` set (e.g., us-east-1)
- [ ] `AWS_ACCOUNT_ID` set (from step 2)
- [ ] `AWS_ACCESS_KEY_ID` set
- [ ] `AWS_SECRET_ACCESS_KEY` set
- [ ] `COST_ALERT_EMAIL` set to your real email

### 6. Test Local Application
```bash
cd src
uvicorn cti_scraper.api.app:app --reload
```
- [ ] Server starts without errors
- [ ] Visit http://localhost:8000/docs - API docs load
- [ ] Visit http://localhost:8000/health - Returns "healthy"
- [ ] Press Ctrl+C to stop server

---

## Terraform Deployment

### 7. Configure Terraform Variables
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars
```
- [ ] `terraform.tfvars` created
- [ ] `cost_alert_email` set to your real email
- [ ] Review all other variables

### 8. Initialize Terraform
```bash
terraform init
```
- [ ] Terraform initialized successfully
- [ ] Provider plugins downloaded
- [ ] No errors

### 9. Validate Configuration
```bash
terraform validate
```
- [ ] Configuration is valid
- [ ] No syntax errors

### 10. Plan Infrastructure
```bash
terraform plan
```
- [ ] Plan completes successfully
- [ ] Review planned resources:
  - [ ] 3 IAM roles
  - [ ] 3 IAM policies
  - [ ] 6 IAM policy attachments
  - [ ] 1 SNS topic
  - [ ] 1 SNS subscription
  - [ ] 1 CloudWatch log group
  - [ ] 1 AWS Budget
  - [ ] 1 CloudWatch metric filter
  - [ ] 1 CloudWatch alarm
  - [ ] 1 CloudWatch dashboard
  - [ ] **Total: ~15 resources**

### 11. Deploy Infrastructure
```bash
terraform apply
```
- [ ] Review plan one final time
- [ ] Type "yes" to confirm
- [ ] Deployment completes successfully
- [ ] Note the output values

**Copy these outputs:**
- Account ID: ________________
- Cost Monitor Role ARN: ________________
- App Role ARN: ________________
- SNS Topic ARN: ________________
- Dashboard URL: ________________

---

## Post-Deployment Verification

### 12. Confirm SNS Email Subscription
- [ ] Check email inbox (and spam folder)
- [ ] Email subject: "AWS Notification - Subscription Confirmation"
- [ ] Click "Confirm subscription" link
- [ ] See "Subscription confirmed!" message

**CRITICAL: Without this, you won't get cost alerts!**

### 13. Verify AWS Console Resources

**CloudWatch Dashboard:**
```
AWS Console → CloudWatch → Dashboards → cti-scraper-dev-cost-monitoring
```
- [ ] Dashboard exists
- [ ] Can view metrics (may be empty initially)

**AWS Budget:**
```
AWS Console → Billing → Budgets
```
- [ ] Budget "cti-scraper-dev-monthly-budget" exists
- [ ] Shows $100.00 limit
- [ ] Has 5 alert thresholds configured

**SNS Topic:**
```
AWS Console → SNS → Topics
```
- [ ] Topic "cti-scraper-dev-cost-alerts" exists
- [ ] Has 1 subscription (your email)
- [ ] Subscription status: "Confirmed"

**CloudWatch Logs:**
```
AWS Console → CloudWatch → Log Groups
```
- [ ] Log group "/aws/cti-scraper/dev" exists

**IAM Roles:**
```
AWS Console → IAM → Roles
```
- [ ] "cti-scraper-dev-cost-monitor-role" exists
- [ ] "cti-scraper-dev-app-role" exists
- [ ] "cti-scraper-dev-ecs-execution-role" exists

### 14. Test Cost Monitoring API

**Start application:**
```bash
cd D:\Users\andrew.skatoff\Huntable.AI.Bedrock
venv\Scripts\activate
python main.py
```

**In another terminal, test endpoints:**
```bash
# Cost summary
curl http://localhost:8000/costs/summary

# Alerts
curl http://localhost:8000/costs/alerts

# Dashboard (open in browser)
# http://localhost:8000/costs/dashboard
```

- [ ] `/costs/summary` returns JSON (may show $0.00 initially)
- [ ] `/costs/alerts` returns empty array (no alerts yet)
- [ ] Cost dashboard loads in browser
- [ ] No error messages

**Note:** Cost data may be $0.00 for first 24-48 hours due to Cost Explorer delay.

### 15. Test Emergency Shutdown (Dry-Run)
```bash
cd scripts
python emergency_shutdown.py --dry-run
```
- [ ] Script runs without errors
- [ ] Shows "[DRY-RUN]" prefix on all actions
- [ ] No actual resources affected

### 16. Test SNS Alert (Optional)
```bash
aws sns publish \
  --topic-arn <YOUR_SNS_TOPIC_ARN> \
  --subject "Test Alert" \
  --message "This is a test cost alert from CTI Scraper"
```
- [ ] Command succeeds
- [ ] Receive test email within 1-2 minutes

---

## Monitoring Period (7 Days)

### 17. Daily Checks (Days 1-7)

**Day 1:**
- [ ] Check cost dashboard: http://localhost:8000/costs/dashboard
- [ ] Verify no unexpected charges
- [ ] Check email for alerts

**Day 2:**
- [ ] Cost data starts appearing (Cost Explorer delay)
- [ ] Verify Phase 0 costs < $0.50/day
- [ ] Check email for alerts

**Day 3-7:**
- [ ] Daily cost check
- [ ] Monitor for anomalies
- [ ] Verify no budget alerts

**After 7 days:**
- [ ] Calculate average daily cost: $______
- [ ] Projected monthly cost: $______ (should be < $2.00)
- [ ] Review CloudWatch dashboard
- [ ] Review AWS billing dashboard

---

## Phase 0 Validation

### 18. Success Criteria

- [ ] All Terraform resources deployed
- [ ] SNS subscription confirmed
- [ ] Cost monitoring API functional
- [ ] Cost dashboard accessible
- [ ] Emergency shutdown tested (dry-run)
- [ ] 7 days of cost data collected
- [ ] Average monthly cost projection < $2.00
- [ ] No unexpected charges
- [ ] Email alerts functional

### 19. Phase 0 Cost Breakdown

| Service | Expected | Actual | Status |
|---------|----------|--------|--------|
| CloudWatch Logs | $0.50 | $____ | ☐ OK / ☐ High |
| SNS | $0.50 | $____ | ☐ OK / ☐ High |
| AWS Budgets | $0.02 | $____ | ☐ OK / ☐ High |
| Cost Explorer API | $1.00 | $____ | ☐ OK / ☐ High |
| **TOTAL** | **$2.02** | **$____** | ☐ OK / ☐ High |

---

## Phase 1 Go/No-Go Decision

### 20. Evaluate Phase 1 Readiness

**Questions to answer:**

1. Is Phase 0 functioning correctly?
   - [ ] Yes
   - [ ] No (troubleshoot before Phase 1)

2. Are Phase 0 costs within budget ($2/month)?
   - [ ] Yes (< $2/month)
   - [ ] No (investigate before Phase 1)

3. Are cost alerts working?
   - [ ] Yes (tested and confirmed)
   - [ ] No (fix before Phase 1)

4. Are you comfortable adding ~$23/month for Phase 1?
   - [ ] Yes (projected total: ~$25/month)
   - [ ] No (optimize or reconsider)

5. Have you reviewed Phase 1 requirements?
   - [ ] Yes (understand what will be deployed)
   - [ ] No (review before proceeding)

**Decision:**
- [ ] **GO:** Proceed with Phase 1 deployment
- [ ] **NO-GO:** Address issues before Phase 1
- [ ] **DEFER:** Need more time to evaluate costs

---

## Troubleshooting

### Common Issues

**Issue: Terraform apply fails**
- Check AWS credentials: `aws sts get-caller-identity`
- Verify IAM permissions
- Check for resource naming conflicts

**Issue: SNS email not received**
- Check spam folder
- Verify email address in terraform.tfvars
- Check SNS subscription status in AWS Console

**Issue: Cost dashboard shows $0.00**
- Normal for first 24-48 hours
- Cost Explorer has data delay
- Verify AWS credentials in .env

**Issue: Python import errors**
- Activate virtual environment: `venv\Scripts\activate`
- Reinstall dependencies: `pip install -r requirements.txt`

**Issue: Terraform state locked**
- Wait for previous operation to complete
- Force unlock if needed: `terraform force-unlock <LOCK_ID>`

---

## Rollback Procedure (If Needed)

If you need to undo Phase 0 deployment:

```bash
cd terraform
terraform destroy
# Type "yes" to confirm
```

**Warning:** This will delete all Phase 0 resources. Cost monitoring will stop.

---

## Next Steps After Phase 0

Once Phase 0 is validated:

1. Review PHASE_0_COMPLETION_SUMMARY.md
2. Review Phase 1 requirements (TBD)
3. Make go/no-go decision for Phase 1
4. If GO: Begin Phase 1 deployment
5. If NO-GO: Optimize Phase 0 or pause project

---

## Sign-Off

**Deployed By:** ________________

**Date:** ________________

**Phase 0 Status:** ☐ Deployed Successfully / ☐ Issues Found

**Phase 1 Decision:** ☐ GO / ☐ NO-GO / ☐ DEFER

**Notes:**
_________________________________________
_________________________________________
_________________________________________

---

**Congratulations on completing Phase 0! 🎉**

You now have comprehensive cost monitoring in place before spending on expensive resources.
