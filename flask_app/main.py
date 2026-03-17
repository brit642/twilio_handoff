"""
Twilio Warm Handoff Backend - Text-Based Implementation

This Flask service handles warm transfers from CX Agent Studio virtual agents
to human agents via Twilio. The human agent receives the full conversation
context (transcript, issue summary) before taking over.
"""

import os
import logging
import json
from datetime import datetime
from flask import Flask, request, jsonify
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment variables
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
HUMAN_AGENT_WEBHOOK = os.environ.get("HUMAN_AGENT_WEBHOOK")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
PORT = int(os.environ.get("PORT", 8080))

# Initialize Twilio client only if not in demo mode and credentials are present
twilio_client = None
if not DEMO_MODE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        from twilio.rest import Client
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully")
    except ImportError:
        logger.warning("Twilio library not installed. Running in demo mode.")
        DEMO_MODE = True
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        DEMO_MODE = True


@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "twilio-warm-handoff",
        "demo_mode": DEMO_MODE,
        "timestamp": datetime.utcnow().isoformat()
    }), 200


@app.route("/start_transfer", methods=["POST"])
def start_transfer():
    """
    Initiates a text-based warm transfer to a human agent.

    The virtual agent calls this endpoint when a handoff is needed.
    The backend notifies the human agent system with full conversation context.

    Expected JSON payload:
    {
        "session_id": "required - CX Agent session identifier",
        "user_id": "optional - User identifier",
        "transcript": "optional - Recent conversation history",
        "issue_summary": "optional - AI-generated summary of the issue",
        "channel_id": "optional - Twilio conversation/channel identifier"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        logger.warning("No JSON payload received")
        return jsonify({
            "status": "error",
            "message": "Missing JSON payload"
        }), 400

    # Extract required and optional fields
    session_id = data.get("session_id")
    if not session_id:
        logger.warning("Missing session_id in request")
        return jsonify({
            "status": "error",
            "message": "Missing required field: session_id"
        }), 400

    user_id = data.get("user_id", "unknown")
    transcript = data.get("transcript", "")
    issue_summary = data.get("issue_summary", "No summary provided")
    channel_id = data.get("channel_id", "")

    logger.info(f"Warm handoff requested - Session: {session_id}, User: {user_id}")
    logger.info(f"Issue Summary: {issue_summary}")

    # Build handoff context for human agent
    handoff_context = {
        "handoff_id": f"handoff_{session_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "session_id": session_id,
        "user_id": user_id,
        "channel_id": channel_id,
        "issue_summary": issue_summary,
        "transcript": transcript,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "cx_agent_studio"
    }

    if DEMO_MODE:
        return _handle_demo_mode(handoff_context)

    return _handle_production_mode(handoff_context)


def _handle_demo_mode(handoff_context):
    """
    Demo mode: Log the handoff context without calling external services.
    Useful for testing and demonstrations.
    """
    logger.info("=" * 60)
    logger.info("DEMO MODE - Warm Handoff Initiated")
    logger.info("=" * 60)
    logger.info(f"Handoff ID: {handoff_context['handoff_id']}")
    logger.info(f"Session ID: {handoff_context['session_id']}")
    logger.info(f"User ID: {handoff_context['user_id']}")
    logger.info(f"Channel ID: {handoff_context['channel_id']}")
    logger.info("-" * 40)
    logger.info(f"Issue Summary: {handoff_context['issue_summary']}")
    logger.info("-" * 40)
    logger.info("Transcript:")
    for line in handoff_context['transcript'].split('\n'):
        logger.info(f"  {line}")
    logger.info("=" * 60)
    logger.info("In production, this would notify the human agent system")
    logger.info("=" * 60)

    return jsonify({
        "status": "success",
        "message": "Warm handoff initiated (demo mode)",
        "handoff_id": handoff_context["handoff_id"],
        "demo_mode": True
    }), 200


def _handle_production_mode(handoff_context):
    """
    Production mode: Notify human agent system via webhook.
    The webhook should be configured to route to your agent routing system.
    """
    if not HUMAN_AGENT_WEBHOOK:
        logger.error("HUMAN_AGENT_WEBHOOK not configured")
        return jsonify({
            "status": "error",
            "message": "Human agent webhook not configured"
        }), 500

    try:
        # Send handoff context to human agent system
        response = requests.post(
            HUMAN_AGENT_WEBHOOK,
            json=handoff_context,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()

        logger.info(f"Human agent notified successfully for handoff {handoff_context['handoff_id']}")

        return jsonify({
            "status": "success",
            "message": "Warm handoff initiated - human agent notified",
            "handoff_id": handoff_context["handoff_id"],
            "webhook_status": response.status_code
        }), 200

    except requests.exceptions.Timeout:
        logger.error("Timeout while notifying human agent system")
        return jsonify({
            "status": "error",
            "message": "Timeout while notifying human agent"
        }), 504

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to notify human agent system: {e}")
        return jsonify({
            "status": "error",
            "message": f"Failed to notify human agent: {str(e)}"
        }), 502


@app.route("/handoff_status", methods=["POST"])
def handoff_status():
    """
    Callback endpoint for handoff completion status.

    Human agent systems can call this endpoint to report handoff status:
    - Agent accepted the handoff
    - Handoff completed
    - Handoff failed/timed out

    Expected JSON payload:
    {
        "handoff_id": "The handoff identifier",
        "status": "accepted|completed|failed|timeout",
        "agent_id": "Human agent identifier",
        "notes": "Optional notes about the handoff"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "status": "error",
            "message": "Missing JSON payload"
        }), 400

    handoff_id = data.get("handoff_id")
    status = data.get("status")

    if not handoff_id or not status:
        return jsonify({
            "status": "error",
            "message": "Missing required fields: handoff_id, status"
        }), 400

    agent_id = data.get("agent_id", "unknown")
    notes = data.get("notes", "")

    logger.info(f"Handoff status update - ID: {handoff_id}, Status: {status}, Agent: {agent_id}")
    if notes:
        logger.info(f"Notes: {notes}")

    # In a full implementation, you might:
    # - Update a database with handoff status
    # - Send analytics events
    # - Notify other systems

    return jsonify({
        "status": "success",
        "message": f"Handoff status updated: {status}",
        "handoff_id": handoff_id
    }), 200


if __name__ == "__main__":
    logger.info(f"Starting Twilio Warm Handoff Backend on port {PORT}")
    logger.info(f"Demo Mode: {DEMO_MODE}")
    if DEMO_MODE:
        logger.info("Running in DEMO MODE - no external calls will be made")
    app.run(host="0.0.0.0", port=PORT, debug=True)
