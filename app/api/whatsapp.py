import os
import json
import requests
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from google import genai
from dotenv import load_dotenv

# Import database sessions and structures
from app.database.database import get_local_db, get_postgres_db
from app.database import models
from app.database.vector_db import query_knowledge_corpus
from router import route_incoming_intent

load_dotenv()

router = APIRouter()

# --- INCENTIVE TRACKER RULE ENGINE CONFIGURATION ---
# Deterministic real-world government payout mappings to eliminate LLM math calculation errors
TASK_PAYOUTS = {
    "ANC_REGISTRATION": 300.0,       # Rupee award for an Antenatal Care registration
    "IMMUNIZATION_COMPLETE": 150.0,  # Rupee award for delivering a full vaccination schedule
    "INSTITUTIONAL_DELIVERY": 500.0, # Rupee award for facilitating hospital institutional births
    "HIGH_RISK_REFERRAL": 200.0       # Rupee award for routing high-risk cases to medical facilities
}

@router.get("/whatsapp/webhook")
async def verify_webhook(request: Request):
    """Handles the initial security handshake authentication challenge with Meta Cloud API."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode == "subscribe" and token == os.getenv("VERIFY_TOKEN"):
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification Token Mismatch", status_code=403)


@router.post("/whatsapp/webhook")
async def receive_whatsapp_message(
    request: Request, 
    sqlite_db: Session = Depends(get_local_db),
    postgres_db: Session = Depends(get_postgres_db)
):
    """
    Main ingestion endpoint processing active WhatsApp message packets from health workers,
    routing them by programmatic intent, and saving patient/incentive data metrics.
    """
    payload = await request.json()
    
    # 1. Parse inbound sender details out of the Meta context layout envelope
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        message = value.get("messages", [])[0]
        
        sender_phone = message.get("from") # The target ASHA worker's identity key
        
        # Capture raw user prompt whether text or parsed voice transcription asset
        incoming_text = ""
        if message.get("type") == "text":
            incoming_text = message.get("text", {}).get("body", "")
        elif message.get("type") == "audio":
            # For Audio Integration Pipeline: fallback until Bhashini IndicASR endpoint hook is live
            incoming_text = "[Voice Input Captured]" 
            
        if not incoming_text:
            return {"status": "ignored", "reason": "Empty text frame"}
            
    except (IndexError, KeyError, TypeError):
        return {"status": "ignored", "reason": "Malformed webhook structure payload packet"}

    # Check if the ASHA worker profile exists in our local database, onboard automatically if missing
    worker = sqlite_db.query(models.AshaWorker).filter(models.AshaWorker.phone_number == sender_phone).first()
    if not worker:
        worker = models.AshaWorker(phone_number=sender_phone, name="Asha Worker", village_name="Pilot Village")
        sqlite_db.add(worker)
        sqlite_db.commit()
        sqlite_db.refresh(worker)

    # 2. ENGAGE COGNITIVE INTENT ROUTER LAYER
    # Pass prompt context to Gemini Flash structured schema engine to evaluate user task context
    routing_result = route_incoming_intent(incoming_text)
    print(f"--- ROUTING ENGAGED --- Intent detected: {routing_result.intent} | Reason: {routing_result.reason}")

    # 3. RUN DATABASE AND INCENTIVE ACTIONS BASED ON INTENT MATCH
    response_message = ""
    
    # --- ROUTE A: INCENTIVE EXTRACTION & DOCUMENTATION ---
    if routing_result.intent == "INCENTIVE_TRACKER":
        # Check text contents to match the right task type
        task_detected = "ANC_REGISTRATION" # Fallback baseline
        
        if "delivery" in incoming_text.lower() or "प्रसव" in incoming_text:
            task_detected = "INSTITUTIONAL_DELIVERY"
        elif "vaccine" in incoming_text.lower() or "टीका" in incoming_text or "टीकाकरण" in incoming_text:
            task_detected = "IMMUNIZATION_COMPLETE"
        elif "referral" in incoming_text.lower() or "रेफर" in incoming_text:
            task_detected = "HIGH_RISK_REFERRAL"

        reward_amount = TASK_PAYOUTS.get(task_detected, 0.0)
        
        # Step 1: Update the ASHA running transaction ledger in local SQLite cache
        worker.total_incentives_earned += reward_amount
        sqlite_db.commit()
        
        # Step 2: Log patient profile demographics into centralized PostgreSQL backend storage
        new_patient = models.PatientRecord(
            asha_phone=sender_phone,
            patient_name=f"Patient Registered via {task_detected}",
            age=25,
            risk_status="Normal"
        )
        postgres_db.add(new_patient)
        postgres_db.commit()
        
        response_message = (
            f"नमस्ते आशा दीदी! आपका कार्य सफलतापुर्वक दर्ज कर लिया गया है।\n\n"
            f"💰 इस कार्य के लिए आपका इंसेंटिव: ₹{reward_amount}\n"
            f"📈 इस महीने का आपका कुल इंसेंटिव अब: ₹{worker.total_incentives_earned} हो गया है!"
        )

    # --- ROUTE B: CLINICAL GUIDELINE PROTOCOL LOOKUP (STG MIRROR) ---
    elif routing_result.intent == "STG_MIRROR":
        # Step 1: Pull relevant clinical handbook guidelines out of your Pinecone Vector Database
        relevant_guidelines = query_knowledge_corpus(incoming_text, top_k=2)
        context_str = "\n".join(relevant_guidelines) if relevant_guidelines else "No specific guideline text found in corpus."
        
        # Step 2: Synthesize a clean, grounded conversational answer using Gemini 2.5 Flash
        try:
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            
            system_instruction = (
                "You are Asha Saheli, a medical guidelines assistant. Use the provided National Health Mission "
                "guidelines context to answer the user's question accurately in simple, friendly spoken Hindi. "
                "Do not make up medical facts. If unsure, tell her to refer the patient to the nearest medical officer."
            )
            
            prompt = f"Guidelines Context:\n{context_str}\n\nASHA Worker Question: {incoming_text}"
            
            ai_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={'system_instruction': system_instruction}
            )
            response_message = ai_response.text
        except Exception as gemini_err:
            print(f"Gemini Synthesis Exception: {gemini_err}")
            response_message = "नमस्ते आशा दीदी! तकनीकी समस्या के कारण मैं अभी जानकारी नहीं निकाल पा रही हूँ। कृपया थोड़ी देर बाद प्रयास करें।"

    # --- ROUTE C: CONVERSATIONAL GENERAL PROCESSING ---
    else:
        response_message = (
            f"नमस्ते आशा दीदी! मैं आपकी 'आशा सहेली' हूँ।\n\n"
            f"आप मुझसे अपने काम का रिकॉर्ड दर्ज करा सकती हैं (जैसे कि ANC रजिस्ट्रेशन या डिलीवरी) "
            f"या फिर किसी बीमारी के इलाज के सरकारी नियम पूछ सकती हैं। आज मैं आपकी क्या मदद करूँ?"
        )

    # 4. DISPATCH OUTBOUND WHATSAPP FRAME BACK TO SENDER PHONE
    send_whatsapp_message_payload(sender_phone, response_message)

    return {"status": "processed", "intent": routing_result.intent}


def send_whatsapp_message_payload(recipient_phone: str, text_body: str):
    """Dispatches outgoing text strings to the Meta Graph API gateway endpoint securely."""
    url = f"https://graph.facebook.com/v18.0/{os.getenv('PHONE_NUMBER_ID')}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": text_body}
    }
    try:
        res = requests.post(url, json=data, headers=headers)
        if res.status_code != 200:
            print(f"Meta Gateway Outbound Error Code: {res.status_code} | Log: {res.text}")
    except Exception as network_error:
        print(f"Outbound Delivery Pipeline Exception Failed: {network_error}")