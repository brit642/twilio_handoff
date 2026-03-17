# Twilio Warm Handoff Setup Guide

This guide walks you through deploying and configuring the Twilio Warm Handoff system for CX Agent Studio.

## Overview

This solution enables warm transfers from CX Agent Studio virtual agents to human agents. "Warm" means the human agent receives the full conversation context (transcript, issue summary) before taking over.

**Architecture:**
```
User <-> CX Agent Studio <-> Flask Backend <-> Human Agent System
                                    |
                              (Twilio API)
```

## Prerequisites

- [ ] Google Cloud Project with billing enabled
- [ ] `gcloud` CLI installed and authenticated
- [ ] Twilio account with API credentials (optional for demo mode)
- [ ] CX Agent Studio access

## Step 1: Deploy Flask Backend to Cloud Run

### Option A: Quick Deploy (Demo Mode)

Deploy without Twilio credentials to test the flow:

```bash
cd flask_app

# Deploy to Cloud Run
gcloud run deploy twilio-warm-handoff-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "DEMO_MODE=true"
```

### Option B: Production Deploy

Deploy with full Twilio integration:

```bash
cd flask_app

# Set your credentials
export TWILIO_ACCOUNT_SID="your_account_sid"
export TWILIO_AUTH_TOKEN="your_auth_token"
export HUMAN_AGENT_WEBHOOK="https://your-agent-system.com/webhook"

# Deploy to Cloud Run
gcloud run deploy twilio-warm-handoff-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID" \
  --set-env-vars "TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN" \
  --set-env-vars "HUMAN_AGENT_WEBHOOK=$HUMAN_AGENT_WEBHOOK"
```

### Verify Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe twilio-warm-handoff-backend \
  --region us-central1 --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/

# Expected response:
# {"status":"healthy","service":"twilio-warm-handoff","demo_mode":true,...}
```

## Step 2: Configure Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DEMO_MODE` | Set to "true" to log instead of calling external services | No |
| `TWILIO_ACCOUNT_SID` | Your Twilio Account SID | Yes (production) |
| `TWILIO_AUTH_TOKEN` | Your Twilio Auth Token | Yes (production) |
| `HUMAN_AGENT_WEBHOOK` | URL to notify when handoff is initiated | Yes (production) |
| `PORT` | Server port (default: 8080) | No |

### Update Environment Variables

```bash
gcloud run services update twilio-warm-handoff-backend \
  --region us-central1 \
  --set-env-vars "DEMO_MODE=false,HUMAN_AGENT_WEBHOOK=https://your-webhook.com"
```

## Step 3: Create OpenAPI Tool in CX Agent Studio

1. **Navigate to your Agent** in CX Agent Studio
2. **Go to Tools** > **Create Tool**
3. **Select "OpenAPI"** as the tool type
4. **Enter the OpenAPI spec URL:**
   ```
   https://twilio-warm-handoff-backend-689910341505.us-central1.run.app/openapi.yaml
   ```
   Or use your deployed Cloud Run URL + `/openapi.yaml`

5. **Select the operation:** `initiateHumanHandoff`

6. **Configure parameter mappings:**

   | Parameter | Source | Value |
   |-----------|--------|-------|
   | session_id | Session | `$session.id` |
   | user_id | Session | `$session.user_id` |
   | issue_summary | Agent Generated | (agent provides at runtime) |
   | transcript | Conversation | `$conversation.recent_messages` |

7. **Save the tool**

## Step 4: Add Handoff Instructions to Agent

Add the following to your agent's instructions:

```
### Human Handoff Capability

You can transfer conversations to human agents using the "Initiate Human Handoff" tool.

**When to transfer:**
- User explicitly asks to speak to a human
- Complex issues beyond your capability
- User shows frustration after multiple attempts

**How to transfer:**
1. Acknowledge the transfer request
2. Call the "Initiate Human Handoff" tool with:
   - session_id: $session.id
   - issue_summary: Brief description of the user's issue
3. Confirm the transfer to the user

**Example:**
"I understand you'd like to speak with a human agent. Let me transfer you now.
The agent will have our full conversation, so you won't need to repeat yourself."
```

See `agent_studio/agent_instructions.md` for detailed instructions.

## Step 5: Test the Integration

### Test via Backend Directly

```bash
# Test handoff endpoint
curl -X POST $SERVICE_URL/start_transfer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-123",
    "user_id": "test-user-456",
    "issue_summary": "User needs help with password reset",
    "transcript": "User: I forgot my password\nAgent: Let me help you reset it."
  }'
```

Expected response:
```json
{
  "status": "success",
  "message": "Warm handoff initiated (demo mode)",
  "handoff_id": "handoff_test-session-123_20260317143052",
  "demo_mode": true
}
```

### Test via CX Agent Studio

1. Open your agent in the **Simulator**
2. Start a conversation
3. Type: "I want to talk to a human"
4. Verify the agent calls the handoff tool
5. Check Cloud Run logs for the handoff context:
   ```bash
   gcloud run services logs read twilio-warm-handoff-backend --region us-central1
   ```

## Step 6: Connect Human Agent System

In production, configure `HUMAN_AGENT_WEBHOOK` to point to your human agent routing system. The webhook receives:

```json
{
  "handoff_id": "handoff_session123_20260317143052",
  "session_id": "session123",
  "user_id": "user456",
  "channel_id": "CH1234567890",
  "issue_summary": "User needs help with billing",
  "transcript": "User: Hi\nAgent: Hello!\n...",
  "timestamp": "2026-03-17T14:30:52.123456",
  "source": "cx_agent_studio"
}
```

Your system should:
1. Route the request to an available human agent
2. Display the issue summary and transcript
3. Connect the agent to the user's conversation
4. (Optional) Call `/handoff_status` to report completion

## Troubleshooting

### Common Issues

**"Missing required field: session_id"**
- Ensure CX Agent Studio is passing session context
- Check parameter mappings in the tool configuration

**"Human agent webhook not configured"**
- Set `HUMAN_AGENT_WEBHOOK` environment variable
- Or enable `DEMO_MODE=true` for testing

**"Failed to notify human agent"**
- Verify the webhook URL is accessible
- Check the webhook endpoint returns 2xx status
- Review Cloud Run logs for detailed errors

**Agent doesn't trigger handoff**
- Verify the tool is added to the agent's available tools
- Check agent instructions include handoff triggers
- Test with explicit phrases like "speak to human"

### View Logs

```bash
# Stream logs
gcloud run services logs tail twilio-warm-handoff-backend --region us-central1

# View recent logs
gcloud run services logs read twilio-warm-handoff-backend --region us-central1 --limit 50
```

### Local Development

```bash
cd flask_app
pip install -r requirements.txt

# Run in demo mode
DEMO_MODE=true python main.py

# Test locally
curl -X POST http://localhost:8080/start_transfer \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-123", "issue_summary": "Test issue"}'
```

## Security Considerations

- **Authentication**: Consider adding API key or OAuth authentication for production
- **Secrets**: Use Google Secret Manager for Twilio credentials instead of env vars
- **Rate Limiting**: Add rate limiting to prevent abuse
- **Input Validation**: The backend validates required fields; consider additional sanitization

## Next Steps

- [ ] Configure authentication for the backend
- [ ] Set up monitoring and alerting
- [ ] Connect to your human agent routing system
- [ ] Add analytics for handoff metrics
