# Agent Instructions for Warm Handoff

Add these instructions to your CX Agent Studio agent to enable warm handoff functionality.

## Instructions to Add to Your Agent

Copy and paste the following into your agent's instructions/system prompt:

---

### Human Handoff Capability

You have the ability to transfer conversations to human agents when needed. Use the `Initiate Human Handoff` tool in these situations:

**When to Transfer:**
1. **User explicitly requests it** - Phrases like "speak to a human", "talk to a real person", "transfer me to an agent"
2. **Complex issues beyond your capability** - Legal matters, sensitive complaints, complex technical issues
3. **User frustration** - If the user seems frustrated after multiple attempts to help
4. **Safety concerns** - Any mention of self-harm, threats, or urgent safety matters

**Before Transferring:**
1. **Acknowledge the request** - Let the user know you're transferring them
2. **Prepare a summary** - Mentally note the key points of the conversation
3. **Set expectations** - Tell them a human agent will have full context

**How to Transfer:**
When calling the `Initiate Human Handoff` tool, include:
- `session_id`: Use `$session.id` (automatically populated)
- `issue_summary`: Write a brief summary like "User needs help with [specific issue]. Key details: [relevant info]"
- `transcript`: Recent conversation will be included automatically

**Example Responses:**

*When user asks to speak to a human:*
> "I understand you'd like to speak with a human agent. Let me transfer you right now. The agent will have our full conversation history, so you won't need to repeat yourself."
> [Call Initiate Human Handoff tool]
> "I've connected you with our support team. A human agent will continue this conversation shortly. Is there anything else you'd like me to note for them?"

*When transferring due to complexity:*
> "This is a complex situation that would be better handled by one of our specialists. I'm going to transfer you to a human agent who can assist you directly. They'll have all the context from our conversation."
> [Call Initiate Human Handoff tool]

---

## Variable References

Use these session variables in your agent logic:

| Variable | Description | Usage |
|----------|-------------|-------|
| `$session.id` | Current session identifier | Pass to handoff tool |
| `$session.user_id` | User identifier (if authenticated) | Pass to handoff tool |
| `$session.channel_id` | Conversation channel ID | For routing |
| `$conversation.recent_messages` | Recent chat history | Included in transcript |

## Testing the Handoff

1. Start a conversation with your agent in the simulator
2. Say "I want to talk to a human"
3. Verify the agent calls the handoff tool
4. Check the backend logs for the handoff context

## Troubleshooting

**Agent doesn't offer transfer:**
- Ensure the tool is added to the agent's available tools
- Check that the instructions mention when to use the tool

**Transfer fails:**
- Verify the backend is deployed and healthy
- Check the OpenAPI spec URL is correct
- Review backend logs for error details

**Missing context in handoff:**
- Ensure parameter mappings are configured correctly
- Verify the agent is generating an issue summary before calling
