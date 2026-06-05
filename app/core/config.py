import os
from dotenv import load_dotenv

# Load variables from the .env file in the root directory
load_dotenv()

class Settings:
    # Meta WhatsApp Business API Credentials
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    VERIFY_TOKEN: str = os.getenv("VERIFY_TOKEN", "")
    PHONE_NUMBER_ID: str = os.getenv("PHONE_NUMBER_ID", "")
    
    # AI / Agent Stack Configuration (For downstream pipelines)
    BHASHINI_API_KEY: str = os.getenv("BHASHINI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

settings = Settings()