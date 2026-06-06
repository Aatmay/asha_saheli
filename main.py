import os
import time
import random  # Required to inject jitter metrics into the exponential retry calculation
import requests
import uvicorn
from fastapi import FastAPI, Request, Response, BackgroundTasks, HTTPException
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Force load active workspace environment mapping parameters
load_dotenv()

app = FastAPI(
    title="ASHA Saheli Core Engine",
    description="Resilient Gemini 2.5 Flash Runtime Intelligence for brainBytes",
    version="1.1.0"
)

# Meta Cloud API Configuration parameter extraction
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "saheli_webhook_verify_2026")

# Initialize the official updated Google GenAI Client
# It automatically reads GEMINI_API_KEY directly from your saved .env configuration file
ai_client = genai.Client()


def send_whatsapp_message(to_number: str, message_body: str):
    """Dispatches outbound text streams back to the frontline user via Meta's Graph API."""
    if not PHONE_NUMBER_ID or not WHATSAPP_TOKEN:
        print("[System Error] Critical Meta credentials missing from environment setup.")
        return

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
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
        print(f"[Meta Cloud API] Inbound frame successfully acknowledged to {to_number}")
    except Exception as e:
        print(f"[Meta Cloud API Error] Failed to push network connection line: {e}")


def get_whatsapp_audio_text(media_id: str) -> str:
    """Downloads binary media file from Meta and transcribes it via Gemini 2.5 Flash."""
    try:
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        
        # Step A: Query Meta for the temporary binary asset download link
        media_info_res = requests.get(f"https://graph.facebook.com/v18.0/{media_id}", headers=headers, timeout=5)
        media_info_res.raise_for_status()
        download_url = media_info_res.json().get("url")
        
        if not download_url:
            return "[Error: Asset URL empty]"

        # Step B: Securely stream raw audio binary packets
        audio_binary_res = requests.get(download_url, headers=headers, timeout=10)
        audio_binary_res.raise_for_status()
        
        local_audio_path = f"incoming_{media_id}.ogg"
        with open(local_audio_path, "wb") as f:
            f.write(audio_binary_res.content)
            
        print(f"[Audio Ingestion Engine] Saved raw audio note locally: {local_audio_path}")

        # Step C: Upload binary file directly using Gemini's File API for safe multimodal parsing
        print("[Gemini File API] Processing voice file upload...")
        uploaded_file = ai_client.files.upload(file=local_audio_path)
        
        # Wait for file processing confirmation loop
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(0.5)
            uploaded_file = ai_client.files.get(name=uploaded_file.name)

        # Step D: Instruct Gemini 2.5 Flash to transcribe speech payload with internal loop retries
        print("[Gemini Flash] Transcribing voice registry packet using gemini-2.5-flash...")
        
        max_asr_retries = 3
        asr_delay = 1.0
        response = None
        
        for attempt in range(max_asr_retries):
            try:
                response = ai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        uploaded_file, 
                        "Extract and transcribe the spoken words in this audio file perfectly. If it is spoken in Hindi or Hinglish, transcribe it directly into readable Devanagari text script. Return ONLY the transcription text output."
                    ]
                )
                break
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    if attempt < max_asr_retries - 1:
                        sleep_time = aser_delay * random.uniform(0.5, 1.5)
                        print(f"[ASR Quota Retry] Transcription 503 limit caught. Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        asr_delay *= 2
                        continue
                raise e
        
        # Cleanup file resources to maintain storage health
        ai_client.files.delete(name=uploaded_file.name)
        if os.path.exists(local_audio_path):
            os.remove(local_audio_path)
            
        if not response or not response.text:
            return "[Error: Empty transcription text]"
            
        print(f"[Gemini Transcription Success]: '{response.text.strip()}'")
        return response.text.strip()

    except Exception as e:
        print(f"[Voice Pipeline Crash Log]: {e}")
        return "[Error processing worker voice data]"


def process_agent_pipeline_async(from_number: str, media_id: str = None, text_input: str = None):
    """Asynchronous pipeline handler with permanent 503 Exponential Backoff Resilience."""
    try:
        user_prompt = ""

        if text_input:
            user_prompt = text_input
        elif media_id:
            user_prompt = get_whatsapp_audio_text(media_id)

        if not user_prompt or user_prompt.startswith("[Error"):
            send_whatsapp_message(from_number, "क्षमा करें, मैं आपके संदेश को संसाधित नहीं कर सकी। कृपया फिर से प्रयास करें।")
            return

        print(f"[Agent Layer] Handing prompt to Gemini 2.5 Flash: '{user_prompt}'")

        # Load your exact Project Document specifications into Gemini's system instructions
        system_instruction = (
            "You are ASHA Saheli, an intelligent, empathetic AI workflow companion designed for "
            "frontline health workers in rural India. The user interacting with you is an ASHA worker.\n\n"
            "Core Design Principles to follow:\n"
            "1. INCENTIVE-FIRST: Prioritize identifying work logs that translate into money recovery for her.\n"
            "2. Simple conversational Hindi (using Devanagari script).\n"
            "3. Help her track patient records, auto-fill ghostwritten entries for registers, and handle checkups.\n\n"
            "Respond warmly, supportively, and concisely."
        )

        # Resiliency Block: Try up to 4 times with exponential backoff if Google throws a 503 spike
        max_retries = 4
        backoff_delay = 1.0  
        response = None

        for attempt in range(max_retries):
            try:
                response = ai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.3
                    )
                )
                # Successful response breakout
                break
            except Exception as e:
                # Capture capacity issues safely
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    if attempt < max_retries - 1:
                        jitter = random.uniform(0.5, 1.5)
                        sleep_time = backoff_delay * jitter
                        print(f"[Infrastructure Warning] Gemini server busy (503). Retrying attempt {attempt + 1}/{max_retries} in {sleep_time:.2f} seconds...")
                        time.sleep(sleep_time)
                        backoff_delay *= 2  
                        continue
                raise e

        if not response or not response.text:
            print("[Worker Core Queue Error] Pipeline failed to fetch execution content after backing off.")
            return

        ai_response = response.text.strip()
        print(f"[Gemini Flash Agent Output]: {ai_response}")

        # Send the smart dynamic output back to her phone screen
        send_whatsapp_message(from_number, ai_response)
        
    except Exception as e:
        print(f"[Worker Core Queue Error]: Exception tracking pipeline generation execution: {e}")


@app.get("/")
async def status():
    return {"status": "online", "engine": "ASHA Saheli - Gemini 2.5 Flash Resilient Production Active"}


@app.get("/whatsapp/webhook")
async def verify(request: Request):
    if request.query_params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=request.query_params.get("hub.challenge"), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token verification mismatch.")


@app.post("/whatsapp/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" in value:
            msg_obj = value["messages"][0]
            from_number = msg_obj["from"]

            # Instant async response layer to hide connection latency over rural 4G
            send_whatsapp_message(from_number, "सुन रहे हैं... कृपया 30 सेकंड प्रतीक्षा करें। 🙏")

            media_id = msg_obj["audio"]["id"] if msg_obj["type"] == "audio" else None
            text_input = msg_obj["text"]["body"] if msg_obj["type"] == "text" else None

            background_tasks.add_task(
                process_agent_pipeline_async,
                from_number=from_number,
                media_id=media_id,
                text_input=text_input
            )
    except Exception as e:
        print(f"[Webhook Parse Warning]: {e}")
        
    return Response(content="EVENT_RECEIVED", status_code=200)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)