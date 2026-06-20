from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class AshaWorker(Base):
    __tablename__ = "asha_workers"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="Asha Worker")
    village_name = Column(String, default="Pilot Village")
    total_incentives_earned = Column(Float, default=0.0)

class ChatSessionState(Base):
    __tablename__ = "chat_session_states"
    
    id = Column(Integer, primary_key=True, index=True)
    asha_phone = Column(String, unique=True, index=True, nullable=False)
    last_detected_patient = Column(String, nullable=True)
    last_detected_intent = Column(String, default="GENERAL")

class PatientRecord(Base):
    __tablename__ = "patient_records"
    
    id = Column(Integer, primary_key=True, index=True)
    asha_phone = Column(String, index=True, nullable=False)
    patient_name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    risk_status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)