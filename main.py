"""
Enhanced Travel Itinerary Generator API

Features:
- Multi-city itinerary support
- Excursions, tours, and experiences
- Detailed budget breakdown with calculations
- Real-time chat modifications
- Recommended experiences section
"""

from fastapi import FastAPI, HTTPException, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import json
import uuid
import asyncio
from pathlib import Path
import os
from dotenv import load_dotenv
import logging
import shutil
import traceback
import base64

from itinerary_service import ItineraryService
from demo_data import DemoDataManager
from flight_data import AviasalesFlightFormatter

# Optional video service imports
try:
    from video_service import VideoGenerationService
    from video_database import VideoDatabase
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Get API keys
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FLIGHT_API_KEY = os.getenv("FLIGHT_API_KEY")
FLIGHT_AFFILIATE_MARKER = os.getenv("FLIGHT_AFFILIATE_MARKER")
KIE_AI_API_KEY = os.getenv("KIE_AI_API_KEY")

# Initialize services
logger.info("🚀 Initializing services...")
demo_data_manager = DemoDataManager(GOOGLE_PLACES_API_KEY, GOOGLE_MAPS_API_KEY, OPENAI_API_KEY)
itinerary_service = ItineraryService(demo_data_manager, api_key=OPENAI_API_KEY)
flight_data = AviasalesFlightFormatter(api_token=FLIGHT_API_KEY, marker=FLIGHT_AFFILIATE_MARKER)

# Video services (optional)
video_service = None
video_db = None
if VIDEO_SERVICE_AVAILABLE and KIE_AI_API_KEY:
    try:
        video_service = VideoGenerationService(KIE_AI_API_KEY)
        video_db = VideoDatabase()
        logger.info("✅ Video service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Video service initialization failed: {e}")

logger.info("✅ Services initialized successfully")

# Storage (in production, use database)
active_itineraries = {}
video_tasks = {}


# =============================================================================
# Pydantic Models
# =============================================================================

class ItineraryRequest(BaseModel):
    destination: str = Field(..., description="Destination (city, country, or multiple cities)")
    budget: float = Field(..., gt=0, description="Total budget in USD")
    activity_preference: str = Field(..., description="Activity level: relaxed, moderate, or high")
    include_flights: bool = Field(default=False, description="Include flight costs")
    include_hotels: bool = Field(default=False, description="Include hotel costs")
    duration: int = Field(..., ge=1, le=30, description="Trip duration in days")
    travelers: int = Field(..., ge=1, le=20, description="Number of travelers")
    current_location: Optional[str] = Field(default="New York", description="User's departure city")


class BudgetReallocationRequest(BaseModel):
    itinerary_id: str
    selected_categories: List[str]


class ChatMessage(BaseModel):
    itinerary_id: str
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = []


class VideoGenerationRequest(BaseModel):
    itinerary_id: str
    user_photo_filename: str


class DayModificationRequest(BaseModel):
    """Request to modify a specific day's activity"""
    itinerary_id: str
    day: int = Field(..., ge=1, description="Day number to modify")
    slot: str = Field(..., description="Slot to modify: morning, afternoon, evening, lunch, dinner")
    new_activity: Dict[str, Any] = Field(..., description="New activity details")


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the home page"""
    logger.info("📄 Serving home page")
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/itinerary/{itinerary_id}", response_class=HTMLResponse)
async def view_itinerary(request: Request, itinerary_id: str):
    """Serve the itinerary page"""
    if itinerary_id not in active_itineraries:
        logger.warning(f"⚠️ Itinerary not found: {itinerary_id}")
        raise HTTPException(status_code=404, detail="Itinerary not found")
    
    logger.info(f"📄 Serving itinerary page: {itinerary_id}")
    return templates.TemplateResponse("itinerary.html", {
        "request": request,
        "itinerary_id": itinerary_id
    })


@app.get("/video/{video_id}", response_class=HTMLResponse)
async def view_video(request: Request, video_id: str):
    """Serve the video display page"""
    if video_id not in video_tasks:
        logger.warning(f"⚠️ Video not found: {video_id}")
        raise HTTPException(status_code=404, detail="Video not found")
    
    logger.info(f"📄 Serving video page: {video_id}")
    return templates.TemplateResponse("video.html", {
        "request": request,
        "video_id": video_id
    })


@app.post("/api/upload-photo")
async def upload_photo(file: UploadFile = File(...)):
    """Upload user photo for video generation"""
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
async def create_itinerary(request: ItineraryRequest):
    """
    Create a new itinerary based on user input.
    
    Enhanced to support:
    - Multi-city trips (country names or multiple cities)
    - Experiences and tours
    - Detailed budget breakdowns
    """
    try:
        logger.info("=" * 80)
        logger.info(f"🌍 CREATING ITINERARY")
        logger.info("=" * 80)
        logger.info(f"📍 Destination: {request.destination}")
        logger.info(f"💰 Budget: ${request.budget}")
        logger.info(f"📅 Duration: {request.duration} days")
        logger.info(f"👥 Travelers: {request.travelers}")
        logger.info(f"✈️ Include Flights: {request.include_flights}")
        logger.info(f"🏨 Include Hotels: {request.include_hotels}")
        logger.info(f"🎯 Activity Level: {request.activity_preference}")
        logger.info(f"📍 User Location: {request.current_location}")
        logger.info("=" * 80)
        
        # Validate budget
        logger.info("\n💵 Validating budget...")
        validation = await itinerary_service.validate_budget(
            current_location=request.current_location,
            destination=request.destination,
            budget=request.budget,
            duration=request.duration,
            travelers=request.travelers,
            include_flights=request.include_flights,
            include_hotels=request.include_hotels
        )
        
        logger.info(f"✅ Budget validation: {validation['sufficient']}")
        
        if not validation["sufficient"]:
            logger.warning(f"❌ Insufficient budget. Minimum required: ${validation['minimum_budget']}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "insufficient_budget",
                    "message": validation["message"],
                    "minimum_budget": validation["minimum_budget"],
                    "current_budget": request.budget,
                    "breakdown": validation.get("breakdown", {})
                }
            )
        
        # Generate itinerary
        logger.info("\n🎨 Generating itinerary...")
        itinerary = await itinerary_service.generate_itinerary(
            current_location=request.current_location,
            destination=request.destination,
            budget=request.budget,
            duration=request.duration,
            travelers=request.travelers,
            activity_preference=request.activity_preference,
            include_flights=request.include_flights,
            include_hotels=request.include_hotels
        )
        
        # Store itinerary
        itinerary_id = str(uuid.uuid4())
        active_itineraries[itinerary_id] = itinerary
        
        logger.info(f"\n✅ Itinerary created successfully!")
        logger.info(f"🆔 Itinerary ID: {itinerary_id}")
        logger.info(f"🏙️ Cities: {itinerary['destination'].get('cities', [])}")
        logger.info("=" * 80)
        
        return {
            "itinerary_id": itinerary_id,
            "itinerary": itinerary
        }
        
    except Exception as e:
        logger.error(f"\n❌ ERROR CREATING ITINERARY: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/itinerary/{itinerary_id}")
async def get_itinerary(itinerary_id: str):
    """Get an existing itinerary"""
    if itinerary_id not in active_itineraries:
        logger.warning(f"⚠️ Itinerary not found: {itinerary_id}")
        raise HTTPException(status_code=404, detail="Itinerary not found")
    
    logger.info(f"📤 Returning itinerary: {itinerary_id}")
    return active_itineraries[itinerary_id]


@app.post("/api/generate-video")
async def generate_video(request: VideoGenerationRequest):
    """Start video generation for itinerary"""
    if not VIDEO_SERVICE_AVAILABLE or not video_service:
        raise HTTPException(status_code=503, detail="Video service not available")
    
    try:
        logger.info("=" * 80)
        logger.info(f"🎥 GENERATING VIDEO")
        logger.info(f"🆔 Itinerary ID: {request.itinerary_id}")
        logger.info(f"📸 User Photo: {request.user_photo_filename}")
        logger.info("=" * 80)
        
        if request.itinerary_id not in active_itineraries:
            raise HTTPException(status_code=404, detail="Itinerary not found")
        
        itinerary = active_itineraries[request.itinerary_id]
        user_photo_url = f"http://localhost:8001/uploads/{request.user_photo_filename}"
        video_id = str(uuid.uuid4())
        
        video_tasks[video_id] = {
            "status": "processing",
            "progress": 0,
            "total_days": len(itinerary.get("daily_activities", [])),
            "completed_days": 0,
            "current_day": 0,
            "itinerary_id": request.itinerary_id,
            "created_at": datetime.now().isoformat(),
            "stage": "initializing",
            "message": "Starting video generation..."
        }
        
        # Start background task
        asyncio.create_task(
            generate_video_background(
                video_id,
                user_photo_url,
                itinerary.get("daily_activities", []),
                itinerary["destination"]["name"],
                itinerary["duration"],
                request.itinerary_id
            )
        )
        
        logger.info(f"✅ Video generation started: {video_id}")
        
        return {
            "success": True,
            "video_id": video_id,
            "message": "Video generation started"
        }
        
    except Exception as e:
        logger.error(f"❌ Error starting video generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/video-status/{video_id}")
async def get_video_status(video_id: str):
    """Get video generation status"""
    if video_id not in video_tasks:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return video_tasks[video_id]


@app.post("/api/reallocate-budget")
async def reallocate_budget(request: BudgetReallocationRequest):
    """Reallocate budget - FIXED"""
    try:
        logger.info(f"💰 Reallocating budget for {request.itinerary_id}")
        
        if request.itinerary_id not in active_itineraries:
            raise HTTPException(status_code=404, detail="Itinerary not found")
        
        current_itinerary = active_itineraries[request.itinerary_id]
        
        # Use fixed reallocation method
        updated_budget = await itinerary_service.reallocate_budget(
            current_itinerary=current_itinerary,
            selected_categories=request.selected_categories
        )
        
        # Update stored itinerary
        active_itineraries[request.itinerary_id]["budget_breakdown"] = updated_budget
        
        logger.info("✅ Budget reallocated successfully")
        
        return {
            "success": True,
            "budget_breakdown": updated_budget
        }
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_with_ai(request: ChatMessage):
    """Chat endpoint - with intelligent bot"""
    try:
        logger.info(f"💬 Chat message from {request.itinerary_id}")
        
        if request.itinerary_id not in active_itineraries:
            raise HTTPException(status_code=404, detail="Itinerary not found")
        
        current_itinerary = active_itineraries[request.itinerary_id]
        
        response = await itinerary_service.process_chat_message(
            message=request.message,
            current_itinerary=current_itinerary,
            conversation_history=request.conversation_history or []
        )
        
        # Update itinerary if modified
        if response.get("modifications_made") and response.get("updated_itinerary"):
            active_itineraries[request.itinerary_id] = response["updated_itinerary"]
            logger.info("✅ Itinerary updated from chat")
        
        return {
            "response": response.get("response", ""),
            "modifications_made": response.get("modifications_made", False),
            "updated_itinerary": response.get("updated_itinerary"),
            "requires_confirmation": response.get("requires_confirmation", False),
            "proposed_changes": response.get("proposed_changes", {}),
            "modification_type": response.get("modification_type", "none"),
            "confidence": response.get("confidence", 0.0)
        }
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "google_places": bool(GOOGLE_PLACES_API_KEY),
            "openai": bool(OPENAI_API_KEY),
            "flights": bool(FLIGHT_API_KEY),
            "video": VIDEO_SERVICE_AVAILABLE and bool(video_service)
        }
    }


# =============================================================================
# Background Tasks
# =============================================================================

async def generate_video_background(
    video_id: str,
    user_photo_url: str,
    daily_activities: List[Dict[str, Any]],
    destination: str,
    duration: int,
    itinerary_id: str
):
    """Background task for video generation"""
    if not VIDEO_SERVICE_AVAILABLE or not video_service:
        video_tasks[video_id]["status"] = "failed"
        video_tasks[video_id]["error"] = "Video service not available"
        return
    
    try:
        logger.info(f"🎬 Starting background video generation for {video_id}")
        
        # Create database session if available
        if video_db:
            video_db.create_session(
                video_id=video_id,
                itinerary_id=itinerary_id,
                destination=destination,
                total_days=duration,
                user_photo_url=user_photo_url
            )
        
        video_tasks[video_id]["status"] = "processing"
        video_tasks[video_id]["message"] = "Generating videos for each day..."
        
        def progress_callback(progress_data: Dict[str, Any]):
            video_tasks[video_id].update({
                "current_day": progress_data.get("current_day", 0),
                "progress": progress_data.get("progress", 0),
                "current_stage": progress_data.get("current_stage", "Processing..."),
                "completed_days": progress_data.get("completed_days", 0),
                "message": progress_data.get("current_stage", "Processing...")
            })
            
            if video_db:
                video_db.update_session(
                    video_id=video_id,
                    progress=progress_data.get("progress", 0),
                    current_day=progress_data.get("current_day", 0),
                    completed_days=progress_data.get("completed_days", 0),
                    current_stage=progress_data.get("current_stage", "Processing...")
                )
        
        result = await video_service.generate_full_itinerary_video(
            user_image_url=user_photo_url,
            destination=destination,
            duration=duration,
            daily_activities=daily_activities,
            model="veo3_fast",
            progress_callback=progress_callback,
            video_id=video_id,
            video_db=video_db
        )
        
        if result.get("success"):
            # Convert video to base64
            video_path = result.get("video_path")
            video_base64 = None
            
            if video_path and os.path.exists(video_path):
                try:
                    logger.info(f"📦 Converting video to base64: {video_path}")
                    with open(video_path, "rb") as video_file:
                        video_bytes = video_file.read()
                        video_base64 = base64.b64encode(video_bytes).decode('utf-8')
                    logger.info(f"✅ Video converted to base64 successfully")
                except Exception as e:
                    logger.error(f"❌ Error converting video to base64: {e}")
            
            video_tasks[video_id].update({
                "status": "completed",
                "progress": 100,
                "itinerary_id": itinerary_id,  
                "video_id": video_id, 
                "completed_at": datetime.now().isoformat(),
                "days_covered": result.get("days_covered", duration),
                "message": "Video complete!",
                "video_url": result.get("video_url"),
                "video_path": result.get("video_path"),
                "video_base64": video_base64
            })
            logger.info(f"✅ Video generation completed for {video_id}")
        else:
            video_tasks[video_id].update({
                "status": "failed",
                "error": result.get("error", "Unknown error"),
                "itinerary_id": itinerary_id,
                "video_id": video_id,
                "message": f"Failed: {result.get('error', 'Unknown error')}"
            })
            logger.error(f"❌ Video generation failed for {video_id}")
            
    except Exception as e:
        logger.error(f"❌ Error in background video generation: {e}")
        traceback.print_exc()
        video_tasks[video_id].update({
            "status": "failed",
            "error": str(e),
            "itinerary_id": itinerary_id,
            "video_id": video_id,
            "message": f"Error: {str(e)}"
        })

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    logger.info("🚀 Starting Travel Itinerary Generator API...")
    logger.info("📡 Server will be available at: http://0.0.0.0:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)