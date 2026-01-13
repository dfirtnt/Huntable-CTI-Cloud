# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CTI Scraper** - A cost-optimized AWS-based platform for collecting, analyzing, and processing threat intelligence content. The project aggregates threat intelligence from 28+ sources, uses ML to filter junk content, and employs AWS Bedrock (LLM) to generate SIGMA detection rules from threat articles.

**Critical Constraint**: $100/month AWS budget maximum with strict cost monitoring and emergency shutdown capabilities.

**Current Phase**: Phase 1 (Core Infrastructure + Basic Scraping) - Complete

## Development Commands

### Local Development

```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Start local API server
cd src
uvicorn cti_scraper.api.app:app --reload --host 0.0.0.0 --port 8000

# Access points
# - API Docs: http://localhost:8000/docs
# - Cost Dashboard: http://localhost:8000/costs/dashboard
# - Health Check: http://localhost:8000/health
```

### Database Operations

```bash
# Run database migrations
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Downgrade one revision
alembic downgrade -1

# Check current migration version
alembic current
```

### Testing Scraper

```bash
# List all configured sources
curl http://localhost:8000/scraper/sources

# Scrape a specific source
curl -X POST http://localhost:8000/scraper/scrape/microsoft-security-blog

# Scrape all sources (background task)
curl -X POST http://localhost:8000/scraper/scrape/all

# View scraper statistics
curl http://localhost:8000/scraper/stats/summary

# List recent articles
curl "http://localhost:8000/scraper/articles?limit=10&min_hunt_score=50"
```

### Terraform Operations

```bash
cd terraform

# Initialize (first time)
terraform init

# Preview changes
terraform plan

# Deploy infrastructure
terraform apply

# View outputs
terraform output

# Destroy infrastructure (CAUTION!)
terraform destroy
```

### Lambda Deployment

```bash
# Build Lambda package
python scripts/build_lambda.py

# Deploy via Terraform (uploads to S3 and updates Lambda)
cd terraform
terraform apply

# View Lambda logs
aws logs tail /aws/lambda/cti-scraper-dev-scraper --follow

# Manual Lambda invocation (testing)
aws lambda invoke --function-name cti-scraper-dev-scraper \
    --payload '{"action": "scrape_all"}' \
    --cli-binary-format raw-in-base64-out \
    response.json
```

### Cost Monitoring

```bash
# Check current costs
curl http://localhost:8000/costs/summary | python -m json.tool

# Get MTD costs
curl http://localhost:8000/costs/mtd

# Check budget alerts
curl http://localhost:8000/costs/alerts
```

### Emergency Procedures

```bash
# Emergency shutdown (if costs approach $95)
python scripts/emergency_shutdown.py

# Dry-run first (recommended)
python scripts/emergency_shutdown.py --dry-run

# Restart after shutdown
python scripts/restart_system.py
```

## Architecture

### Core Application Structure

```
src/cti_scraper/
├── api/                    # FastAPI application
│   ├── app.py             # Application factory with lifespan management
│   └── routes/            # API route modules
│       ├── cost.py        # Cost monitoring endpoints
│       ├── health.py      # Health checks
│       ├── scraper.py     # Scraper control endpoints
│       ├── articles.py    # Article management
│       └── ml.py          # ML operations
├── config/
│   ├── settings.py        # Pydantic settings with env vars
│   └── sources.py         # 28 hardcoded threat intel sources
├── db/
│   ├── base.py            # SQLAlchemy async setup
│   └── models.py          # All database models (13 tables)
├── services/              # Business logic layer
│   ├── cost_monitor.py    # AWS Cost Explorer integration
│   ├── rss_parser.py      # RSS/Atom feed parsing
│   ├── web_scraper.py     # BeautifulSoup web scraping
│   ├── scraper_orchestrator.py  # Coordinates all scraping
│   ├── hunt_scorer.py     # Threat hunting scoring algorithm
│   ├── content_chunker.py # Text chunking for ML
│   └── ml_classifier.py   # ML model inference
├── lambda_handler.py      # Lambda function for scraping
├── lambda_api.py          # Lambda function for API (Mangum)
└── lambda_ml_trainer.py   # Lambda function for ML training
```

### Database Schema (PostgreSQL + pgvector)

**Phase 1 Tables** (Active):
- `sources` - Source configuration and health metrics
- `articles` - Article content with embeddings and hunt scores
- `source_checks` - Scraping history and performance
- `article_annotations` - User annotations for ML training
- `content_hashes` - Deduplication tracking

**Phase 2 Tables** (Ready for ML):
- `chunk_analysis_results` - ML predictions per chunk
- `chunk_classification_feedback` - User feedback on predictions
- `ml_model_versions` - Model versioning and metrics
- `ml_prediction_logs` - Inference tracking

**Phase 3+ Tables** (Ready for Agentic Workflow):
- `agentic_workflow_config` - Workflow configuration
- `agentic_workflow_executions` - Execution tracking
- `sigma_rules` - Generated SIGMA detection rules
- `article_sigma_matches` - Article-to-rule relationships
- `sigma_rule_queue` - Human review queue

### Threat Hunting Score Algorithm

The `HuntScorer` service implements a sophisticated scoring system with geometric series scoring (ensures scores approach but never reach 100):

**Scoring Categories**:
1. **Perfect Discriminators** (75 points max): Windows malware indicators, cmd.exe obfuscation patterns, PowerShell attacks, macOS indicators
2. **LOLBAS Executables** (10 points max): 200+ living-off-the-land binaries
3. **Intelligence Indicators** (10 points max): APT groups, attack lifecycle phases, incident indicators
4. **Good Discriminators** (5 points max): Supporting technical content
5. **Negative Indicators** (-10 points penalty): Educational/marketing content

**Formula**: `score = max_points * (1.0 - (0.5 ** num_matches))`

### Scraper Orchestrator Flow

1. Loads active sources from `sources.py` (28 pre-configured)
2. Separates RSS sources (faster) from web scraping sources
3. For each source:
   - Checks if scrape is due based on `check_frequency`
   - Parses RSS feed or scrapes web page
   - Calculates hunt score for each article
   - Deduplicates by content hash (SHA256)
   - Stores in database with metadata
   - Records check history in `source_checks`
4. Updates source health metrics

### Cost Monitoring System

- Queries AWS Cost Explorer API for MTD costs
- Tracks Bedrock-specific costs separately
- CloudWatch alarms at 25%, 50%, 80%, 95% thresholds
- Emergency shutdown disables EventBridge, stops ECS/RDS
- Real-time cost dashboard with dark mode UI

### AWS Infrastructure (Terraform Modules)

```
terraform/
├── main.tf           # Root module configuration
├── iam.tf            # IAM roles and policies
├── monitoring.tf     # CloudWatch, SNS, Budgets
├── phase1.tf         # RDS, S3, VPC for Phase 1
├── phase2.tf         # ML training resources
└── modules/
    ├── vpc/          # VPC with public subnets (no NAT)
    ├── rds/          # PostgreSQL 16 (db.t4g.micro ARM)
    ├── s3/           # Content and model storage
    ├── lambda/       # Lambda functions
    ├── ecs/          # ECS for future API hosting
    └── monitoring/   # Cost alarms and dashboards
```

**Key Design Decision**: Public subnets without NAT Gateway to save $32/month. Lambda and RDS use public IPs with security groups.

## Configuration

### Environment Variables (.env)

Critical settings loaded via Pydantic:
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/cti_scraper
DATABASE_URL_SYNC=postgresql://user:pass@host:5432/cti_scraper  # For Alembic

# AWS
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Bedrock (Phase 3+)
BEDROCK_DAILY_BUDGET=1.50
BEDROCK_MONTHLY_BUDGET=45.00

# Cost Alerts
COST_ALERT_EMAIL=your-email@example.com
COST_ALERT_THRESHOLD_95=95.00

# ML Models
ML_MODEL_BUCKET=cti-scraper-models
CONTENT_FILTER_THRESHOLD=0.7
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Workflow (Phase 3+)
WORKFLOW_MIN_HUNT_SCORE=70
WORKFLOW_ENABLED=false
```

### Threat Intelligence Sources

28 sources configured in `src/cti_scraper/config/sources.py`:
- RSS feeds preferred (faster, more reliable)
- Fallback to web scraping for sites without RSS
- Check frequencies: 30min to 2hr based on source update patterns
- Examples: Microsoft Security Blog, CISA Alerts, CrowdStrike, Mandiant, Unit 42

**Adding New Sources**: Edit `THREAT_INTEL_SOURCES` list in `sources.py` with:
- `identifier`: Unique slug (e.g., "new-blog-source")
- `name`: Display name
- `url`: Homepage URL
- `rss_url`: RSS feed URL (or None for web scraping)
- `check_frequency`: Seconds between checks
- `active`: Boolean to enable/disable

## Development Guidelines

### Infrastructure as Code (CRITICAL)

**All AWS compute and infrastructure changes MUST be managed through Terraform.**

- **Never** create AWS resources manually via Console or CLI
- **Never** use `aws lambda update-function-code` directly
- **Never** modify security groups, IAM roles, or RDS settings outside Terraform
- **Always** make infrastructure changes in Terraform files
- **Always** run `terraform plan` before `terraform apply` to review changes

**Deployment workflow**:
1. Update Terraform configuration files
2. Build Lambda packages if needed: `python scripts/build_lambda.py`
3. Review changes: `terraform plan`
4. Apply changes: `terraform apply`

This ensures:
- Infrastructure is version controlled
- Changes are reviewable and reversible
- State is consistent across environments
- No configuration drift

### Adding New API Endpoints

1. Create route function in appropriate file in `api/routes/`
2. Register router in `api/app.py`
3. Use dependency injection for database sessions
4. Return Pydantic models for type safety
5. Add error handling with appropriate HTTP status codes

Example:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from cti_scraper.db import get_db_session

router = APIRouter()

@router.get("/example")
async def example_endpoint(db: AsyncSession = Depends(get_db_session)):
    # Implementation
    return {"status": "success"}
```

### Database Model Changes

1. Update models in `src/cti_scraper/db/models.py`
2. Create migration: `alembic revision --autogenerate -m "description"`
3. Review generated migration in `alembic/versions/`
4. Test migration: `alembic upgrade head`
5. Update relevant services to use new fields

**Important**: Always review autogenerated migrations before applying. Alembic may not detect all schema changes correctly.

### Adding New Services

1. Create service file in `src/cti_scraper/services/`
2. Use async/await for all I/O operations
3. Accept database session as constructor parameter
4. Add comprehensive logging with logger = logging.getLogger(__name__)
5. Raise descriptive exceptions for error cases

### Cost Optimization Principles

- **Always** check projected costs before deploying new resources
- Use ARM-based instances (t4g) over x86 (t3) for 20% savings
- Avoid NAT Gateways ($32/month each)
- Use S3 lifecycle policies to transition old data to cheaper tiers
- Monitor Bedrock token usage closely (most expensive component)
- Implement request caching where possible
- Use smaller models (Claude Haiku) for simple tasks

### Lambda Development

- Package dependencies in `requirements-lambda.txt` (stripped down)
- Build with `scripts/build_lambda.py` (creates zip)
- Deploy via Terraform (uploads to S3, updates function)
- Lambda timeout: 5 minutes for scraper, 15 minutes for ML training
- Memory: 512MB for scraper, 2GB for ML training
- Environment variables set via Terraform

## Testing

### Manual Testing Workflow

1. Start local server: `uvicorn cti_scraper.api.app:app --reload`
2. Test health: `curl http://localhost:8000/health`
3. Verify DB connection: `curl http://localhost:8000/health/db`
4. Test scraper: `curl -X POST http://localhost:8000/scraper/scrape/microsoft-security-blog`
5. Check results: `curl http://localhost:8000/scraper/articles?limit=5`
6. Verify hunt scores in response metadata

### Pre-Deployment Checklist

- [ ] Terraform plan reviewed (no unexpected changes)
- [ ] Environment variables updated in `.env` and Terraform
- [ ] Database migrations tested locally
- [ ] Cost projections within budget
- [ ] CloudWatch alarms configured
- [ ] SNS subscription confirmed (check email)
- [ ] Lambda package built and tested
- [ ] Emergency shutdown script tested (dry-run)

## Phase Roadmap & Budget

- **Phase 0**: Cost Monitoring (~$1-2/month) ✅ Complete
- **Phase 1**: Core Infrastructure + Scraping (~$16-20/month) ✅ Complete
  - RDS db.t4g.micro: $13/month
  - S3 + data transfer: $3/month
  - Lambda: $0-2/month (within free tier)
- **Phase 2**: ML Pipeline (~$5-10/month)
  - Training compute on Lambda
  - Model storage in S3
- **Phase 3**: Bedrock Integration (~$45/month)
  - Controlled daily budget: $1.50/day
  - LangGraph workflow
  - SIGMA rule generation
- **Phase 4+**: Production optimization

**Total Projected**: ~$70-80/month (well under $100 budget)

## Common Issues & Solutions

### Cost Dashboard Shows Zero

AWS Cost Explorer has 24-hour data delay. Wait 24 hours after first usage, or use CloudWatch Billing metrics for real-time data.

### Terraform Apply Fails

```bash
# Verify AWS credentials
aws configure
aws sts get-caller-identity

# Check region matches .env
echo $AWS_REGION
```

### Lambda Import Errors

Ensure `requirements-lambda.txt` includes all dependencies. Rebuild package:
```bash
python scripts/build_lambda.py
cd terraform && terraform apply
```

### Database Connection Errors

- Verify RDS security group allows inbound from your IP (or Lambda VPC)
- Check DATABASE_URL format: `postgresql+asyncpg://` for async, `postgresql://` for sync (Alembic)
- Ensure RDS instance is running (check AWS console)

### Alembic Migration Conflicts

```bash
# Show current version
alembic current

# Show migration history
alembic history

# If stuck, manually set version (use with caution)
alembic stamp head
```

## Key Files Reference

- `README.md` - Comprehensive project documentation
- `QUICK_REFERENCE.md` - Quick command reference
- `FUNCTIONAL_REQUIREMENTS.md` - Feature specifications from original implementation
- `DEPLOYMENT_CHECKLIST.md` - Pre-deployment verification steps
- `.env.example` - Template for environment variables
- `pyproject.toml` - Poetry dependency specification
- `requirements.txt` - Pip-compatible dependency list
- `alembic.ini` - Database migration configuration

## Important Notes

- **Never** commit `.env` file (contains AWS credentials)
- **Always** use dry-run for emergency shutdown before executing
- **Monitor** costs daily via dashboard during active development
- **Test** migrations on local database before production
- **Review** Terraform plan output before applying
- **Keep** hunt score algorithm consistent with `FUNCTIONAL_REQUIREMENTS.md`
- **Document** any changes to source configuration in commit messages
