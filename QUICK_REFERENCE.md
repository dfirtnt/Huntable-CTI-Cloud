# CTI Scraper - Quick Reference

**Phase 0: Cost Monitoring Foundation** ✅

---

## 🚀 Quick Start Commands

### Start Local Development Server
```bash
cd D:\Users\andrew.skatoff\Huntable.AI.Bedrock
venv\Scripts\activate
cd src
uvicorn cti_scraper.api.app:app --reload
```

### Access Points
- **API Docs:** http://localhost:8000/docs
- **Cost Dashboard:** http://localhost:8000/costs/dashboard
- **Health Check:** http://localhost:8000/health

---

## 💰 Cost Monitoring

### Check Current Costs
```bash
curl http://localhost:8000/costs/summary | python -m json.tool
```

### Key Metrics
- **MTD Cost:** `/costs/mtd`
- **Daily Costs:** `/costs/daily?days=7`
- **By Service:** `/costs/by-service`
- **Bedrock:** `/costs/bedrock`
- **Projected:** `/costs/projected`
- **Alerts:** `/costs/alerts`

---

## 🚨 Emergency Procedures

### Emergency Shutdown (if costs > $95)
```bash
python scripts/emergency_shutdown.py
```

### Dry-Run Test
```bash
python scripts/emergency_shutdown.py --dry-run
```

### Restart System
```bash
python scripts/restart_system.py
```

---

## 🔧 Terraform Commands

### Deploy Infrastructure
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### View Outputs
```bash
terraform output
```

### Destroy Infrastructure (CAUTION!)
```bash
terraform destroy
```

---

## 📊 Budget Thresholds

| % | Amount | Severity | Action |
|---|--------|----------|--------|
| 25% | $25 | INFO | Monitor |
| 50% | $50 | WARNING | Review |
| 80% | $80 | CRITICAL | Investigate |
| 95% | $95 | EMERGENCY | Consider shutdown |

---

## 🗂️ Key Files

### Configuration
- `.env` - Environment variables (AWS credentials, database, etc.)
- `terraform/terraform.tfvars` - Terraform variables

### Application
- `src/cti_scraper/api/app.py` - FastAPI application
- `src/cti_scraper/services/cost_monitor.py` - Cost monitoring service
- `src/cti_scraper/db/models.py` - Database models

### Scripts
- `scripts/emergency_shutdown.py` - Emergency shutdown
- `scripts/restart_system.py` - System restart

### Documentation
- `README.md` - Full project documentation
- `PHASE_0_SETUP.md` - Phase 0 setup guide
- `QUICK_REFERENCE.md` - This file

---

## 🔍 Troubleshooting Quick Fixes

### Cost Dashboard Shows Zero
**Wait 24 hours** - Cost Explorer has data delay

### Terraform Fails
```bash
aws configure
aws sts get-caller-identity
```

### Module Import Error
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

### SNS Email Not Received
Check spam folder, verify email in `terraform.tfvars`

---

## 📈 Phase Status

- [x] **Phase 0:** Cost Monitoring - **COMPLETE**
- [ ] **Phase 1:** Core Infrastructure (~$25/month projected)
- [ ] **Phase 2:** ML Pipeline
- [ ] **Phase 3:** Bedrock Integration
- [ ] **Phase 4:** Automation
- [ ] **Phase 5:** Embeddings + SIGMA
- [ ] **Phase 6:** Production

---

## 🎯 Current Phase 0 Costs

**Expected: $1-2/month**

- CloudWatch Logs: $0.50
- SNS: $0.50
- AWS Budgets: $0.02
- Cost Explorer API: $1.00

---

## ✅ Phase 0 Success Checklist

- [ ] Terraform deployed successfully
- [ ] SNS subscription confirmed
- [ ] Cost dashboard accessible
- [ ] Emergency shutdown tested (dry-run)
- [ ] AWS Budget visible in console
- [ ] Email alerts configured
- [ ] Phase 0 costs < $2/month

---

## 🆘 Emergency Contacts

**Cost Overrun:**
1. Run `python scripts/emergency_shutdown.py`
2. Check AWS Cost Explorer
3. Review CloudWatch logs
4. Email: COST_ALERT_EMAIL from `.env`

**Technical Issues:**
1. Check logs: `CloudWatch → Log Groups → /aws/cti-scraper/dev`
2. Check health: `http://localhost:8000/health`
3. Verify AWS creds: `aws sts get-caller-identity`

---

## 🔗 Useful AWS Console Links

**Replace `us-east-1` with your region if different**

### Cost Monitoring
- [Cost Explorer](https://console.aws.amazon.com/cost-management/home#/cost-explorer)
- [Budgets](https://console.aws.amazon.com/billing/home#/budgets)
- [Billing Dashboard](https://console.aws.amazon.com/billing/home)

### CloudWatch
- [Dashboards](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:)
- [Alarms](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#alarmsV2:)
- [Log Groups](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups)

### IAM
- [Roles](https://console.aws.amazon.com/iam/home#/roles)
- [Policies](https://console.aws.amazon.com/iam/home#/policies)

### SNS
- [Topics](https://console.aws.amazon.com/sns/v3/home?region=us-east-1#/topics)
- [Subscriptions](https://console.aws.amazon.com/sns/v3/home?region=us-east-1#/subscriptions)

---

## 📚 Documentation Links

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [AWS Cost Explorer API](https://docs.aws.amazon.com/cost-management/latest/APIReference/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [AWS Bedrock](https://docs.aws.amazon.com/bedrock/)

---

## 🔑 Environment Variables Quick Reference

```bash
# AWS
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret

# Database (Phase 1+)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Bedrock (Phase 3+)
BEDROCK_DAILY_BUDGET=1.50
BEDROCK_MONTHLY_BUDGET=45.00

# Alerts
COST_ALERT_EMAIL=your-email@example.com

# App
APP_ENV=development
LOG_LEVEL=INFO
```

---

## 🎓 Common Tasks

### View All IAM Roles
```bash
aws iam list-roles --query 'Roles[?contains(RoleName, `cti-scraper`)].RoleName'
```

### Check CloudWatch Logs
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/cti-scraper"
```

### Test SNS Topic
```bash
aws sns publish --topic-arn <TOPIC_ARN> --message "Test alert"
```

### Get Current AWS Costs (CLI)
```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "1 day ago" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost
```

---

## 💡 Pro Tips

1. **Set up shell alias:**
   ```bash
   alias cti-start="cd D:/Users/andrew.skatoff/Huntable.AI.Bedrock && venv/Scripts/activate && cd src && uvicorn cti_scraper.api.app:app --reload"
   ```

2. **Daily cost check routine:**
   - Morning: Check cost dashboard
   - Check email for alerts
   - Review CloudWatch dashboard weekly

3. **Before deploying Phase 1:**
   - Verify Phase 0 costs for 7 days
   - Confirm email alerts working
   - Test emergency shutdown

4. **Budget safety:**
   - Always deploy new phases on weekends (time to monitor)
   - Set phone notifications for critical alerts
   - Keep emergency shutdown script bookmarked

---

**Last Updated:** Phase 0 Implementation
**Next Review:** Before Phase 1 Deployment
