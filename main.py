import uvicorn
from fastapi import FastAPI
from app.api.whatsapp import router as whatsapp_router

app = FastAPI(
    title="ASHA Saheli Backend Engine",
    description="Runtime Intelligence for India's Frontline Health Workers",
    version="1.0.0"
)

# Attach our operational endpoint modules
app.include_router(whatsapp_router)

@app.get("/")
async def root_status_check():
    return {
        "status": "online",
        "system": "ASHA Saheli Core Backend Engine",
        "active_modules": ["WhatsApp Input Channel Async Loop Ready"]
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)