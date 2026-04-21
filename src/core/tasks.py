import asyncio
import logging
from celery import Celery
from src.core.config import settings
from src.services.video_service import VideoGenerationService
from src.core.database import AsyncSessionLocal
from src.core.models import VideoTask, Itinerary
from sqlalchemy import select, update
import base64
import os
from datetime import datetime

celery_app = Celery(
    "travel_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,          
    task_soft_time_limit=3000,
)

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent video generation
video_semaphore = asyncio.Semaphore(settings.VIDEO_MAX_CONCURRENT)

@celery_app.task(bind=True, name="generate_video")
def generate_video(self, video_id: str, itinerary_id: str, user_photo_url: str, user_photo_filename: str):
    """
    Celery task to generate video.
    Updates VideoTask record in DB with progress and final result.
    """
    # Run async code in sync task
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_generate_video_async(self, video_id, itinerary_id, user_photo_url, user_photo_filename))

async def _generate_video_async(celery_task, video_id: str, itinerary_id: str, user_photo_url: str, user_photo_filename: str):
    async with video_semaphore:
        logger.info(f"🎬 Starting video generation task for {video_id}")

        # Get itinerary from DB
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Itinerary).where(Itinerary.id == itinerary_id))
            itinerary = result.scalar_one_or_none()
            if not itinerary:
                logger.error(f"Itinerary {itinerary_id} not found")
                return {"error": "Itinerary not found"}

            daily_activities = itinerary.daily_activities
            destination = itinerary.destination.get("name", "Unknown")
            duration = itinerary.duration

        # Initialize video service
        video_service = VideoGenerationService(api_key=settings.KIE_AI_API_KEY)

        # Progress callback to update DB
        def progress_callback(progress_data: dict):
            async def update_task():
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(VideoTask)
                        .where(VideoTask.id == video_id)
                        .values(
                            progress=progress_data.get("progress", 0),
                            current_day=progress_data.get("current_day", 0),
                            completed_days=progress_data.get("completed_days", 0),
                            stage=progress_data.get("current_stage", ""),
                            message=progress_data.get("message", ""),
                        )
                    )
                    await db.commit()
            asyncio.create_task(update_task())
       
        # Generate video
        result = await video_service.generate_full_itinerary_video(
            user_image_url=user_photo_url,
            destination=destination,
            duration=duration,
            daily_activities=daily_activities,
            model="veo3_fast",
            progress_callback=progress_callback,
            video_id=video_id,
            video_db=None,
        )

        # Final update in DB
        async with AsyncSessionLocal() as db:
            video_task = await db.get(VideoTask, video_id)
            if video_task:
                if result.get("success"):
                    video_task.status = "completed"
                    video_task.progress = 100
                    video_task.completed_at = datetime.now()   
                    video_task.video_url = result.get("video_url")
                    video_task.video_path = result.get("video_path")
                    # Convert video to base64 if needed
                    video_path = result.get("video_path")
                    if video_path and os.path.exists(video_path):
                        with open(video_path, "rb") as f:
                            video_task.video_base64 = base64.b64encode(f.read()).decode('utf-8')
                else:
                    video_task.status = "failed"
                    video_task.error = result.get("error", "Unknown error")
                await db.commit()

        return result