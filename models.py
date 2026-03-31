from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Itinerary(Base):
    __tablename__ = "itineraries"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_location = Column(String, nullable=True)
    destination = Column(JSON, nullable=False)          
    duration = Column(Integer, nullable=False)
    travelers = Column(Integer, nullable=False)
    total_budget = Column(Float, nullable=False)
    activity_preference = Column(String, nullable=False)
    include_flights = Column(Boolean, default=False)
    include_hotels = Column(Boolean, default=False)
    main_title = Column(String)
    trip_dates = Column(String)
    daily_activities = Column(JSON)                     
    budget_breakdown = Column(JSON)                    
    recommended_experiences = Column(JSON)
    hotel_recommendations = Column(JSON)
    restaurant_recommendations = Column(JSON)
    updated_flights = Column(JSON)
    local_transport = Column(JSON)
    attractions_summary = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    itinerary_id = Column(String, ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    role = Column(String)         
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class VideoTask(Base):
    __tablename__ = "video_tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    itinerary_id = Column(String, ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    user_photo_filename = Column(String)
    status = Column(String)         
    progress = Column(Integer, default=0)
    total_days = Column(Integer)
    completed_days = Column(Integer, default=0)
    current_day = Column(Integer, default=0)
    stage = Column(String)
    message = Column(Text)
    error = Column(Text)
    video_url = Column(String)
    video_path = Column(String)
    video_base64 = Column(Text)     
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

class PendingModification(Base):
    __tablename__ = "pending_modifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    itinerary_id = Column(String, ForeignKey("itineraries.id", ondelete="CASCADE"), index=True, unique=True)
    modifications = Column(JSON)
    summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AccumulatedParams(Base):
    __tablename__ = "accumulated_params"

    id = Column(String, primary_key=True, default=generate_uuid)
    itinerary_id = Column(String, ForeignKey("itineraries.id", ondelete="CASCADE"), index=True, unique=True)
    params = Column(JSON)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())