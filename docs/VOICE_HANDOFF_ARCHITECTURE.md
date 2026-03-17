# Voice Handoff Architecture

This document describes how to extend the current text-based warm handoff solution to support **voice calls** using Twilio's Programmable Voice API.

## Overview

Voice handoff is more complex than text because it involves:
- **Real-time audio streams** instead of text messages
- **Conference bridging** to connect multiple parties
- **Hold music/announcements** while waiting for human agent
- **Call state management** across the transfer

## Architecture Comparison

### Text-Based (Current)
```
User ──text──▶ CX Agent Studio ──API──▶ Backend ──webhook──▶ Human Agent System
```

### Voice-Based (Future)
```
                                    ┌────────────────┐
User ──PSTN──▶ Twilio ──webhook──▶ │ CX Agent Studio │
                 │                  │ (Voice Agent)   │
                 │                  └────────┬────────┘
                 │                           │
                 │                    handoff trigger
                 │                           │
                 ▼                           ▼
         ┌──────────────┐           ┌───────────────┐
         │   Twilio     │◀──TwiML───│ Flask Backend │
         │  Conference  │           └───────────────┘
         └──────┬───────┘                    │
                │                            │
    ┌───────────┴───────────┐               │
    ▼                       ▼               ▼
┌────────┐            ┌────────────┐   ┌────────────┐
│  User  │            │Human Agent │   │ Call Agent │
│ (hold) │            │  (dialed)  │   │   (SIP)    │
└────────┘            └────────────┘   └────────────┘
```

## Key Components

### 1. Twilio Voice Webhook

When a call comes in, Twilio sends a webhook to your application with call details.

```python
@app.route("/voice/incoming", methods=["POST"])
def incoming_call():
    """Handle incoming voice call from Twilio."""
    call_sid = request.form.get("CallSid")
    from_number = request.form.get("From")

    # Start CX Agent Studio voice session
    # Return TwiML to connect to voice agent
    response = VoiceResponse()
    response.say("Welcome! How can I help you today?")
    # Connect to CX Agent Studio voice endpoint
    response.connect(url="wss://cx-agent-studio-voice-endpoint")

    return str(response)
```

### 2. Conference-Based Handoff

The key to voice handoff is using Twilio Conferences:

```python
@app.route("/voice/start_transfer", methods=["POST"])
def start_voice_transfer():
    """Initiate voice handoff using Twilio Conference."""
    call_sid = request.json.get("call_sid")
    context = request.json.get("context")  # Issue summary, transcript

    # Create unique conference name
    conference_name = f"handoff_{call_sid}"

    # Step 1: Move user to conference with hold music
    client.calls(call_sid).update(
        url=f"{BASE_URL}/voice/join_conference_user?conf={conference_name}",
        method="POST"
    )

    # Step 2: Call human agent and add to same conference
    client.calls.create(
        to=HUMAN_AGENT_NUMBER,
        from_=TWILIO_NUMBER,
        url=f"{BASE_URL}/voice/join_conference_agent?conf={conference_name}",
        status_callback=f"{BASE_URL}/voice/agent_status"
    )

    # Step 3: Send context to agent's screen (via separate channel)
    notify_agent_screen(agent_id, context)

    return jsonify({"status": "transfer_initiated", "conference": conference_name})
```

### 3. TwiML Endpoints

#### User Joins Conference (with hold music)
```python
@app.route("/voice/join_conference_user", methods=["POST"])
def join_conference_user():
    """TwiML for user to join conference with hold music."""
    conference_name = request.args.get("conf")

    response = VoiceResponse()
    response.say("Please hold while we connect you to an agent.")

    dial = Dial()
    dial.conference(
        conference_name,
        start_conference_on_enter=False,  # Wait for agent
        end_conference_on_exit=True,
        wait_url="http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical",
        wait_method="GET"
    )
    response.append(dial)

    return str(response)
```

#### Agent Joins Conference
```python
@app.route("/voice/join_conference_agent", methods=["POST"])
def join_conference_agent():
    """TwiML for agent to join conference."""
    conference_name = request.args.get("conf")

    response = VoiceResponse()
    response.say("You are joining a customer call. Context has been sent to your screen.")

    dial = Dial()
    dial.conference(
        conference_name,
        start_conference_on_enter=True,  # Start when agent joins
        end_conference_on_exit=True,
        beep=True  # Notify user that agent joined
    )
    response.append(dial)

    return str(response)
```

## Implementation Steps

### Phase 1: Basic Voice Handoff

1. **Set up Twilio Phone Number**
   - Purchase a Twilio phone number
   - Configure voice webhook to your application

2. **Implement Conference Logic**
   - Create conference endpoints
   - Implement hold music
   - Handle agent dialing

3. **Integrate with CX Agent Studio Voice**
   - Connect CX Agent Studio to handle initial voice interaction
   - Trigger handoff when agent detects need

### Phase 2: Context Transfer

1. **Screen Pop for Agents**
   - Build agent dashboard to display context
   - Send context via WebSocket or API when call transfers

2. **Transcript Handoff**
   - Capture voice-to-text transcript from CX Agent Studio
   - Include in context sent to human agent

### Phase 3: Advanced Features

1. **Warm Introduction**
   - Agent joins conference but user can't hear
   - Virtual agent provides verbal context to human agent
   - Then connect all parties

2. **Supervisor Monitoring**
   - Add supervisor to conference in listen-only mode
   - Enable whisper (supervisor speaks to agent only)

3. **Call Recording**
   - Record conference for quality assurance
   - Store with handoff context

## Sample Voice Handoff Flow

```
Timeline:
─────────────────────────────────────────────────────────────────────▶

User calls         CX Agent          Handoff          Agent         Connected
    │             handles call       triggered         joins           │
    │                 │                 │               │              │
    ▼                 ▼                 ▼               ▼              ▼
┌───────┐       ┌──────────┐      ┌─────────┐    ┌──────────┐    ┌─────────┐
│ Ring  │──────▶│  Voice   │─────▶│ User to │───▶│ Agent    │───▶│ User +  │
│       │       │  Agent   │      │ Hold    │    │ Dialed   │    │ Agent   │
└───────┘       └──────────┘      └─────────┘    └──────────┘    └─────────┘
                                        │              │
                                        │              │
                                   Hold Music    Context Screen Pop
```

## Code Structure for Voice

```
flask_app/
├── main.py                    # Current text endpoints
├── voice/
│   ├── __init__.py
│   ├── handlers.py            # Voice webhook handlers
│   ├── conference.py          # Conference management
│   ├── twiml_responses.py     # TwiML generators
│   └── context_transfer.py    # Agent screen pop logic
├── openapi.yaml               # Updated with voice endpoints
└── requirements.txt           # Add twilio>=9.0.0
```

## New Endpoints for Voice

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice/incoming` | POST | Handle incoming calls |
| `/voice/start_transfer` | POST | Initiate voice handoff |
| `/voice/join_conference_user` | POST | TwiML for user to join conference |
| `/voice/join_conference_agent` | POST | TwiML for agent to join conference |
| `/voice/agent_status` | POST | Callback for agent call status |
| `/voice/conference_status` | POST | Callback for conference events |

## Environment Variables (Additional)

| Variable | Description |
|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number |
| `HUMAN_AGENT_PHONE` | Human agent phone number |
| `AGENT_DASHBOARD_URL` | URL for agent screen pop |

## Twilio Pricing Considerations

| Component | Cost (approximate) |
|-----------|-------------------|
| Phone Number | $1/month |
| Inbound Calls | $0.0085/min |
| Outbound Calls (to agent) | $0.014/min |
| Conference | $0.0025/min per participant |

## CX Agent Studio Voice Integration

CX Agent Studio supports voice through:
1. **Telephony Integration** - Connect phone numbers directly
2. **WebRTC** - Browser-based voice
3. **SIP Trunking** - Enterprise phone systems

The handoff trigger works similarly to text:
```xml
<taskflow>
  <subtask name="Voice Handoff">
    <step name="Detect Handoff Need">
      <trigger>User says "speak to a human" or similar</trigger>
      <action>
        Say: "Let me transfer you to a specialist."
        Call initiateVoiceHandoff tool.
      </action>
    </step>
  </subtask>
</taskflow>
```

## Migration Path

To migrate from text to voice:

1. **Keep text handoff working** - Don't break existing functionality
2. **Add voice endpoints** - Separate route handlers
3. **Unified context format** - Same JSON structure for context
4. **Shared agent dashboard** - Display context from both channels
5. **Gradual rollout** - Test with subset of calls first

## Security Considerations

1. **Validate Twilio Requests**
   ```python
   from twilio.request_validator import RequestValidator

   validator = RequestValidator(TWILIO_AUTH_TOKEN)
   if not validator.validate(url, request.form, signature):
       return "Invalid request", 403
   ```

2. **Secure Conference Names** - Use unpredictable conference IDs

3. **Call Recording Consent** - Announce recording if enabled

4. **Agent Authentication** - Verify agent identity before connecting

## References

- [Twilio Programmable Voice](https://www.twilio.com/docs/voice)
- [Twilio Conference](https://www.twilio.com/docs/voice/tutorials/how-to-create-conference-calls)
- [TwiML Reference](https://www.twilio.com/docs/voice/twiml)
- [CX Agent Studio Voice](https://cloud.google.com/agent-studio/docs/voice)

## Next Steps

1. Review this architecture with stakeholders
2. Set up Twilio account and phone number
3. Implement Phase 1 (basic conference handoff)
4. Integrate with CX Agent Studio voice
5. Build agent dashboard for context display
6. Test end-to-end voice flow
