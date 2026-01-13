# CTI Scraper - Functional Requirements
## Based on Existing Implementation Analysis

This document outlines the functional features from the existing CTIScraper implementation that should be replicated in the new AWS Bedrock-based system.

## 1. Hunt Scoring System

### 1.1 Threat Hunting Content Scorer
**Source**: `src/utils/content.py` - `ThreatHuntingScorer` class

**Capabilities**:
- Multi-category keyword matching with weighted scoring
- Geometric series scoring (ensures scores approach but never reach 100)
- Regex pattern matching for cmd.exe obfuscation techniques

**Scoring Categories**:
1. **Perfect Discriminators** (75 points max)
   - Windows malware indicators (rundll32.exe, powershell.exe, wmic.exe)
   - Cmd.exe obfuscation patterns (environment variable manipulation, caret obfuscation)
   - PowerShell attack techniques (invoke-mimikatz, hashdump, invoke-shellcode)
   - macOS-specific indicators (homebrew, chmod 777, tccd, spctl)
   - High-threat keywords (CN=, -ComObject, -EncodedCommand, icacls)

2. **LOLBAS Executables** (10 points max)
   - Living-off-the-land binaries and scripts
   - 200+ executables and DLLs tracked

3. **Intelligence Indicators** (10 points max)
   - APT groups (APT28, Lazarus, Carbanak)
   - Attack lifecycle phases (lateral movement, persistence, exfiltration)
   - Real incident indicators (ransomware, data breach, espionage)

4. **Good Discriminators** (5 points max)
   - Supporting technical content indicators
   - Detection and hunting keywords

5. **Negative Indicators** (-10 points penalty)
   - Educational content (what is, how to, tutorial)
   - Marketing content (free trial, contact us, sign up)

**Formula**: `score = max_points * (1.0 - (0.5 ** num_matches))`
- Ensures diminishing returns on additional matches
- Theoretical max is 100 but never reached in practice

### 1.2 Sigma Rule Huntability Scorer
**Source**: `src/services/sigma_huntability_scorer.py`

**Evaluates SIGMA rules across**:
- Command-line specificity
- TTP (Tactics, Techniques, Procedures) clarity
- Parent/child process correctness
- Telemetry feasibility
- False-positive risk
- Overfitting risk
- Generates 0-10 huntability score with detailed breakdown

## 2. Machine Learning Components

### 2.1 Content Filter
**Capabilities**:
- Binary/multiclass classification of article chunks
- Filters out non-technical content
- Model versioning and performance tracking
- Standardized evaluation framework

### 2.2 Model Evaluation System
**Source**: `src/services/model_evaluation.py`

**Features**:
- Standardized test sets with annotated chunks
- Metrics: accuracy, precision, recall, F1 score
- Comparison between model versions
- Tracks training metadata and configuration

**Database Schema**:
```python
class MLModelVersionTable:
    - version_id
    - model_name
    - training_date
    - performance_metrics (JSON)
    - evaluation_metrics (JSON)
    - configuration (JSON)
```

## 3. Agentic Workflow

### 3.1 Multi-Stage Processing Pipeline
**Source**: `src/services/agentic_workflow.py`

**Workflow Stages**:
1. **OS Detection**: Identify target operating system (Windows/macOS/Linux)
2. **Junk Filter**: Remove non-technical content
3. **Article Ranking**: Score article relevance
4. **Extraction Agent**: Extract threat behaviors and TTPs
5. **SIGMA Rule Generation**: Create detection rules
6. **Similarity Search**: Find similar existing rules
7. **Queue Promotion**: Determine if rule needs human review

**Architecture**:
- Built with LangGraph for state management
- Configurable agent models per stage
- QA-enabled workflow with retry mechanisms
- Dynamic threshold configuration
- Comprehensive execution tracking

### 3.2 Workflow Configuration
```python
class AgenticWorkflowConfig:
    - os_detection_model
    - junk_filter_model
    - ranking_model
    - extraction_model
    - sigma_generation_model
    - similarity_threshold
    - min_hunt_score
    - qa_enabled
```

### 3.3 Execution Tracking
```python
class AgenticWorkflowExecutionTable:
    - execution_id
    - article_id
    - workflow_version
    - stage_results (JSON)
    - start_time
    - end_time
    - status
    - error_message
```

## 4. Database Schema

### 4.1 Core Tables

**ArticleTable**:
- Basic metadata (title, URL, published_date)
- Content (summary, full_content)
- Scoring (threat_hunting_score, ml_score)
- Processing status
- Vector embedding (768-dimensional)
- Content hash for deduplication

**SigmaRuleTable**:
- Rule content (YAML)
- Metadata (title, description, level)
- Huntability score
- False positive assessment
- Vector embedding for similarity search
- Human review status

**ArticleSigmaMatchTable**:
- Links articles to generated SIGMA rules
- Match confidence score
- Extraction details

**ChunkAnalysisResultTable**:
- ML predictions per chunk
- Confidence scores
- Model version used

**AgenticWorkflowExecutionTable**:
- Tracks each workflow run
- Stage-by-stage results
- Error handling and retry information

### 4.2 Vector Search
- Uses pgvector extension
- 768-dimensional embeddings
- Cosine similarity for rule matching
- Enables duplicate detection and similar rule finding

## 5. Web Services & API

### 5.1 REST Endpoints

**Article Management**:
- GET /api/articles - List articles with filters
- GET /api/articles/{id} - Article details
- POST /api/articles/{id}/rescore - Trigger rescoring

**Workflow Operations**:
- POST /api/workflow/execute - Run workflow on article
- GET /api/workflow/status/{execution_id} - Check status
- GET /api/workflow/config - Get current configuration
- PUT /api/workflow/config - Update configuration

**SIGMA Rule Management**:
- GET /api/sigma/rules - List rules
- GET /api/sigma/rules/{id} - Rule details
- POST /api/sigma/rules/{id}/approve - Human approval
- GET /api/sigma/rules/similar/{id} - Find similar rules

**ML Operations**:
- POST /api/ml/predict - Run ML prediction
- GET /api/ml/models - List model versions
- GET /api/ml/evaluate - Model evaluation results

### 5.2 Web Dashboard Routes
- `/` - Main dashboard
- `/articles` - Article browser
- `/sigma` - SIGMA rule viewer
- `/workflow` - Workflow configuration
- `/analytics` - Performance metrics
- `/evaluation` - ML model evaluation

## 6. Content Processing Utilities

### 6.1 ContentCleaner
**Source**: `src/utils/content.py`

**Capabilities**:
- HTML to clean text conversion
- Remove navigation, ads, UI elements
- Extract main content area
- Normalize whitespace
- Clean non-printable characters
- Fix UTF-8 corruption

### 6.2 MetadataExtractor
**Extracts**:
- OpenGraph metadata
- Twitter Card metadata
- Canonical URLs
- Author information
- Publication dates
- Keywords and tags

## 7. Configuration Management

### 7.1 Source Configuration
**Source**: `src/config/sources.py`

**Per-Source Settings**:
- URL and RSS feed URL
- Check frequency (seconds)
- Active/inactive status
- Custom scrapers (if needed)
- Minimum content length
- Source-specific selectors

### 7.2 Workflow Configuration
**Stored in Database**:
- Agent model selections
- Threshold values
- Retry policies
- QA settings
- Cost limits

## 8. Implementation Priorities

### Phase 1 (Current - Basic Scraping)
- [x] Source configuration
- [x] RSS feed parser
- [x] Web scraper
- [ ] **Update Hunt Scorer** to match existing implementation
- [x] Basic database schema
- [ ] Article storage

### Phase 2 (ML Content Filter)
- [ ] Content chunking
- [ ] ML model training infrastructure
- [ ] Model evaluation framework
- [ ] Model versioning system

### Phase 3 (Bedrock Integration)
- [ ] AWS Bedrock integration
- [ ] Prompt engineering for extraction
- [ ] Cost monitoring and budgets
- [ ] LangGraph workflow setup

### Phase 4 (Agentic Workflow)
- [ ] Multi-stage workflow implementation
- [ ] SIGMA rule generation
- [ ] Vector similarity search
- [ ] Human review queue

### Phase 5 (Web Interface)
- [ ] FastAPI REST API
- [ ] Web dashboard
- [ ] Analytics and reporting

## 9. Key Design Patterns

### 9.1 Service Layer Architecture
- Clean separation of concerns
- Each service has single responsibility
- Services use dependency injection
- All services log extensively

### 9.2 Configuration-Driven
- Workflow stages configurable
- Agent models swappable
- Thresholds adjustable without code changes

### 9.3 Async-First
- All I/O operations use async/await
- Database operations async
- HTTP requests async
- Enables high concurrency

### 9.4 Comprehensive Logging
- Structured logging with context
- Trace IDs for request tracking
- Performance metrics logged
- Error tracking with full context

## 10. Cost Controls

### 10.1 Budget Enforcement
- Daily Bedrock spending limit
- Monthly total budget
- Automatic workflow suspension on limit
- Cost alerts at thresholds

### 10.2 Smart Caching
- Cache LLM responses
- Deduplicate similar articles
- Reuse embeddings when possible

### 10.3 Batch Processing
- Process multiple articles together
- Optimize API call patterns
- Use cheaper models where appropriate

---

## Next Steps

1. **Immediate**: Update hunt_scorer.py to match ThreatHuntingScorer implementation
2. **Phase 1 Completion**: Deploy infrastructure, test scraping
3. **Phase 2 Planning**: Design ML training pipeline
4. **Phase 3 Planning**: Design Bedrock integration architecture
