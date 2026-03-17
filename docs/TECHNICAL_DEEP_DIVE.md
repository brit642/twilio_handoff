# Twilio Warm Handoff Project - Technical Deep Dive

## Executive Summary

We built a **text-based warm handoff system** that enables CX Agent Studio virtual agents to transfer conversations to human agents while preserving full conversation context. The solution is deployed on Google Cloud Run and integrates with CX Agent Studio via OpenAPI toolsets.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            USER JOURNEY                                  │
└─────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐         ┌─────────────────────┐         ┌──────────────┐
     │          │  Chat   │                     │  Tool   │              │
     │   User   │────────▶│  CX Agent Studio    │────────▶│ Cloud Run    │
     │          │         │  (Virtual Agent)    │  Call   │ Backend      │
     └──────────┘         └─────────────────────┘         └──────┬───────┘
                                    │                            │
                                    │                            │ Webhook
                                    │                            │ (Production)
                                    ▼                            ▼
                          ┌─────────────────────┐       ┌──────────────────┐
                          │  Agent continues    │       │  Human Agent     │
                          │  conversation until │       │  System receives │
                          │  handoff triggered  │       │  full context    │
                          └─────────────────────┘       └──────────────────┘
```

---

## Components Built

### 1. Flask Backend (`flask_app/main.py`)

**Purpose:** Receives handoff requests from CX Agent Studio and notifies human agent systems.

**Key Design Decisions:**

```python
# Demo Mode Toggle - Critical for testing without external dependencies
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

# Environment-based configuration - No hardcoded secrets
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
HUMAN_AGENT_WEBHOOK = os.environ.get("HUMAN_AGENT_WEBHOOK")
```

**Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check - Returns service status and demo mode flag |
| `/start_transfer` | POST | Main entry - Receives context, notifies human agent |
| `/handoff_status` | POST | Callback - Human agent system reports completion |

**Request Flow for `/start_transfer`:**

```
1. Receive JSON payload with:
   - session_id (required)
   - user_id, transcript, issue_summary, channel_id (optional)

2. Validate required fields

3. Build handoff context object:
   {
     "handoff_id": "handoff_{session_id}_{timestamp}",
     "session_id": "...",
     "user_id": "...",
     "transcript": "User: Hi\nAgent: Hello...",
     "issue_summary": "User needs password reset help",
     "timestamp": "2026-03-17T12:55:26",
     "source": "cx_agent_studio"
   }

4. If DEMO_MODE:
   → Log full context to stdout (visible in Cloud Run logs)

   If PRODUCTION:
   → POST context to HUMAN_AGENT_WEBHOOK
   → Handle timeouts and errors gracefully
```

### 2. OpenAPI Specification (`flask_app/openapi.yaml`)

**Purpose:** Defines the API contract that CX Agent Studio uses to call our backend.

**Key Sections:**

```yaml
openapi: 3.0.0
info:
  title: Twilio Warm Handoff API
  version: 2.0.0

servers:
  - url: https://twilio-warm-handoff-backend-689910341505.us-central1.run.app

paths:
  /start_transfer:
    post:
      operationId: initiateHumanHandoff  # This is what the agent calls
      requestBody:
        schema:
          properties:
            session_id:    # Required
            user_id:       # Optional
            issue_summary: # Optional - AI-generated
            transcript:    # Optional - Chat history
            channel_id:    # Optional - For routing
```

**Why OpenAPI?**
- CX Agent Studio natively supports OpenAPI toolsets
- Self-documenting API contract
- Automatic parameter validation
- Easy to version and update

### 3. CX Agent Studio Integration

**Toolset Creation:**
- Created "Human Handoff API" toolset via REST API
- Contains 3 operations: `healthCheck`, `initiateHumanHandoff`, `updateHandoffStatus`
- Assigned to root agent

**Agent Instructions (XML format):**

```xml
<taskflow>
  <subtask name="Human Handoff">
    <step name="Detect Handoff Need">
      <trigger>
        User requests human agent OR issue is complex OR user is frustrated
      </trigger>
      <action>
        Acknowledge and prepare to transfer
      </action>
    </step>
    <step name="Execute Transfer">
      <action>
        Call initiateHumanHandoff with session_id, issue_summary, transcript
        Say: "I've connected you with our support team."
      </action>
    </step>
  </subtask>
</taskflow>
```

### 4. Deployment (Cloud Run)

**Configuration:**

```bash
gcloud run deploy twilio-warm-handoff-backend \
  --source flask_app/ \
  --region us-central1 \
  --allow-unauthenticated \      # For demo - add auth in production
  --set-env-vars "DEMO_MODE=true"
```

**Why Cloud Run?**
- Serverless - scales to zero when not in use
- Auto-scaling for traffic spikes
- Built-in HTTPS
- Easy environment variable management
- Integrated logging with Cloud Logging

---

## What Makes It "Warm"

The key differentiator from a "cold" transfer:

| Cold Transfer | Warm Transfer (Our Solution) |
|---------------|------------------------------|
| User transferred, context lost | Full context preserved |
| Human asks "How can I help?" | Human already knows the issue |
| User repeats everything | Seamless continuation |
| Frustrating experience | Professional experience |

**Context Passed to Human Agent:**

```json
{
  "handoff_id": "handoff_session123_20260317125526",
  "session_id": "session123",
  "user_id": "user456",
  "issue_summary": "User cannot reset password - reset email not received",
  "transcript": "User: Hi, I need help\nAgent: Hello! How can I assist?\nUser: I forgot my password\nAgent: Let me transfer you to a specialist.",
  "timestamp": "2026-03-17T12:55:26.291Z",
  "source": "cx_agent_studio"
}
```

---

## Challenges Faced & Solutions

### Challenge 1: CX Agent Studio API Access

**Problem:** The CXAS SCRAPI library wasn't available via pip, and the CES SDK had complex dependencies.

**What We Tried:**
1. Installing via pip → Package not found
2. Installing from GCS → Dependency chain (pyyaml, pandas, sentence-transformers)
3. Using the SDK directly → Regional endpoint confusion

**Solution:** Used the REST API directly with `curl` and `gcloud auth print-access-token`:

```bash
curl -X POST "https://ces.googleapis.com/v1beta/${APP_ID}/toolsets" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -d '{"displayName": "Human Handoff API", "openApiToolset": {"openApiSchema": "..."}}'
```

**Lesson:** When SDKs are complex or unavailable, REST APIs with proper auth often work better.

---

### Challenge 2: OpenAPI Tool vs Toolset

**Problem:** Initial attempt to create an "OpenApiTool" failed with error:

```
Creating tools of type OpenApiTool is not supported.
Please use OpenApi Toolsets instead.
```

**Solution:** CX Agent Studio requires **toolsets** (collections of operations), not individual tools. Changed from:

```json
// Wrong
{"displayName": "...", "openApiTool": {"url": "..."}}

// Correct
{"displayName": "...", "openApiToolset": {"openApiSchema": "..."}}
```

---

### Challenge 3: OpenAPI Schema Inline vs URL

**Problem:** Tried to reference the OpenAPI spec by URL, but:
1. Flask doesn't serve static YAML files by default
2. API error: "OpenAPI toolset must have an OpenAPI schema"

**Solution:** Embedded the full OpenAPI schema inline in the API request:

```python
with open('openapi.yaml', 'r') as f:
    spec = f.read()

payload = {
    "displayName": "Human Handoff API",
    "openApiToolset": {
        "openApiSchema": spec  # Full YAML content, not URL
    }
}
```

---

### Challenge 4: Agent Update Limitations

**Problem:** Tried to update agent instructions and toolsets via API:

```bash
curl -X PATCH ".../agents/{id}?updateMask=instructions,toolsets"
# Error: "Invalid update mask"
```

**Solution:** Agent configuration (assigning toolsets, updating instructions) must be done via the CX Agent Studio UI. The API supports creating resources but has limited update capabilities.

**Workaround:** Created the toolset via API, then assigned it via UI.

---

### Challenge 5: Session API Not Externally Accessible

**Problem:** Wanted to test conversations programmatically:

```bash
curl -X POST ".../sessions/{id}:run"
# Error: 404 Not Found
```

**Solution:** The Sessions API is internal/restricted. Testing must be done via:
- CX Agent Studio Simulator (UI)
- SCRAPI library (in Colab/authenticated environment)

We verified the integration by testing in the simulator and monitoring Cloud Run logs.

---

## Testing Strategy

### 1. Local Testing (Demo Mode)

```bash
DEMO_MODE=true PORT=8090 python main.py

curl -X POST http://localhost:8090/start_transfer \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-123", "issue_summary": "Test issue"}'
```

### 2. Cloud Run Verification

```bash
# Health check
curl https://SERVICE_URL/

# Handoff test
curl -X POST https://SERVICE_URL/start_transfer \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "issue_summary": "Test"}'

# Check logs
gcloud run services logs read twilio-warm-handoff-backend --region us-central1
```

### 3. End-to-End Test

1. Open CX Agent Studio Simulator
2. Type: "I want to talk to a human"
3. Agent calls `initiateHumanHandoff`
4. Cloud Run logs show full context:

```
============================================================
DEMO MODE - Warm Handoff Initiated
============================================================
Handoff ID: handoff_test-session-id_20260317125526
Session ID: test-session-id
Issue Summary: User wants to talk to a human.
Transcript:
  User: I want to talk to a human
============================================================
```

---

## Production Considerations

### Security
- Add API key authentication to endpoints
- Use Google Secret Manager for credentials
- Enable Cloud Run authentication (remove `--allow-unauthenticated`)

### Monitoring
- Set up Cloud Monitoring alerts for errors
- Track handoff success/failure rates
- Monitor latency percentiles

### Scaling
- Cloud Run auto-scales (configure min/max instances)
- Consider regional deployment for latency
- Add retry logic for webhook failures

---

## Files Delivered

```
twilio_handoff/
├── flask_app/
│   ├── main.py              # 190 lines - Core backend logic
│   ├── openapi.yaml         # 180 lines - API specification
│   ├── requirements.txt     # Dependencies
│   └── Dockerfile           # Container config
├── agent_studio/
│   ├── agent_instructions.xml   # XML format for CX Agent Studio
│   ├── agent_instructions.md    # Markdown reference
│   └── tool_config.yaml         # Toolset configuration guide
├── docs/
│   ├── VOICE_HANDOFF_ARCHITECTURE.md  # Future voice implementation
│   ├── CXAS_SCRAPI_GUIDE.md           # SCRAPI library guide
│   └── TECHNICAL_DEEP_DIVE.md         # This document
├── README.md                # Comprehensive usage guide
└── SETUP_GUIDE.md           # Step-by-step deployment
```

---

## Key Talking Points for Customer Call

1. **Google Cloud Native:** Runs on Cloud Run, integrates with CX Agent Studio natively

2. **Demo Ready:** Works in demo mode without any external dependencies

3. **Production Path Clear:** Just set environment variables for Twilio/webhook

4. **Extensible:** Voice architecture documented for future phases

5. **Well Documented:** README, setup guide, and SCRAPI guide included

6. **Tested End-to-End:** Verified from simulator to Cloud Run logs

---

## Questions to Anticipate

**Q: Why not use Twilio directly for text?**

A: This architecture focuses on CX Agent Studio as the conversation layer. Twilio is optional for production webhook notifications. The demo works without Twilio.

---

**Q: How does the human agent receive the context?**

A: Via webhook POST to their system (configurable via `HUMAN_AGENT_WEBHOOK`). They would build a dashboard/screen pop to display it.

---

**Q: Can this work with voice?**

A: Yes, we documented the voice architecture in `docs/VOICE_HANDOFF_ARCHITECTURE.md`. It requires Twilio Conferences and is more complex but follows similar patterns.

---

**Q: What about authentication?**

A: Demo mode has no auth. For production, add API keys or OAuth, plus Cloud Run IAM authentication.

---

**Q: How long did this take to build?**

A: The core implementation (backend + OpenAPI + integration) was completed in a single session. The majority of time was spent on:
- Debugging CX Agent Studio API quirks
- Testing end-to-end flow
- Creating comprehensive documentation

---

**Q: What are the costs?**

A: Minimal for demo/low traffic:
- Cloud Run: Pay per request (free tier: 2M requests/month)
- No Twilio costs in demo mode
- Production: Twilio messaging rates apply if using their APIs

---

## Appendix: API Quick Reference

### Health Check
```bash
curl https://twilio-warm-handoff-backend-689910341505.us-central1.run.app/
```

### Initiate Handoff
```bash
curl -X POST https://twilio-warm-handoff-backend-689910341505.us-central1.run.app/start_transfer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-123",
    "user_id": "user-456",
    "issue_summary": "User needs help with billing",
    "transcript": "User: Hi\nAgent: Hello, how can I help?"
  }'
```

### Update Handoff Status
```bash
curl -X POST https://twilio-warm-handoff-backend-689910341505.us-central1.run.app/handoff_status \
  -H "Content-Type: application/json" \
  -d '{
    "handoff_id": "handoff_session-123_20260317125526",
    "status": "completed",
    "agent_id": "agent-jane",
    "notes": "Issue resolved"
  }'
```
