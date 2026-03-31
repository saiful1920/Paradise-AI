"""
Enhanced Travel Itinerary Generator API - Production Version

- Multi-city itinerary support
- Excursions, tours, and experiences
- Detailed budget breakdown with calculations
- Real-time chat modifications (persisted in DB)
- Recommended experiences section
- Database persistence (PostgreSQL)
- Redis caching & rate limiting
- Celery background tasks for video generation
"""

from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import uvicorn
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import json
import uuid
import asyncio
from pathlib import Path
import os
import time
from dotenv import load_dotenv
import logging
import shutil
import traceback
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from database import get_db, engine, Base
from models import Itinerary as ItineraryModel, ChatMessage, VideoTask, PendingModification, AccumulatedParams
from config import settings
from rate_limiter import limiter, rate_limit_exceeded_handler
import cache
from tasks import celery_app, generate_video

# Existing service imports
from itinerary_service import ItineraryService
from demo_data import DemoDataManager
from flight_data import AviasalesFlightFormatter

# Optional video service imports
try:
    from video_service import VideoGenerationService
    VIDEO_SERVICE_AVAILABLE = True
except ImportError:
    VIDEO_SERVICE_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("⚠️ Video service not available")

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Travel Itinerary Generator",
    description="Generate personalized travel itineraries with multi-city support, experiences, and detailed budget breakdowns",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Create necessary directories
static_path = Path("static")
static_path.mkdir(exist_ok=True)
uploads_path = Path("uploads")
uploads_path.mkdir(exist_ok=True)
videos_path = Path("videos")
videos_path.mkdir(exist_ok=True, parents=True)
templates_path = Path("templates")
templates_path.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

# Templates
templates = Jinja2Templates(directory="templates")

# Initialize services 
demo_data_manager = DemoDataManager(
    settings.GOOGLE_PLACES_API_KEY,
    settings.GOOGLE_MAPS_API_KEY,
    settings.OPENAI_API_KEY
)
itinerary_service = ItineraryService(
    demo_data_manager,
    api_key=settings.OPENAI_API_KEY
)
flight_data = AviasalesFlightFormatter(
    api_token=settings.FLIGHT_API_KEY,
    marker=settings.FLIGHT_AFFILIATE_MARKER
)

# Video service 
video_service = None
if VIDEO_SERVICE_AVAILABLE and settings.KIE_AI_API_KEY:
    try:
        video_service = VideoGenerationService(settings.KIE_AI_API_KEY)
        logger.info("✅ Video service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Video service initialization failed: {e}")

# Background task for cleaning up old videos
async def cleanup_videos_folder():
    """Background task: delete video files older than 1 hour, running every hour."""
    # Wait one hour before first cleanup
    await asyncio.sleep(3600)
    
    while True:
        try:
            videos_dir = Path("videos")
            if videos_dir.exists():
                now = time.time()
                deleted_count = 0
                for file in videos_dir.glob("*.mp4"):
                    try:
                        # Get modification time as float
                        file_mtime = os.path.getmtime(str(file))
                    except Exception as e:
                        logger.warning(f"⚠️ Could not get mtime for {file}: {e}")
                        continue
                    
                    # Delete if older than 1 hour
                    if now - file_mtime > 3600:
                        file.unlink()
                        deleted_count += 1
                        logger.info(f"🧹 Cleaned up old video: {file}")
                
                if deleted_count:
                    logger.info(f"✅ Video cleanup removed {deleted_count} old file(s)")
        except Exception as e:
            logger.error(f"❌ Error in video cleanup: {e}", exc_info=True)
        
        # Wait another hour before next run
        await asyncio.sleep(3600)

# Create database tables on startup 
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables created/verified")

    # Start background video cleanup
    asyncio.create_task(cleanup_videos_folder())
    logger.info("✅ Video cleanup task scheduled (first run in 1 hour)")

# Pydantic models for request validation
class ItineraryRequest(BaseModel):
    destination: str
    budget: float
    activity_preference: str
    include_flights: bool = False
    include_hotels: bool = False
    duration: int
    travelers: int
    user_location: Optional[str] = "New York"

class BudgetReallocationRequest(BaseModel):
    itinerary_id: str
    selected_categories: List[str]

class ChatMessageRequest(BaseModel):
    itinerary_id: str
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = []   

class VideoGenerationRequest(BaseModel):
    itinerary_id: str
    user_photo_filename: str

# Helper functions for DB interactions
async def get_itinerary_from_db(itinerary_id: str, db: AsyncSession) -> Optional[Dict]:
    """Fetch itinerary from DB and convert to dict."""
    result = await db.execute(select(ItineraryModel).where(ItineraryModel.id == itinerary_id))
    itinerary = result.scalar_one_or_none()
    if not itinerary:
        return None
    # Convert SQLAlchemy model to dict
    data = {
        "itinerary_id": itinerary.id,
        "user_location": itinerary.user_location,
        "destination": itinerary.destination,
        "duration": itinerary.duration,
        "travelers": itinerary.travelers,
        "total_budget": itinerary.total_budget,
        "activity_preference": itinerary.activity_preference,
        "include_flights": itinerary.include_flights,
        "include_hotels": itinerary.include_hotels,
        "main_title": itinerary.main_title,
        "trip_dates": itinerary.trip_dates,
        "daily_activities": itinerary.daily_activities,
        "budget_breakdown": itinerary.budget_breakdown,
        "recommended_experiences": itinerary.recommended_experiences,
        "hotel_recommendations": itinerary.hotel_recommendations,
        "restaurant_recommendations": itinerary.restaurant_recommendations,
        "updated_flights": itinerary.updated_flights,
        "local_transport": itinerary.local_transport,
        "attractions_summary": itinerary.attractions_summary,
        "created_at": itinerary.created_at.isoformat() if itinerary.created_at else None,
    }
    return data

async def save_itinerary_to_db(itinerary_data: Dict, db: AsyncSession) -> str:
    """Save itinerary dict to DB, return ID."""
    itinerary_id = itinerary_data.get("itinerary_id") or str(uuid.uuid4())
    # Extract fields that match model
    model_data = {
        "id": itinerary_id,
        "user_location": itinerary_data.get("user_location"),
        "destination": itinerary_data.get("destination"),
        "duration": itinerary_data.get("duration"),
        "travelers": itinerary_data.get("travelers"),
        "total_budget": itinerary_data.get("total_budget"),
        "activity_preference": itinerary_data.get("activity_preference"),
        "include_flights": itinerary_data.get("include_flights"),
        "include_hotels": itinerary_data.get("include_hotels"),
        "main_title": itinerary_data.get("main_title"),
        "trip_dates": itinerary_data.get("trip_dates"),
        "daily_activities": itinerary_data.get("daily_activities"),
        "budget_breakdown": itinerary_data.get("budget_breakdown"),
        "recommended_experiences": itinerary_data.get("recommended_experiences"),
        "hotel_recommendations": itinerary_data.get("hotel_recommendations"),
        "restaurant_recommendations": itinerary_data.get("restaurant_recommendations"),
        "updated_flights": itinerary_data.get("updated_flights"),
        "local_transport": itinerary_data.get("local_transport"),
        "attractions_summary": itinerary_data.get("attractions_summary"),
    }
    itinerary = ItineraryModel(**model_data)
    db.add(itinerary)
    await db.commit()
    return itinerary_id


# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/itinerary/{itinerary_id}", response_class=HTMLResponse)
async def view_itinerary(request: Request, itinerary_id: str, db: AsyncSession = Depends(get_db)):
    itinerary = await get_itinerary_from_db(itinerary_id, db)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return templates.TemplateResponse("itinerary.html", {
        "request": request,
        "itinerary_id": itinerary_id
    })

@app.get("/video/{video_id}", response_class=HTMLResponse)
async def view_video(request: Request, video_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VideoTask).where(VideoTask.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return templates.TemplateResponse("video.html", {
        "request": request,
        "video_id": video_id
    })

@app.post("/api/upload-photo")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")
async def upload_photo(request: Request, file: UploadFile = File(...)):
    try:
        logger.info(f"📤 Uploading photo: {file.filename}")
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = uploads_path / unique_filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"✅ Photo uploaded: {unique_filename}")
        return {
            "success": True,
            "filename": unique_filename,
            "url": f"/uploads/{unique_filename}"
        }
    except Exception as e:
        logger.error(f"❌ Error uploading photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/create-itinerary")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")
async def create_itinerary(
    request: Request,
    itinerary_req: ItineraryRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info("="*80)
        logger.info(f"🌍 CREATING ITINERARY for {itinerary_req.destination}")
        logger.info("="*80)

        # Validate budget
        validation = await itinerary_service.validate_budget(
            user_location=itinerary_req.user_location,
            destination=itinerary_req.destination,
            budget=itinerary_req.budget,
            duration=itinerary_req.duration,
            travelers=itinerary_req.travelers,
            include_flights=itinerary_req.include_flights,
            include_hotels=itinerary_req.include_hotels
        )

        if not validation["sufficient"]:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "insufficient_budget",
                    "message": validation["message"],
                    "minimum_budget": validation["minimum_budget"],
                    "current_budget": itinerary_req.budget,
                    "breakdown": validation.get("breakdown", {})
                }
            )

        # Generate itinerary
        itinerary = await itinerary_service.generate_itinerary(
            user_location=itinerary_req.user_location,
            destination=itinerary_req.destination,
            budget=itinerary_req.budget,
            duration=itinerary_req.duration,
            travelers=itinerary_req.travelers,
            activity_preference=itinerary_req.activity_preference,
            include_flights=itinerary_req.include_flights,
            include_hotels=itinerary_req.include_hotels
        )

        # Save to DB
        itinerary_id = await save_itinerary_to_db(itinerary, db)

        logger.info(f"✅ Itinerary created: {itinerary_id}")
        return {
            "itinerary_id": itinerary_id,
            "itinerary": itinerary
        }

    except Exception as e:
        logger.error(f"❌ ERROR: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/itinerary/{itinerary_id}")
async def get_itinerary(itinerary_id: str, db: AsyncSession = Depends(get_db)):
    itinerary = await get_itinerary_from_db(itinerary_id, db)
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itinerary

@app.post("/api/generate-video")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")
async def generate_video_endpoint(
    request: Request,
    video_req: VideoGenerationRequest,
    db: AsyncSession = Depends(get_db)
):
    if not VIDEO_SERVICE_AVAILABLE or not video_service:
        raise HTTPException(status_code=503, detail="Video service not available")

    try:
        # Verify itinerary exists
        itinerary = await get_itinerary_from_db(video_req.itinerary_id, db)
        if not itinerary:
            raise HTTPException(status_code=404, detail="Itinerary not found")

        video_id = str(uuid.uuid4())
        user_photo_url = f"http://localhost:8001/uploads/{video_req.user_photo_filename}"

        # Create video task record
        video_task = VideoTask(
            id=video_id,
            itinerary_id=video_req.itinerary_id,
            user_photo_filename=video_req.user_photo_filename,
            status="processing",
            progress=0,
            total_days=itinerary.get("duration", 0),
            stage="queued",
            message="Video generation queued"
        )
        db.add(video_task)
        await db.commit()

        # Enqueue Celery task (async)
        generate_video.delay(video_id, video_req.itinerary_id, user_photo_url, video_req.user_photo_filename)

        return {
            "success": True,
            "video_id": video_id,
            "message": "Video generation started"
        }

    except Exception as e:
        logger.error(f"❌ Error starting video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/video-status/{video_id}")
async def get_video_status(video_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VideoTask).where(VideoTask.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Return as dict 
    return {
        "status": video.status,
        "progress": video.progress,
        "total_days": video.total_days,
        "completed_days": video.completed_days,
        "current_day": video.current_day,
        "stage": video.stage,
        "message": video.message,
        "error": video.error,
        "video_url": video.video_url,
        "video_path": video.video_path,
        "video_base64": video.video_base64,
        "created_at": video.created_at.isoformat() if video.created_at else None,
        "completed_at": video.completed_at.isoformat() if video.completed_at else None,
    }

@app.post("/api/reallocate-budget")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")
async def reallocate_budget(
    request: Request,
    realloc_req: BudgetReallocationRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Fetch itinerary from DB
        itinerary = await get_itinerary_from_db(realloc_req.itinerary_id, db)
        if not itinerary:
            raise HTTPException(status_code=404, detail="Itinerary not found")

        # Reallocate 
        updated_budget = await itinerary_service.reallocate_budget(
            current_itinerary=itinerary,
            selected_categories=realloc_req.selected_categories
        )

        # Update DB
        await db.execute(
            update(ItineraryModel)
            .where(ItineraryModel.id == realloc_req.itinerary_id)
            .values(budget_breakdown=updated_budget)
        )
        await db.commit()

        return {"success": True, "budget_breakdown": updated_budget}

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")
async def chat_with_ai(
    request: Request,
    chat_req: ChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Fetch itinerary
        itinerary = await get_itinerary_from_db(chat_req.itinerary_id, db)
        if not itinerary:
            raise HTTPException(status_code=404, detail="Itinerary not found")

        # Load conversation history from DB
        history_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.itinerary_id == chat_req.itinerary_id)
            .order_by(ChatMessage.timestamp)
            .limit(20)
        )
        history_messages = history_result.scalars().all()
        conversation_history = [
            {"role": msg.role, "content": msg.content} for msg in history_messages
        ]

       # Save user message to DB
        response_data = await itinerary_service.process_chat_message(
            message=chat_req.message,
            current_itinerary=itinerary,
            conversation_history=conversation_history  
        )

        # If itinerary was updated, save it
        if response_data.get("modifications_made") and response_data.get("updated_itinerary"):
            updated_itinerary = response_data["updated_itinerary"]
            updated_itinerary["itinerary_id"] = chat_req.itinerary_id
            await db.execute(
                update(ItineraryModel)
                .where(ItineraryModel.id == chat_req.itinerary_id)
                .values(
                    daily_activities=updated_itinerary.get("daily_activities"),
                    budget_breakdown=updated_itinerary.get("budget_breakdown"),
                    recommended_experiences=updated_itinerary.get("recommended_experiences"),
                    hotel_recommendations=updated_itinerary.get("hotel_recommendations"),
                    restaurant_recommendations=updated_itinerary.get("restaurant_recommendations"),
                    updated_flights=updated_itinerary.get("updated_flights")

                )
            )

        await db.commit()

        # Return response, including conversation history from DB (optional)
        return {
            "response": response_data.get("response", ""),
            "modifications_made": response_data.get("modifications_made", False),
            "updated_itinerary": response_data.get("updated_itinerary"),
            "requires_confirmation": response_data.get("requires_confirmation", False),
            "proposed_changes": response_data.get("proposed_changes", {}),
            "modification_type": response_data.get("modification_type", "none"),
            "confidence": response_data.get("confidence", 0.0),
            "conversation_history": await get_chat_history_from_db(chat_req.itinerary_id, db)
        }

    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def get_chat_history_from_db(itinerary_id: str, db: AsyncSession) -> List[Dict]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.itinerary_id == itinerary_id)
        .order_by(ChatMessage.timestamp)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()} for m in messages]

@app.get("/api/chat-history/{itinerary_id}")
async def get_chat_history(itinerary_id: str, db: AsyncSession = Depends(get_db)):
    history = await get_chat_history_from_db(itinerary_id, db)
    return {
        "itinerary_id": itinerary_id,
        "conversation_history": history,
        "message_count": len(history)
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "google_places": bool(settings.GOOGLE_PLACES_API_KEY),
            "openai": bool(settings.OPENAI_API_KEY),
            "flights": bool(settings.FLIGHT_API_KEY),
            "video": VIDEO_SERVICE_AVAILABLE and bool(video_service),
            "database": True,
            "redis": True
        }
    }

if __name__ == "__main__":
    logger.info("🚀 Starting Travel Itinerary Generator API...")
    logger.info("📡 Server available at: http://0.0.0.0:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)