# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two main components:

1. **Twilio Warm Handoff Backend** (`flask_app/`) - A Flask service for text-based warm transfers from CX Agent Studio to human agents
2. **CXAS SCRAPI Skill** (`skills/cxas_scrapi/`) - Claude Code skill for interacting with CX Agent Studio API

## Flask App Commands

```bash
# Run locally (demo mode)
cd flask_app
pip install -r requirements.txt
DEMO_MODE=true python main.py

# Run locally (production mode with Twilio)
TWILIO_ACCOUNT_SID=xxx TWILIO_AUTH_TOKEN=xxx HUMAN_AGENT_WEBHOOK=https://... python main.py

# Deploy to Cloud Run
gcloud run deploy twilio-warm-handoff-backend \
  --source flask_app/ \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "DEMO_MODE=true"
```

## Architecture

### Text-Based Warm Handoff Flow

1. User chats with CX Agent Studio virtual agent
2. Virtual Agent detects need for human handoff (user request or agent logic)
3. Agent calls `/start_transfer` endpoint with conversation context
4. Backend notifies human agent system via webhook with full context
5. Human agent receives transcript + issue summary ("warm" context)
6. Human agent continues the text conversation with the user

**What makes it "warm":** The human agent receives the full conversation transcript and issue summary before taking over. They don't need to ask "How can I help you?" - they already know the context.

### Key Endpoints (flask_app/main.py)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check |
| `/start_transfer` | POST | Main entry point - notifies human agent with conversation context |
| `/handoff_status` | POST | Callback for handoff completion status |

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DEMO_MODE` | Set to "true" to log instead of calling external services | No |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | Yes (production) |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | Yes (production) |
| `HUMAN_AGENT_WEBHOOK` | Webhook URL to notify human agent system | Yes (production) |
| `PORT` | Server port (default: 8080) | No |

### CX Agent Studio Integration

The `agent_studio/` directory contains configuration files for integrating with CX Agent Studio:
- `tool_config.yaml` - OpenAPI tool definition for `initiate_human_handoff`
- `agent_instructions.md` - Sample agent instructions for triggering warm handoff

### CXAS SCRAPI Skill

The skill in `skills/cxas_scrapi/` documents how to use the `cxas_scrapi` library for:
- CRUD operations on Apps, Agents, Tools
- Session-based conversational testing
- Running and parsing evaluations to pandas DataFrames
- Extracting latency metrics (p50/p90/p99) from evals or conversation history
- Tool unit testing with YAML-defined test cases

## Key Files

| File | Description |
|------|-------------|
| `flask_app/main.py` | Flask backend with handoff endpoints |
| `flask_app/openapi.yaml` | OpenAPI spec for CX Agent Studio tools |
| `flask_app/requirements.txt` | Python dependencies |
| `agent_studio/tool_config.yaml` | CX Agent Studio tool configuration |
| `agent_studio/agent_instructions.md` | Agent instruction templates |
| `SETUP_GUIDE.md` | Step-by-step deployment guide |
| `skills/cxas_scrapi/SKILL.md` | Skill definition for Claude Code |
| `CXAS_SCRAPI.ipynb` | Interactive Colab notebook for CXAS SCRAPI |

## Testing

```bash
# Test health endpoint
curl https://SERVICE_URL/

# Test handoff endpoint (demo mode)
curl -X POST https://SERVICE_URL/start_transfer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-123",
    "issue_summary": "User needs password reset help",
    "transcript": "User: I forgot my password\nAgent: Let me help."
  }'
```
