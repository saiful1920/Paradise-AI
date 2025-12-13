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

from itinerary_service import ItineraryService
from demo_data import DemoDataManager
from video_service import VideoGenerationService
from video_database import VideoDatabase

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Travel Itinerary Generator")

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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

# Templates
templates = Jinja2Templates(directory="templates")

# Get API key
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
GOOGLE_MAPS_API_KEY= os.getenv("GOOGLE_MAPS_API_KEY")
OPEN_AI_API_KEY=os.getenv("OPENAI_API_KEY")
KIE_AI_API_KEY = os.getenv("KIE_AI_API_KEY")

# Initialize services
logger.info("🚀 Initializing services...")
demo_data_manager = DemoDataManager(GOOGLE_PLACES_API_KEY, GOOGLE_MAPS_API_KEY, OPEN_AI_API_KEY)
itinerary_service = ItineraryService(demo_data_manager, api_key=OPEN_AI_API_KEY)
video_service = VideoGenerationService(api_key=KIE_AI_API_KEY)
video_db = VideoDatabase()  # Initialize database
logger.info("✅ Services initialized successfully")

# Store active itineraries (in production, use database)
active_itineraries = {}
video_tasks = {}  # Store video generation tasks


# Pydantic Models
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


class ChatMessage(BaseModel):
    itinerary_id: str
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = []


class VideoGenerationRequest(BaseModel):
    itinerary_id: str
    user_photo_filename: str


# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the home page with the input form"""
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
        
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Generate unique filename
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = uploads_path / unique_filename
        
        # Save file
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
    """Create a new itinerary based on user input"""
    try:
        logger.info("="*80)
        logger.info(f"🌍 CREATING ITINERARY")
        logger.info("="*80)
        logger.info(f"📍 Destination: {request.destination}")
        logger.info(f"💰 Budget: ${request.budget}")
        logger.info(f"📅 Duration: {request.duration} days")
        logger.info(f"👥 Travelers: {request.travelers}")
        logger.info(f"✈️ Include Flights: {request.include_flights}")
        logger.info(f"🏨 Include Hotels: {request.include_hotels}")
        logger.info(f"🎯 Activity Level: {request.activity_preference}")
        logger.info("="*80)
        
        # Validate budget first
        logger.info("\n💵 Validating budget...")
        validation = await itinerary_service.validate_budget(
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
                    "current_budget": request.budget
                }
            )
        
        # Generate itinerary
        logger.info("\n🎨 Generating itinerary...")
        itinerary = await itinerary_service.generate_itinerary(
            destination=request.destination,
            budget=request.budget,
            duration=request.duration,
            travelers=request.travelers,
            activity_preference=request.activity_preference,
            include_flights=request.include_flights,
            include_hotels=request.include_hotels,
            user_location=request.user_location
        )
        
        # Store itinerary
        itinerary_id = str(uuid.uuid4())
        active_itineraries[itinerary_id] = itinerary
        
        logger.info(f"\n✅ Itinerary created successfully!")
        logger.info(f"🆔 Itinerary ID: {itinerary_id}")
        logger.info("="*80)
        
        return {
            "itinerary_id": itinerary_id,
            "itinerary": itinerary
        }
        
    except Exception as e:
        logger.error(f"\n❌ ERROR CREATING ITINERARY: {str(e)}")
        import traceback
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
    try:
        logger.info("="*80)
        logger.info(f"🎥 GENERATING VIDEO")
        logger.info(f"🆔 Itinerary ID: {request.itinerary_id}")
        logger.info(f"📸 User Photo: {request.user_photo_filename}")
        logger.info("="*80)
        
        if request.itinerary_id not in active_itineraries:
            raise HTTPException(status_code=404, detail="Itinerary not found")
        
        itinerary = active_itineraries[request.itinerary_id]
        
        # Get user photo URL
        user_photo_url = f"http://localhost:8001/uploads/{request.user_photo_filename}"
        
        # Generate video ID
        video_id = str(uuid.uuid4())
        
        # Store initial task info
        video_tasks[video_id] = {
            "status": "processing",
            "progress": 0,
            "total_days": len(itinerary["daily_activities"]),
            "completed_days": 0,
            "current_day": 0,
            "itinerary_id": request.itinerary_id,
            "created_at": datetime.now().isoformat(),
            "stage": "initializing",
            "message": "Starting video generation..."
        }
        
        # Start video generation in background
        asyncio.create_task(
            generate_video_background(
                video_id,
                user_photo_url,
                itinerary["daily_activities"],
                itinerary["destination"]["name"],
                itinerary["duration"],
                request.itinerary_id  # Pass itinerary_id
            )
        )
        
        logger.info(f"✅ Video generation started")
        logger.info(f"🆔 Video ID: {video_id}")
        logger.info("="*80)
        
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


async def generate_video_background(
    video_id: str,
    user_photo_url: str,
    daily_activities: List[Dict[str, Any]],
    destination: str,
    duration: int,
    itinerary_id: str
):
    """Background task to generate day-by-day videos and merge them"""
    try:
        logger.info(f"🎬 Starting background video generation for {video_id}")
        
        # Create database session
        video_db.create_session(
            video_id=video_id,
            itinerary_id=itinerary_id,
            destination=destination,
            total_days=duration,
            user_photo_url=user_photo_url
        )
        
        # Update status
        video_tasks[video_id]["status"] = "processing"
        video_tasks[video_id]["message"] = "Generating videos for each day..."
        video_tasks[video_id]["current_day"] = 0
        video_tasks[video_id]["progress"] = 0
        
        # Progress callback to update status and database
        def progress_callback(progress_data: Dict[str, Any]):
            # Update memory
            video_tasks[video_id].update({
                "current_day": progress_data.get("current_day", 0),
                "progress": progress_data.get("progress", 0),
                "current_stage": progress_data.get("current_stage", "Processing..."),
                "completed_days": progress_data.get("completed_days", 0),
                "message": progress_data.get("current_stage", "Processing...")
            })
            
            # Update database
            video_db.update_session(
                video_id=video_id,
                progress=progress_data.get("progress", 0),
                current_day=progress_data.get("current_day", 0),
                completed_days=progress_data.get("completed_days", 0),
                current_stage=progress_data.get("current_stage", "Processing...")
            )
            
            logger.info(f"📊 Progress update: {progress_data}")
        
        # Generate day-by-day videos and merge
        result = video_service.generate_full_itinerary_video(
            user_image_url=user_photo_url,
            destination=destination,
            duration=duration,
            daily_activities=daily_activities,
            model="veo3_fast",
            progress_callback=progress_callback,
            video_id=video_id,  # Pass video_id for database
            video_db=video_db   # Pass database
        )
        
        if result["success"]:
            # Video is already saved and ready
            video_url = result["video_url"]
            video_path = result.get("video_path")
            days_covered = result.get("days_covered", duration)
            
            # Update database
            video_db.update_session(
                video_id=video_id,
                status="completed",
                progress=100,
                final_video_url=video_url,
                final_video_path=video_path,
                completed_days=duration
            )
            
            # Update memory
            video_tasks[video_id].update({
                "status": "completed",
                "progress": 100,
                "video_url": video_url,
                "video_path": video_path,
                "completed_at": datetime.now().isoformat(),
                "days_covered": days_covered,
                "total_days": duration,
                "completed_days": duration,
                "message": f"Video complete! {days_covered} days merged into final video",
                "current_stage": "Complete!"
            })
            logger.info(f"✅ Video generation completed for {video_id}")
        else:
            error_msg = result.get("error", "Unknown error")
            
            # Update database
            video_db.update_session(
                video_id=video_id,
                status="failed",
                error_message=error_msg
            )
            
            # Update memory
            video_tasks[video_id].update({
                "status": "failed",
                "error": error_msg,
                "message": f"Video generation failed: {error_msg}"
            })
            logger.error(f"❌ Video generation failed for {video_id}")
            
    except Exception as e:
        logger.error(f"❌ Error in background video generation: {e}")
        import traceback
        traceback.print_exc()
        video_tasks[video_id].update({
            "status": "failed",
            "error": str(e),
            "message": f"Error: {str(e)}"
        })


@app.post("/api/reallocate-budget")
async def reallocate_budget(request: BudgetReallocationRequest):
    """Reallocate remaining budget to selected categories"""
    try:
        logger.info("="*80)
        logger.info(f"💰 REALLOCATING BUDGET")
        logger.info(f"🆔 Itinerary ID: {request.itinerary_id}")
        logger.info(f"📊 Selected Categories: {', '.join(request.selected_categories)}")
        logger.info("="*80)
        
        if request.itinerary_id not in active_itineraries:
            logger.warning(f"⚠️ Itinerary not found: {request.itinerary_id}")
            raise HTTPException(status_code=404, detail="Itinerary not found")
        
        current_itinerary = active_itineraries[request.itinerary_id]
        
        # Reallocate budget
        updated_budget = await itinerary_service.reallocate_budget(
            current_itinerary=current_itinerary,
            selected_categories=request.selected_categories
        )
        
        # Update stored itinerary
        active_itineraries[request.itinerary_id]["budget_breakdown"] = updated_budget
        
        logger.info("✅ Budget reallocated successfully")
        logger.info("="*80)
        
        return {
            "success": True,
            "budget_breakdown": updated_budget
        }
        
    except Exception as e:
        logger.error(f"❌ Error in reallocate_budget: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_with_ai(request: ChatMessage):
    """Handle chat messages for itinerary modifications"""
    try:
        logger.info("="*80)
        logger.info(f"💬 PROCESSING CHAT MESSAGE")
        logger.info(f"🆔 Itinerary ID: {request.itinerary_id}")
        logger.info("="*80)
        
        if request.itinerary_id not in active_itineraries:
            raise HTTPException(status_code=404, detail="Itinerary not found")
        
        current_itinerary = active_itineraries[request.itinerary_id]
        
        # Process chat message
        response = await itinerary_service.process_chat_message(
            message=request.message,
            current_itinerary=current_itinerary,
            conversation_history=request.conversation_history or []
        )
        
        # If modifications were made, update itinerary
        if response.get("modifications_made") and response.get("updated_itinerary"):
            active_itineraries[request.itinerary_id] = response["updated_itinerary"]
            logger.info("✅ Itinerary updated")
        
        logger.info("="*80)
        
        return {
            "response": response["message"],
            "modifications_made": response.get("modifications_made", False),
            "updated_itinerary": response.get("updated_itinerary"),
            "requires_confirmation": response.get("requires_confirmation", False),
            "proposed_changes": response.get("proposed_changes", {})
        }
        
    except Exception as e:
        logger.error(f"❌ Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info("🚀 Starting Travel Itinerary Generator API...")
    logger.info("📡 Server will be available at: http://0.0.0.0:8001")
    logger.info("="*80)
    uvicorn.run(app, host="0.0.0.0", port=8001)