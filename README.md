# CTI Scraper - Threat Intelligence Aggregation Platform

A cost-optimized AWS-based platform for collecting, analyzing, and processing threat intelligence content with strict budget controls.

**Project Status:** Phase 1 (Core Infrastructure + Basic Scraping) ✅

**Budget Constraint:** $100/month AWS costs maximum

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- AWS Account with CLI configured
- Terraform 1.5+
- PostgreSQL 14+ (local development) or AWS RDS (production)

### Local Development Setup

1. **Clone the repository**
   ```bash
   cd D:\Users\andrew.skatoff\Huntable.AI.Bedrock
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and database settings
   ```

5. **Run the application**
   ```bash
   cd src
   uvicorn cti_scraper.api.app:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the Cost Dashboard**
   - Open browser: http://localhost:8000/costs/dashboard
   - API docs: http://localhost:8000/docs

---

## 📊 Phase 0: Cost Monitoring Foundation

**Status:** ✅ Complete

**Goal:** Set up comprehensive cost tracking and alerting before deploying expensive resources.

### What's Included

1. **Cost Monitoring Service** (`src/cti_scraper/services/cost_monitor.py`)
   - AWS Cost Explorer integration
   - Month-to-date cost tracking
   - Daily cost trends
   - Cost breakdown by service
   - Bedrock API cost monitoring
   - Projected end-of-month calculations

2. **Cost Dashboard UI** (`/costs/dashboard`)
   - Real-time cost visualization
   - Budget usage tracking
   - Service-level cost breakdown
   - Alert indicators
   - Dark mode design

3. **Database Schema** (`src/cti_scraper/db/models.py`)
   - All tables defined (ready for Phase 1+)
   - PostgreSQL with pgvector extension support
   - SQLAlchemy async ORM models

4. **Terraform Infrastructure** (`terraform/`)
   - IAM roles and policies
   - CloudWatch billing alarms (25%, 50%, 80%, 95%)
   - AWS Budgets configuration
   - SNS topic for email alerts
   - CloudWatch dashboard

5. **Emergency Shutdown Scripts** (`scripts/`)
   - `emergency_shutdown.py`: Stop all resources immediately
   - `restart_system.py`: Resume operations after shutdown

### Expected Cost

**Phase 0 Monthly Cost:** ~$1-2
- CloudWatch Logs: $0.50
- SNS: $0.50
- AWS Budgets: $0.02
- Cost Explorer API calls: $1.00

---

## 🔧 Terraform Deployment (Phase 0)

### Initial Setup

1. **Configure Terraform variables**
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your settings
   ```

2. **Initialize Terraform**
   ```bash
   terraform init
   ```

3. **Preview changes**
   ```bash
   terraform plan
   ```

4. **Deploy infrastructure**
   ```bash
   terraform apply
   ```

5. **Confirm SNS subscription**
   - Check your email for SNS subscription confirmation
   - Click the confirmation link to enable cost alerts

### What Gets Created

- ✅ IAM roles (cost monitoring, app role, ECS execution)
- ✅ CloudWatch log group
- ✅ SNS topic for cost alerts
- ✅ AWS Budget with 4 threshold alerts
- ✅ CloudWatch billing alarms
- ✅ CloudWatch dashboard

---

## 🚨 Emergency Procedures

### If Costs Approach $95 (95% of budget)

**Option 1: Emergency Shutdown**
```bash
python scripts/emergency_shutdown.py
```

This will:
1. Disable all EventBridge scheduled tasks
2. Disable Lambda event sources
3. Stop all ECS tasks
4. Create RDS snapshot
5. Stop RDS instance

**Option 2: Dry-Run First (Recommended)**
```bash
python scripts/emergency_shutdown.py --dry-run
```

### To Restart After Shutdown

```bash
python scripts/restart_system.py
```

---

## 📈 Cost Monitoring

### Accessing Cost Data

**Web Dashboard:**
```
http://localhost:8000/costs/dashboard
```

**API Endpoints:**
- `GET /costs/summary` - Comprehensive cost summary
- `GET /costs/mtd` - Month-to-date costs
- `GET /costs/daily?days=7` - Daily costs for last N days
- `GET /costs/by-service` - Costs grouped by AWS service
- `GET /costs/bedrock` - Bedrock-specific costs
- `GET /costs/projected` - Projected end-of-month cost
- `GET /costs/alerts` - Budget alert status

### Alert Thresholds

| Threshold | Amount | Action |
|-----------|--------|--------|
| 25% | $25 | Email alert (informational) |
| 50% | $50 | Email alert (monitor closely) |
| 80% | $80 | Email alert + review costs |
| 95% | $95 | Email alert + consider emergency shutdown |
| 100% | $100 | Budget exceeded |

### CloudWatch Dashboard

Access via AWS Console:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:
```

---

## 🗂️ Project Structure

```
Huntable.AI.Bedrock/
├── src/
│   └── cti_scraper/
│       ├── api/              # FastAPI application
│       │   ├── app.py        # App factory
│       │   └── routes/       # API routes
│       │       ├── cost.py   # Cost monitoring endpoints
│       │       └── health.py # Health check endpoints
│       ├── config/           # Configuration
│       │   └── settings.py   # Pydantic settings
│       ├── db/               # Database
│       │   ├── base.py       # SQLAlchemy setup
│       │   └── models.py     # All database models
│       ├── services/         # Business logic
│       │   └── cost_monitor.py  # Cost monitoring service
│       ├── templates/        # Jinja2 templates
│       │   └── cost_dashboard.html
│       └── utils/            # Utilities
├── terraform/                # Infrastructure as Code
│   ├── main.tf               # Main configuration
│   ├── variables.tf          # Input variables
│   ├── outputs.tf            # Output values
│   ├── iam.tf                # IAM roles and policies
│   └── monitoring.tf         # CloudWatch, SNS, Budgets
├── scripts/                  # Operational scripts
│   ├── emergency_shutdown.py # Emergency cost control
│   └── restart_system.py     # System restart
├── .env.example              # Environment template
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Poetry configuration
└── README.md                 # This file
```

---

## 🔐 AWS Permissions Required

The application requires the following AWS permissions:

**Cost Monitoring:**
- `ce:GetCostAndUsage`
- `ce:GetCostForecast`
- `ce:GetDimensionValues`
- `ce:GetTags`

**Logging:**
- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`

**Bedrock (Phase 3+):**
- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`

---

## 🧪 Testing Phase 0

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/health/db

# Readiness check
curl http://localhost:8000/health/ready
```

### Cost API Tests

```bash
# Get cost summary
curl http://localhost:8000/costs/summary | python -m json.tool

# Check budget alerts
curl http://localhost:8000/costs/alerts | python -m json.tool
```

### Emergency Shutdown Test

```bash
# Dry-run to see what would happen
python scripts/emergency_shutdown.py --dry-run
```

---

## 📊 Phase 1: Core Infrastructure + Basic Scraping

**Status:** ✅ Complete

**Goal:** Deploy core infrastructure and implement threat intelligence scraping.

### What's Included

1. **Terraform Infrastructure** (`terraform/phase1.tf`)
   - VPC with public subnets (no NAT Gateway for cost savings)
   - RDS PostgreSQL 16 (db.t4g.micro ARM-based)
   - S3 buckets for content and ML models
   - Security groups for RDS and application

2. **Scraper Services** (`src/cti_scraper/services/`)
   - `rss_parser.py`: RSS/Atom feed parsing with feedparser
   - `web_scraper.py`: Web scraping with BeautifulSoup for sites without RSS
   - `scraper_orchestrator.py`: Coordinates all scraping operations
   - `hunt_scorer.py`: Threat hunting scoring algorithm

3. **Source Configuration** (`src/cti_scraper/config/sources.py`)
   - 28 pre-configured threat intelligence sources
   - Microsoft, CrowdStrike, Mandiant, CISA, and more
   - Configurable check frequencies

4. **Scraper API** (`/scraper/*`)
   - `GET /scraper/sources` - List configured sources
   - `GET /scraper/sources/stats` - Database statistics
   - `POST /scraper/scrape/all` - Trigger full scrape (background)
   - `POST /scraper/scrape/{identifier}` - Scrape single source
   - `GET /scraper/articles` - List articles with filtering
   - `GET /scraper/articles/{id}` - Get article details
   - `GET /scraper/stats/summary` - Overall statistics

5. **Database Migrations** (`alembic/`)
   - Alembic configured for schema management
   - Initial migration for Phase 1 tables

### Expected Cost

**Phase 1 Monthly Cost:** ~$16-20
- RDS db.t4g.micro: ~$13/month
- S3 storage: ~$1/month
- Data transfer: ~$2/month

### Deploying Phase 1 Infrastructure

```bash
cd terraform

# Initialize if not already done
terraform init

# Preview Phase 1 resources
terraform plan

# Deploy (creates VPC, RDS, S3)
terraform apply
```

### Running Database Migrations

```bash
# Run migrations
alembic upgrade head

# Create new migration (after model changes)
alembic revision --autogenerate -m "description"
```

### Testing the Scraper (Local)

```bash
# List all sources
curl http://localhost:8000/scraper/sources

# Scrape a single source
curl -X POST http://localhost:8000/scraper/scrape/microsoft-security-blog

# Get scraper statistics
curl http://localhost:8000/scraper/stats/summary

# List recent articles
curl "http://localhost:8000/scraper/articles?limit=10&min_hunt_score=50"
```

### Lambda Deployment (Production Scraping)

The scraper runs on AWS Lambda with EventBridge scheduling (hourly). **All AWS resources are managed via Terraform.**

**Estimated Cost:** ~$0-2/month (within free tier)

**Deployment (Terraform-only):**

```bash
# 1. Build Lambda package locally
python scripts/build_lambda.py

# 2. Deploy everything via Terraform
cd terraform
terraform apply
```

Terraform will:
- Create S3 bucket for Lambda deployments
- Upload `lambda_package.zip` to S3
- Create Lambda function from S3
- Set up EventBridge hourly schedule
- Configure IAM roles and VPC access

**Updating Lambda Code:**

```bash
# 1. Rebuild package
python scripts/build_lambda.py

# 2. Apply changes (Terraform detects zip file change)
cd terraform
terraform apply
```

**Manual Lambda Invocation (for testing):**

```bash
# Scrape all sources
aws lambda invoke --function-name cti-scraper-dev-scraper \
    --payload '{"action": "scrape_all"}' \
    --cli-binary-format raw-in-base64-out \
    response.json

# Scrape specific source
aws lambda invoke --function-name cti-scraper-dev-scraper \
    --payload '{"action": "scrape", "sources": ["microsoft-security-blog"]}' \
    --cli-binary-format raw-in-base64-out \
    response.json
```

**View Lambda Logs:**

```bash
aws logs tail /aws/lambda/cti-scraper-dev-scraper --follow
```

---

## 📋 Next Steps: Phase 2

**Phase 2: ML Pipeline**

Will implement:
- Article chunk classification
- ML model training pipeline
- Junk content filtering
- Annotation interface

**Estimated Additional Cost:** $5-10/month (training compute)

---

## 📝 Configuration

### Environment Variables

Key environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/cti_scraper

# AWS
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Bedrock (Phase 3+)
BEDROCK_DAILY_BUDGET=1.50
BEDROCK_MONTHLY_BUDGET=45.00

# Cost Alerts
COST_ALERT_EMAIL=your-email@example.com
COST_ALERT_THRESHOLD_95=95.00
```

---

## 🐛 Troubleshooting

### Cost Dashboard Shows Zero

**Cause:** AWS Cost Explorer data has 24-hour delay

**Solution:** Wait 24 hours after first AWS usage, or use CloudWatch Billing metrics

### Terraform Apply Fails

**Cause:** Missing AWS credentials or permissions

**Solution:**
```bash
aws configure
aws sts get-caller-identity  # Verify credentials
```

### Emergency Shutdown Fails

**Cause:** Resources may not exist yet (Phase 0 only)

**Solution:** This is expected in Phase 0. Script will work once Phase 1+ resources are deployed.

---

## 📚 Documentation

- [AWS Cost Explorer API](https://docs.aws.amazon.com/cost-management/latest/APIReference/)
- [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

---

## 📞 Support

For issues or questions:
1. Check AWS CloudWatch logs
2. Review cost dashboard alerts
3. Verify environment variables in `.env`

---

## ⚖️ License

Proprietary - Internal Use Only

---

## 🎯 Phase Roadmap

- [x] **Phase 0:** Cost Monitoring Foundation
- [x] **Phase 1:** Core Infrastructure + Basic Scraping (Current)
- [ ] **Phase 2:** ML Pipeline
- [ ] **Phase 3:** Bedrock Integration (Controlled)
- [ ] **Phase 4:** Automation (Lambda + EventBridge)
- [ ] **Phase 5:** Embeddings + SIGMA
- [ ] **Phase 6:** Production Optimization

**Each phase requires cost gate approval before proceeding.**
