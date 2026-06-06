import os
import time
import requests
from fastapi import APIRouter, Request, Response, BackgroundTasks, HTTPException
from app.core.config import settings

# The prefix here handles the "/whatsapp" part of the URL structure
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhook"])

def send_instant_acknowledgement(to_number: str, message_body: str):
    """Fires a fast interactive/text reply back to WhatsApp to hide latency."""
    url = f"https://graph.facebook.com/v18.0/{settings.PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_body}
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        res.raise_for_status()
    except Exception as e:
        print(f"Failed to push fast acknowledgement: {e}")

def process_agent_pipeline_async(from_number: str, media_id: str = None, text_input: str = None):
    """
    Asynchronous Worker thread handling Audio Intelligence + Intent Router.
    This prevents clogging up the primary connection line.
    """
    try:
        print(f"[Worker] Thread spawned for {from_number}. Simulating pipeline tasks...")
        
        # Mocking pipeline duration (ASR Transcription -> LLM Agent Route -> Processing)
        time.sleep(4) 
        
        # Final delivery string imitating an Agent outcome
        resolved_reply = "नमस्ते! आपका संदेश मिल गया है। मैंने इंसेंटिव ट्रैकर अपडेट कर दिया है।"
        send_instant_acknowledgement(from_number, resolved_reply)
        
    except Exception as e:
        print(f"Error executing agent processing logic: {e}")


@router.get("/webhook")
async def verify_webhook(request: Request):
    """Verifies connection parameter registration from Meta developers hub."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    local_token = getattr(settings, "VERIFY_TOKEN", None) or os.getenv("VERIFY_TOKEN")

    if mode == "subscribe" and token == local_token:
        print("--- WEBHOOK VERIFIED SUCCESSFULLY ---")
        response = Response(content=challenge, media_type="text/plain")
        response.headers["ngrok-skip-browser-warning"] = "1"
        return response
    
    print(f"--- VERIFICATION FAILED --- Got: '{token}', Expected: '{local_token}'")
    raise HTTPException(status_code=403, detail="Verification failed; token mismatch.")


@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Receives JSON events from WhatsApp, runs fast response layer, hands heavy logic to queue."""
    data = await request.json()
    
    if "object" in data and data["object"] == "whatsapp_business_account":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    msg_obj = value["messages"][0]
                    from_number = msg_obj["from"]
                    msg_type = msg_obj["type"]

                    # Instant feedback pattern rule from our system document architecture
                    ack_message = "सुन रहे हैं... कृपया 30 सेकंड प्रतीक्षा करें। 🙏"
                    send_instant_acknowledgement(from_number, ack_message)

                    # Inspect inputs for routing profiles
                    media_id = msg_obj["audio"]["id"] if msg_type == "audio" else None
                    text_input = msg_obj["text"]["body"] if msg_type == "text" else None

                    # Push backend processing away from the user thread
                    background_tasks.add_task(
                        process_agent_pipeline_async,
                        from_number=from_number,
                        media_id=media_id,
                        text_input=text_input
                    )
                    
        return Response(content="EVENT_RECEIVED", status_code=200)
    
    raise HTTPException(status_code=400, detail="Invalid payload payload object definition.")