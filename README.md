# Twilio Warm Handoff for CX Agent Studio

A production-ready solution for transferring conversations from CX Agent Studio virtual agents to human agents via Twilio. This implementation focuses on **text-based chat** and provides a complete demo package showcasing Google Cloud products.

## Overview

### What is a "Warm" Handoff?

A warm handoff transfers a conversation to a human agent **with full context**. The human agent receives:
- **Conversation transcript** - Complete chat history
- **Issue summary** - AI-generated summary of the user's problem
- **Session metadata** - User ID, channel info, timestamps

This allows the human agent to continue seamlessly without asking "How can I help you?" — they already know the context.

### Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│                 │     │                      │     │                 │
│  User (Chat)    │────▶│  CX Agent Studio     │────▶│  Flask Backend  │
│                 │     │  (Virtual Agent)     │     │  (Cloud Run)    │
│                 │     │                      │     │                 │
└─────────────────┘     └──────────────────────┘     └────────┬────────┘
                                                              │
                                                              ▼
                                                     ┌─────────────────┐
                                                     │  Human Agent    │
                                                     │  System         │
                                                     │  (via Webhook)  │
                                                     └─────────────────┘
```

### Flow

1. **User** chats with CX Agent Studio virtual agent
2. **Virtual Agent** detects need for human handoff (user request or complex issue)
3. **Virtual Agent** calls `initiateHumanHandoff` tool with conversation context
4. **Flask Backend** receives request and notifies human agent system
5. **Human Agent** receives full context and continues the conversation

## Quick Start

### Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Python 3.9+ (for local development)
- Access to CX Agent Studio

### 1. Deploy to Cloud Run (Demo Mode)

```bash
# Clone the repository
git clone https://github.com/brit642/twilio_handoff.git
cd twilio_handoff

# Deploy to Cloud Run
cd flask_app
gcloud run deploy twilio-warm-handoff-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "DEMO_MODE=true"
```

### 2. Test the Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe twilio-warm-handoff-backend \
  --region us-central1 --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/

# Test handoff endpoint
curl -X POST $SERVICE_URL/start_transfer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-123",
    "issue_summary": "User needs help with account access",
    "transcript": "User: I cannot log in\nAgent: Let me help you."
  }'
```

### 3. Configure CX Agent Studio

1. **Open your Agent** in [CX Agent Studio](https://ces.cloud.google.com)

2. **Create OpenAPI Toolset:**
   - Go to **Tools** → **Create Toolset**
   - Select **OpenAPI**
   - Paste the contents of `flask_app/openapi.yaml`
   - Name it "Human Handoff API"

3. **Assign Toolset to Agent:**
   - Select your root agent
   - Go to **Tools** section
   - Add the "Human Handoff API" toolset

4. **Add Agent Instructions:**

   Add this to your agent's instructions (see `agent_studio/agent_instructions.xml` for full template):

   ```xml
   <tools>
     <tool name="initiateHumanHandoff">
       <description>Transfers the conversation to a human agent with full context.</description>
       <when_to_use>
         - User explicitly requests to speak to a human
         - Complex issues beyond your capability
         - User shows frustration after multiple attempts
       </when_to_use>
     </tool>
   </tools>

   <taskflow>
     <subtask name="Human Handoff">
       <step name="Execute Transfer">
         <trigger>User requests human agent OR issue is too complex</trigger>
         <action>
           Call initiateHumanHandoff with session_id, issue_summary, and transcript.
           Say: "I've connected you with our support team."
         </action>
       </step>
     </subtask>
   </taskflow>
   ```

### 4. Test End-to-End

1. Open the **Simulator** in CX Agent Studio
2. Type: "I want to talk to a human"
3. Verify the agent calls the handoff tool
4. Check Cloud Run logs:
   ```bash
   gcloud run services logs read twilio-warm-handoff-backend --region us-central1 --limit 20
   ```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DEMO_MODE` | Set to `true` to log instead of calling external services | No (default: false) |
| `TWILIO_ACCOUNT_SID` | Your Twilio Account SID | Production only |
| `TWILIO_AUTH_TOKEN` | Your Twilio Auth Token | Production only |
| `HUMAN_AGENT_WEBHOOK` | Webhook URL to notify human agent system | Production only |
| `PORT` | Server port | No (default: 8080) |

### Production Deployment

```bash
# Set environment variables
gcloud run services update twilio-warm-handoff-backend \
  --region us-central1 \
  --set-env-vars "DEMO_MODE=false" \
  --set-env-vars "HUMAN_AGENT_WEBHOOK=https://your-agent-system.com/webhook"
```

## API Reference

### POST /start_transfer

Initiates a warm handoff to a human agent.

**Request:**
```json
{
  "session_id": "required - CX Agent session identifier",
  "user_id": "optional - User identifier",
  "transcript": "optional - Conversation history",
  "issue_summary": "optional - AI-generated issue summary",
  "channel_id": "optional - Twilio channel identifier"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Warm handoff initiated",
  "handoff_id": "handoff_session123_20260317143052"
}
```

### POST /handoff_status

Callback for human agent systems to report handoff completion.

**Request:**
```json
{
  "handoff_id": "required - Handoff identifier",
  "status": "required - accepted|completed|failed|timeout",
  "agent_id": "optional - Human agent identifier",
  "notes": "optional - Completion notes"
}
```

### GET /

Health check endpoint.

## Project Structure

```
twilio_handoff/
├── flask_app/
│   ├── main.py           # Flask application with endpoints
│   ├── openapi.yaml      # OpenAPI spec for CX Agent Studio
│   ├── requirements.txt  # Python dependencies
│   └── Dockerfile        # Container configuration
├── agent_studio/
│   ├── tool_config.yaml       # Toolset configuration guide
│   ├── agent_instructions.md  # Agent instruction templates
│   └── agent_instructions.xml # XML-formatted instructions
├── docs/
│   └── VOICE_HANDOFF_ARCHITECTURE.md  # Future voice implementation
├── SETUP_GUIDE.md        # Detailed setup instructions
└── README.md             # This file
```

## Demo Mode

Demo mode (`DEMO_MODE=true`) logs all handoff requests without calling external services. This is useful for:
- Testing the integration
- Demonstrations
- Development

**Demo mode output:**
```
============================================================
DEMO MODE - Warm Handoff Initiated
============================================================
Handoff ID: handoff_session123_20260317143052
Session ID: session123
User ID: user456
----------------------------------------
Issue Summary: User needs help with password reset
----------------------------------------
Transcript:
  User: I forgot my password
  Agent: Let me transfer you to a specialist.
============================================================
```

## Monitoring

### View Logs

```bash
# Stream logs
gcloud run services logs tail twilio-warm-handoff-backend --region us-central1

# View recent logs
gcloud run services logs read twilio-warm-handoff-backend --region us-central1 --limit 50
```

### Key Log Events

- `Warm handoff requested` - Handoff initiated
- `DEMO MODE - Warm Handoff Initiated` - Demo mode handoff
- `Human agent notified successfully` - Production webhook success

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Missing required field: session_id" | Ensure CX Agent passes session context |
| "Human agent webhook not configured" | Set `HUMAN_AGENT_WEBHOOK` or enable `DEMO_MODE` |
| Agent doesn't trigger handoff | Verify toolset is assigned and instructions include handoff triggers |
| 502 errors | Check webhook URL is accessible |

## Security Considerations

- **Authentication**: Consider adding API key authentication for production
- **Secrets Management**: Use Google Secret Manager for credentials
- **Rate Limiting**: Implement rate limiting to prevent abuse
- **Input Validation**: Backend validates required fields

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and feature requests, please open a GitHub issue.
