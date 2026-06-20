import os
import uvicorn
import app.database.models as models
from app.database.sqlite_client import sqlite_engine

# Automatically compile local SQLite schemas using the newly declared Base instance
models.Base.metadata.create_all(bind=sqlite_engine)

from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.whatsapp import router as stateful_whatsapp_router

load_dotenv()

app = FastAPI(
    title="ASHA Saheli Core Engine",
    description="Resilient Contextual Multi-Turn Pipeline Gateway",
    version="1.3.0"
)

@app.get("/")
async def status():
    return {"status": "online", "state_routing": "Mounted and Active"}

app.include_router(stateful_whatsapp_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)