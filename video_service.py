"""
Video Generation Service using KIE AI API (Google Veo 3.1)

CINEMATIC TRAVEL VIDEO WITH INTELLIGENT TIMELINE:
- Videos show the traveler from uploaded photo doing actual itinerary activities
- Cinematic quality with smooth transitions and natural lighting
- Intelligent time allocation based on activity visual appeal
- Morning/Afternoon/Evening flow with appropriate moods
- Temporary file storage with automatic cleanup
- Maximum 7 days of video generation
"""

import os
import time
import requests
import logging
import json
import tempfile
import shutil
import atexit
import uuid
import base64
from typing import Dict, List, Optional, Any, Callable
from moviepy.editor import VideoFileClip, concatenate_videoclips

logger = logging.getLogger(__name__)

# Maximum days for video generation
MAX_VIDEO_DAYS = 7

# Temporary directory for session files
TEMP_VIDEO_DIR = tempfile.mkdtemp(prefix="travel_videos_")
TEMP_UPLOAD_DIR = tempfile.mkdtemp(prefix="travel_uploads_")


def cleanup_temp_directories():
    """Cleanup temporary directories on exit."""
    for temp_dir in [TEMP_VIDEO_DIR, TEMP_UPLOAD_DIR]:
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"🧹 Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup {temp_dir}: {e}")


# Register cleanup on program exit
atexit.register(cleanup_temp_directories)


class VideoGenerationService:
    """Service for generating cinematic travel videos matching actual itinerary activities"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.kie.ai/api/v1/veo"
        self.upload_base_url = "https://kieai.redpandaai.co"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.temp_files: List[str] = []  # Track temp files for this instance

    def _track_temp_file(self, filepath: str):
        """Track a temporary file for cleanup."""
        self.temp_files.append(filepath)

    def cleanup_session_files(self):
        """Cleanup all temporary files created in this session."""
        for filepath in self.temp_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"🧹 Removed temp file: {filepath}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to remove {filepath}: {e}")
        self.temp_files.clear()

    def upload_file_to_kie(self, local_file_path: str) -> Optional[str]:
        """Upload a local file to KIE AI and get a public URL."""
        try:
            if not os.path.exists(local_file_path):
                logger.error(f"❌ File not found: {local_file_path}")
                return None

            filename = os.path.basename(local_file_path)
            logger.info(f"📤 Uploading file to KIE AI: {filename}")

            with open(local_file_path, 'rb') as f:
                files = {'file': (filename, f, 'image/jpeg')}
                data = {'uploadPath': 'travel-videos'}
                headers = {"Authorization": f"Bearer {self.api_key}"}

                response = requests.post(
                    f"{self.upload_base_url}/api/file-stream-upload",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=30
                )

            if not response.ok:
                logger.error(f"❌ Upload failed: {response.status_code}")
                return None

            result = response.json()

            if result.get("code") != 200:
                logger.error(f"❌ Upload API error: {result.get('msg')}")
                return None

            data = result.get("data", {})
            file_url = (data.get("downloadUrl") or data.get("url") or
                       data.get("fileUrl") or data.get("file_url"))

            if file_url:
                logger.info(f"✅ File uploaded: {file_url}")
            return file_url

        except Exception as e:
            logger.error(f"❌ Upload exception: {e}")
            return None

    async def generate_activity_matched_prompt(
        self,
        day_num: int,
        total_days: int,
        day_activities: Dict[str, Any],
        destination: str
    ) -> str:
        """
        Generate prompt in exact format: 
        "Create a cinematic 8-second travel video... throughout.
        0-Xs | Time – Place (Mood) Description"
        
        Focuses on enjoyable moments and tour clip feel.
        """
        
        # Extract ACTUAL activities
        day_title = day_activities.get("title", f"Day {day_num} in {destination}")
        day_text = f"Day {day_num} – {day_title}"
        morning = day_activities.get("morning", {})
        afternoon = day_activities.get("afternoon", {})
        evening = day_activities.get("evening", {})
        
        morning_name = morning.get("name", "Morning location")
        morning_desc = morning.get("description", "exploring quietly")
        afternoon_name = afternoon.get("name", "Afternoon location")
        afternoon_desc = afternoon.get("description", "discovering things")
        evening_name = evening.get("name", "Evening location")
        evening_desc = evening.get("description", "enjoying the atmosphere")

        prompt = f"""Create an 8-second cinematic travel reel–style vlog video.

        ABSOLUTE TIMING RULE (NON-NEGOTIABLE):
        - The video must follow the time ranges EXACTLY as written.
        - Do NOT shift, compress, extend, or overlap any segment.
        - Do NOT skip any segment.
  
        TRAVELER IDENTITY (STRICT – SINGLE OR MULTIPLE PEOPLE):
        - Use ALL people visible in the reference image as the ONLY travelers.
        - If the reference image contains multiple people, ALL of them must appear together throughout the video.
        - Do NOT add, remove, merge, duplicate, or replace any person.
        - Maintain exact identity consistency for EACH person individually:
        - same facial structure, skin tone, hairstyle, hair color
        - same body shape, height, and proportions
        - same gender, ethnicity, and age group
        - Clothing must remain realistic and consistent for each person.
        - No beautification, no stylization, no face reshaping.
        - No age changes, no smoothing, no artificial enhancements.
        - Natural human motion only.
        - No exaggerated expressions or forced emotions.

        GROUP BEHAVIOR RULES:
        - The travelers behave as a natural group (friends, family, or companions).
        - Group spacing and interaction must feel realistic and relaxed.
        - No posing for camera, no influencer-style gestures.
        - No one person should disappear or dominate scenes unnaturally.
        - All travelers must remain visible when contextually reasonable.

        IMPORTANT (Veo 3 Guidance):
        - Automatically select activities based on the visible environment and location type
        - Activities must feel LOCATION-AWARE and CONTEXT-DRIVEN
        - Avoid repetitive walking or running-focused actions
        - No jogging, no rushing, no staged poses
        - Actions should feel naturally motivated by surroundings
        - Activities must be safe, realistic, and culturally appropriate
        - No extreme actions, no adult or sensitive content

        Overall Style:
        Cinematic short travel reel, realistic, immersive, and naturally fun.
        Smooth transitions, stable camera, high-quality natural lighting.
        Authentic exploration, subtle enjoyment, and quiet discovery.
        Scene pacing should match upbeat but relaxed travel music.
        Clean cuts with a loop-friendly ending.

        The video should show SAFE, FAMILY-FRIENDLY, and LOCATION-APPROPRIATE activities only.

        0.0–1.0s | TITLE CARD (TEXT-ONLY FRAME)
        HARD RULE:
        This segment is a CLEAN TITLE CARD, NOT a cinematic scene.

        - Solid or lightly blurred neutral background ONLY
        - NO environment details
        - NO depth of field effects
        - NO camera motion
        - NO objects
        - NO people

        TEXT (CRITICAL):
        Render EXACT string:
        "{day_text}"

        STRICT:
        - Exact match (character-by-character)
        - No extra text
        - No paraphrasing
        - No styling changes

        STYLE:
        - Centered
        - Large, bold sans-serif
        - High contrast
        - Completely static (no animation, no fade, no motion)

        FAIL IF:
        - Any extra words appear
        - Text is incorrect
        - Background is complex

        1.0–3s | Morning – {morning_name} (Observational & Immersive)
        The SAME group of travelers {morning_desc}, engaging with the environment in a location-aware way:
        - observing architecture, landscapes, or cultural details
        - pausing to admire views, signage, or surroundings
        - touching textures (walls, railings, leaves)
        - interacting lightly with textures (railings, stone, plants, displays)
        - standing, leaning, or slowly shifting position rather than continuous walking
        Expression: neutral, focused, naturally curious (no forced smiles).
        Lighting: soft natural morning light.
        Camera: stabilized medium or wide shot with gentle motion.

        3–6.8s | Afternoon – {afternoon_name} (Fun & Active Exploration)
        The SAME group of travelers {afternoon_desc}, doing activities motivated by the location, such as:
        - Physical activities dependent on location (hiking, biking, water sports, etc.)
        - Exploring landmarks, trying activities, moving between places
        - Experiencing local attractions (museums, parks, viewpoints)
        - light, non-repetitive movement (no running or constant walking loops)
        Expression: focused excitement, visible enjoyment (no forced smiles).
        Lighting: bright daylight with clear details and vibrant tones.
        Camera: dynamic follow shot, side pan, or smooth cinematic cut.

        6.8–8s | Evening – {evening_name} (Atmospheric & Reflective)
        The SAME group of travelers {evening_desc}, engaging in evening activities that naturally
        fit the location:
        - enjoying local food (non-alcoholic, family-friendly), cafes, or markets
        - engaging with local culture (music, art, performances)
        - participating in community events or gatherings
        - sitting at a cozy cafe or restaurant
        - standing or slowly moving through softly lit streets or viewpoints
        - relaxing at scenic spots
        - Park visits
        - observing city lights, sunset, or night scenery
        - relaxed, grounded body language
        Expression: content, reflective, quietly happy.
        Lighting: golden hour or cinematic night ambience.
        Camera: smooth, stable motion ending on a still, loopable frame.

        End with a steady cinematic frame suitable for a seamless viral travel reel loop.
        """

        return prompt

    async def generate_full_itinerary_video(
        self,
        user_image_url: str,
        destination: str,
        duration: int,
        daily_activities: List[Dict[str, Any]],
        video_id: Optional[str] = None,
        model: str = "veo3_fast",
        progress_callback: Optional[Callable] = None,
        video_db: Optional[Any] = None   
    ) -> Dict[str, Any]:
        """
        Generate cinematic travel videos matching actual itinerary activities.

        This method is now a pure async function; it does not start background tasks.
        It returns the result directly. Progress updates are sent via callback.

        Args:
            user_image_url: URL or path to user's reference photo
            destination: Travel destination name
            duration: Number of days (max 7)
            daily_activities: List of day activities
            video_id: Unique identifier for this video generation
            model: AI model to use
            progress_callback: Optional callback for progress updates
            video_db: Ignored (kept for backward compatibility)

        Returns:
            Dict with success status, video URL, and metadata
        """

        # Enforce maximum days limit
        if duration > MAX_VIDEO_DAYS:
            logger.warning(f"⚠️ Duration {duration} exceeds max {MAX_VIDEO_DAYS}. Limiting to {MAX_VIDEO_DAYS} days.")
            duration = MAX_VIDEO_DAYS

        # Generate video_id if not provided
        if not video_id:
            video_id = str(uuid.uuid4())[:8]

        logger.info("="*80)
        logger.info("🎥 GENERATING CINEMATIC TRAVEL VIDEO")
        logger.info(f"📍 Destination: {destination}")
        logger.info(f"📅 Duration: {duration} days (max {MAX_VIDEO_DAYS})")
        logger.info(f"🆔 Video ID: {video_id}")
        logger.info("="*80)

        # Upload user photo if localhost
        if user_image_url.startswith("http://localhost") or user_image_url.startswith("http://127.0.0.1"):
            logger.info("🔄 Uploading user photo...")
            filename = user_image_url.split("/uploads/", 1)[-1]
            local_path = f"uploads/{filename}"

            public_url = self.upload_file_to_kie(local_path)
            if public_url:
                user_image_url = public_url
                self._track_temp_file(local_path)
            else:
                return {"success": False, "error": "Failed to upload user photo"}

        day_video_paths = []

        for day_num in range(1, duration + 1):
            logger.info("="*60)
            logger.info(f"🎬 DAY {day_num} - Creating cinematic travel video")
            logger.info("="*60)

            if progress_callback:
                progress_callback({
                    "current_day": day_num,
                    "total_days": duration,
                    "progress": int((day_num - 1) / duration * 90),
                    "current_stage": f"🎬 Creating Day {day_num} cinematic video...",
                    "completed_days": day_num - 1
                })

            # Get this day's actual activities
            day_idx = day_num - 1
            day_activities_data = daily_activities[day_idx] if day_idx < len(daily_activities) else {}

            # Generate cinematic prompt
            try:
                matched_prompt = await self.generate_activity_matched_prompt(
                    day_num=day_num,
                    total_days=duration,
                    day_activities=day_activities_data,
                    destination=destination
                )
            except Exception as e:
                logger.error(f"❌ Error generating prompt: {e}")
                continue

            logger.info(f"📝 Cinematic Prompt: {matched_prompt[:500]}...")

            # Generate video
            result = self._generate_video_with_images(
                prompt=matched_prompt,
                image_urls=[user_image_url],
                model=model,
                destination=destination,
                duration=1
            )

            if not result["success"]:
                logger.error(f"❌ Day {day_num} video failed: {result.get('error')}")
                continue

            task_id = result["task_id"]
            logger.info(f"⏳ Rendering Day {day_num} cinematic video...")

            video_result = self.wait_for_video(task_id, max_wait_time=600)

            if not video_result["success"]:
                logger.error(f"❌ Day {day_num} video failed: {video_result.get('error')}")
                continue

            video_url = video_result.get("video_url")
            if not video_url:
                logger.error(f"❌ No video URL for Day {day_num}")
                continue

            # Save day video to temp directory
            output_filename = f"day_{day_num}_{destination.replace(' ', '_')}_{video_id}.mp4"
            output_path = os.path.join(TEMP_VIDEO_DIR, output_filename)

            if self.download_video(video_url, output_path):
                day_video_paths.append(output_path)
                self._track_temp_file(output_path)
                logger.info(f"✅ Day {day_num} cinematic video ready!")
            else:
                logger.error(f"❌ Failed to download Day {day_num} video")

        # Merge videos
        if not day_video_paths:
            return {"success": False, "error": "No day videos generated"}

        logger.info("="*60)
        logger.info(f"🎬 Merging {len(day_video_paths)} day videos into final cinematic piece...")
        logger.info("="*60)

        if progress_callback:
            progress_callback({
                "current_day": duration,
                "total_days": duration,
                "progress": 92,
                "current_stage": "🎞️ Creating your complete travel film...",
                "completed_days": duration
            })

        # Create videos directory if it doesn't exist
        videos_dir = "videos"
        os.makedirs(videos_dir, exist_ok=True)

        # Final video naming: destination_videoid.mp4
        sanitized_destination = destination.replace(' ', '_').replace('/', '_').replace('\\', '_')
        final_video_filename = f"{sanitized_destination}_{video_id}.mp4"
        final_video_path = os.path.join(videos_dir, final_video_filename)

        merge_success = self._merge_videos(day_video_paths, final_video_path)

        # Cleanup day videos (they're temporary)
        for temp_path in day_video_paths:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info(f"🧹 Cleaned up temp day video: {temp_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to cleanup {temp_path}: {e}")

        if not merge_success:
            return {"success": False, "error": "Failed to merge videos"}

        logger.info("="*80)
        logger.info(f"🎉 YOUR CINEMATIC TRAVEL VIDEO IS COMPLETE!")
        logger.info(f"📁 Path: {final_video_path}")
        logger.info(f"📅 {len(day_video_paths)} days of cinematic travel content")
        logger.info("="*80)

        if progress_callback:
            progress_callback({
                "current_day": duration,
                "total_days": duration,
                "progress": 100,
                "current_stage": "🎬 Your cinematic travel video is ready!",
                "completed_days": duration
            })

        # Optionally encode video to base64 for immediate delivery
        video_base64 = None
        if os.path.exists(final_video_path):
            with open(final_video_path, "rb") as f:
                video_base64 = base64.b64encode(f.read()).decode('utf-8')

        return {
            "success": True,
            "video_url": f"/videos/{final_video_filename}",
            "video_path": final_video_path,
            "video_id": video_id,
            "days_covered": len(day_video_paths),
            "total_days": duration,
            "status": "completed",
            "video_base64": video_base64,
            "temporary": True
        }
    
    def _generate_video_with_images(
        self,
        prompt: str,
        image_urls: List[str],
        model: str,
        destination: str,
        duration: int
    ) -> Dict[str, Any]:
        """Generate video with the traveler from reference photo at actual locations."""
        try:
            payload = {
                "prompt": prompt,
                "imageUrls": image_urls,
                "model": model,
                "aspectRatio": "16:9",
                "generationType": "FIRST_AND_LAST_FRAMES_2_VIDEO",
                "enableTranslation": True,
                "enableFallback": True,
                "personGeneration": "allow_adult",
                "generateAudio": False,
                "negativePrompt": "different person, inconsistent face, static pose, fake smile, tourist posing, blank expression, bored look, mannequin, doll, plastic look, text overlay, watermark, logo, blurry, shaky camera, bad lighting, cartoon, animation, frozen frame, slow motion, dull colors, celebrity, famous person, politician, actor, public figure"
            }
            
            logger.info(f"🔧 Generating cinematic video with reference person...")
            
            response = requests.post(
                f"{self.base_url}/generate",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if not response.ok:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            
            if result.get("code") != 200:
                return {"success": False, "error": result.get("msg", "API error")}
            
            task_id = None
            if result.get("data") and isinstance(result["data"], dict):
                task_id = result["data"].get("taskId") or result["data"].get("task_id") or result["data"].get("id")
            if not task_id:
                task_id = result.get("taskId") or result.get("task_id")
            
            if not task_id:
                return {"success": False, "error": "No task_id returned"}
            
            return {"success": True, "task_id": task_id, "status": "processing"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_video_status(self, task_id: str) -> Dict[str, Any]:
        """Check video status."""
        try:
            response = requests.get(
                f"{self.base_url}/record-info?taskId={task_id}",
                headers=self.headers,
                timeout=10
            )
            
            if not response.ok:
                return {"success": False, "status": "error", "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            if result.get("code") != 200:
                return {"success": False, "status": "error", "error": result.get("msg")}
            
            data = result.get("data", {})
            success_flag = data.get("successFlag")
            
            if success_flag == 1:
                video_url = None
                if data.get("response") and isinstance(data["response"], dict):
                    result_urls = data["response"].get("resultUrls")
                    if result_urls and len(result_urls) > 0:
                        video_url = result_urls[0]
                
                if not video_url:
                    result_urls_str = data.get("resultUrls")
                    if result_urls_str:
                        try:
                            urls = json.loads(result_urls_str) if isinstance(result_urls_str, str) else result_urls_str
                            if urls and len(urls) > 0:
                                video_url = urls[0]
                        except:
                            pass
                
                if not video_url:
                    video_url = data.get("videoUrl") or data.get("video_url") or data.get("url")
                
                return {"success": True, "status": "completed", "video_url": video_url, "task_id": task_id}
            
            elif success_flag in [2, 3]:
                return {"success": False, "status": "failed", "error": data.get("errorMessage", "Failed"), "task_id": task_id}
            
            return {"success": True, "status": "processing", "task_id": task_id}
            
        except Exception as e:
            return {"success": False, "status": "error", "error": str(e), "task_id": task_id}
    
    def wait_for_video(self, task_id: str, max_wait_time: int = 600, poll_interval: int = 10) -> Dict[str, Any]:
        """Wait for video completion."""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            result = self.check_video_status(task_id)
            
            if result["status"] == "completed":
                logger.info(f"✅ Video ready in {int(time.time() - start_time)}s")
                return result
            elif result["status"] == "failed":
                return result
            
            logger.info(f"⏳ Rendering... ({int(time.time() - start_time)}s)")
            time.sleep(poll_interval)
        
        return {"success": False, "status": "timeout", "error": "Timeout", "task_id": task_id}
    
    def download_video(self, video_url: str, output_path: str) -> bool:
        """Download video."""
        try:
            response = requests.get(video_url, stream=True, timeout=120)
            response.raise_for_status()
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"✅ Downloaded: {output_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return False
    
    def _merge_videos(self, video_paths: List[str], output_path: str) -> bool:
        """Merge day videos with smooth transitions and validate output."""
        clips = []
        try:
            # First, load and validate each clip
            for i, path in enumerate(video_paths):
                if not os.path.exists(path):
                    logger.error(f"❌ Day {i+1} video file missing: {path}")
                    return False

                file_size = os.path.getsize(path)
                if file_size < 10 * 1024:
                    logger.error(f"❌ Day {i+1} video file too small ({file_size} bytes): {path}")
                    return False

                try:
                    clip = VideoFileClip(path)
                    if clip.duration <= 0:
                        logger.error(f"❌ Day {i+1} video has zero duration: {path}")
                        clip.close()
                        return False
                    logger.info(f"✅ Loaded day {i+1} video: {path} ({file_size} bytes, {clip.duration:.2f}s, {clip.fps}fps, {clip.size})")
                    clips.append(clip)
                except Exception as e:
                    logger.error(f"❌ Failed to load {path}: {e}", exc_info=True)
                    return False

            if not clips:
                logger.error("❌ No valid clips to merge")
                return False

            # Check that all clips have the same fps and resolution
            fps = clips[0].fps
            size = clips[0].size
            for idx, clip in enumerate(clips[1:], start=2):
                if clip.fps != fps:
                    logger.warning(f"⚠️ Day {idx} fps ({clip.fps}) differs from first clip ({fps}) – may cause sync issues.")
                if clip.size != size:
                    logger.warning(f"⚠️ Day {idx} resolution {clip.size} differs from first clip {size} – will be resized automatically.")

            logger.info(f"🎬 Merging {len(clips)} clips...")
            final_clip = concatenate_videoclips(clips, method="compose")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            final_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=fps,              
                preset='medium',
                threads=2,
                logger=None
            )

            # Validate final video duration
            final_duration = final_clip.duration
            expected_duration = sum(clip.duration for clip in clips)
            logger.info(f"✅ Final video duration: {final_duration:.2f}s (expected: {expected_duration:.2f}s)")

            if abs(final_duration - expected_duration) > 0.5:
                logger.error(f"❌ Final video duration mismatch: {final_duration:.2f}s vs {expected_duration:.2f}s")
                # Optionally, we could still return True but warn
            else:
                logger.info("✅ Duration matches expected.")

            final_clip.close()
            for clip in clips:
                clip.close()

            if os.path.exists(output_path):
                logger.info(f"✅ Final cinematic video saved: {output_path}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Merge failed: {e}", exc_info=True)
            return False
        finally:
            # Ensure all clips are closed even on error
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass
    
    def __del__(self):
        """Cleanup on instance destruction."""
        self.cleanup_session_files()