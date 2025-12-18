"""
Video Generation Service using KIE AI API (Google Veo 3.1)

OPTIMIZED APPROACH:
- Generate ONE video per day using ONLY user photos
- Create hyper-specific prompts based on ACTUAL daily activities
- Show what the user is DOING, not just describing scenes
- Focus on user's actions, emotions, and journey through the day
- Merge all day videos into final video using moviepy
"""

import os
import time
import requests
import logging
import json
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)

class VideoGenerationService:
    """Service for generating day-by-day travel videos and merging them"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KIE_AI_API_KEY")
        self.base_url = "https://api.kie.ai/api/v1/veo"
        self.upload_base_url = "https://kieai.redpandaai.co"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
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
            
            logger.info(f"📡 Upload HTTP Status: {response.status_code}")
            
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
                logger.info(f"✅ File uploaded successfully!")
                return file_url
            
            logger.error(f"❌ No URL in upload response")
            return None
            
        except Exception as e:
            logger.error(f"❌ Upload exception: {e}")
            return None
    
    def generate_full_itinerary_video(
        self,
        user_image_url: str,
        destination: str,
        duration: int,
        daily_activities: List[Dict[str, Any]],
        model: str = "veo3_fast",
        progress_callback: Optional[Callable] = None,
        video_id: Optional[str] = None,
        video_db: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Generate day-by-day videos showing user's actual journey."""
        
        logger.info("="*80)
        logger.info("🎥 GENERATING DAY-BY-DAY TRAVEL VIDEOS")
        logger.info(f"📍 Destination: {destination}")
        logger.info(f"📅 Duration: {duration} days")
        logger.info("="*80)
        
        # Upload user photo if localhost
        if user_image_url.startswith("http://localhost") or user_image_url.startswith("http://127.0.0.1"):
            logger.info("🔄 Uploading user photo to KIE AI...")
            filename = user_image_url.split("/uploads/", 1)[-1]
            local_path = f"uploads/{filename}"
            
            public_url = self.upload_file_to_kie(local_path)
            if public_url:
                user_image_url = public_url
                logger.info(f"✅ Using public URL")
            else:
                logger.error("❌ Upload failed!")
                return {"success": False, "error": "Failed to upload photo"}
        
        # Generate videos for each day
        day_video_paths = []
        
        for day_num in range(1, duration + 1):
            logger.info("="*60)
            logger.info(f"🎬 GENERATING VIDEO FOR DAY {day_num}")
            logger.info("="*60)
            
            if progress_callback:
                progress_callback({
                    "current_day": day_num,
                    "total_days": duration,
                    "progress": int((day_num - 1) / duration * 90),
                    "current_stage": f"Generating Day {day_num} video...",
                    "completed_days": day_num - 1
                })
            
            # Get day's activities
            day_idx = day_num - 1
            if day_idx >= len(daily_activities):
                logger.warning(f"⚠️ No activities for day {day_num}, skipping")
                continue
            
            day_activities = daily_activities[day_idx]
            
            # User photo only
            day_photos = [user_image_url]
            logger.info(f"📸 Using user photo for Day {day_num}")
            
            # Create optimized activity-specific prompt
            prompt = self._create_journey_prompt(day_num, day_activities)
            logger.info(f"📝 Prompt preview: {prompt[:150]}...")
            
            # Save to database
            if video_db and video_id:
                video_db.save_day_video(
                    video_id=video_id,
                    day_number=day_num,
                    prompt=prompt,
                    photos=day_photos,
                    status="processing"
                )
            
            # Generate video
            result = self._generate_video_with_images(
                prompt=prompt,
                image_urls=day_photos,
                model=model,
                destination=destination,
                duration=1
            )
            
            if not result["success"]:
                logger.error(f"❌ Day {day_num} failed: {result.get('error')}")
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        status="failed",
                        error_message=result.get('error')
                    )
                continue
            
            # Wait for video
            task_id = result["task_id"]
            logger.info(f"⏳ Waiting for Day {day_num} video (task: {task_id})...")
            
            if video_db and video_id:
                video_db.save_day_video(
                    video_id=video_id,
                    day_number=day_num,
                    task_id=task_id,
                    status="processing"
                )
            
            video_result = self.wait_for_video(task_id, max_wait_time=600)
            
            if not video_result["success"]:
                logger.error(f"❌ Day {day_num} video failed: {video_result.get('error')}")
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        status="failed",
                        error_message=video_result.get('error')
                    )
                continue
            
            # Download video
            video_url = video_result.get("video_url")
            if not video_url:
                logger.error(f"❌ No video URL for Day {day_num}")
                continue
            
            output_filename = f"day_{day_num}_{destination.replace(' ', '_')}.mp4"
            output_path = f"/tmp/{output_filename}"
            
            if self.download_video(video_url, output_path):
                day_video_paths.append(output_path)
                logger.info(f"✅ Day {day_num} video downloaded")
                
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        video_url=video_url,
                        local_path=output_path,
                        status="completed"
                    )
        
        # Merge all day videos
        if not day_video_paths:
            logger.error("❌ No day videos generated!")
            return {
                "success": False,
                "error": "No day videos were generated successfully"
            }
        
        logger.info("="*60)
        logger.info(f"🎬 MERGING {len(day_video_paths)} DAY VIDEOS")
        logger.info("="*60)
        
        if progress_callback:
            progress_callback({
                "current_day": duration,
                "total_days": duration,
                "progress": 90,
                "current_stage": "Merging videos...",
                "completed_days": duration
            })
        
        final_video_path = f"videos/{destination.replace(' ', '_')}_trip_final.mp4"
        merge_success = self._merge_videos(day_video_paths, final_video_path)
        
        # Cleanup
        for temp_path in day_video_paths:
            try:
                os.remove(temp_path)
            except:
                pass
        
        if not merge_success:
            return {"success": False, "error": "Failed to merge day videos"}
        
        logger.info("="*80)
        logger.info(f"🎉 FINAL VIDEO COMPLETE: {final_video_path}")
        logger.info("="*80)
        
        video_filename = os.path.basename(final_video_path)
        
        if progress_callback:
            progress_callback({
                "current_day": duration,
                "total_days": duration,
                "progress": 100,
                "current_stage": "Complete!",
                "completed_days": duration
            })
        
        return {
            "success": True,
            "video_url": f"/videos/{video_filename}",
            "video_path": final_video_path,
            "days_covered": len(day_video_paths),
            "total_days": duration,
            "status": "completed"
        }
    
    def _create_journey_prompt(
        self,
        day_num: int,
        day_activities: Dict[str, Any]
    ) -> str:
        """
        Create vivid, emotionally engaging prompt that captures the EXCITEMENT and JOY of travel.
        
        Focus on:
        1. Visible EXCITEMENT and enthusiasm in every action
        2. FUN MOMENTS and laughter throughout activities
        3. Active EXPLORATION with curiosity and wonder
        4. MEMORABLE EXPERIENCES showing authentic joy
        5. Emotional connection to the journey
        """
        
        morning = day_activities.get("morning", {})
        afternoon = day_activities.get("afternoon", {})
        evening = day_activities.get("evening", {})
        
        # Build narrative showing vivid journey with excitement
        scenes = []
        
        # Morning scene
        if morning.get("activity"):
            morning_scene = self._build_vivid_activity_scene(
                activity_text=morning.get("activity", ""),
                time_period="morning",
                timing="0-2.5 seconds"
            )
            scenes.append(morning_scene)
        
        # Afternoon scene
        if afternoon.get("activity"):
            afternoon_scene = self._build_vivid_activity_scene(
                activity_text=afternoon.get("activity", ""),
                time_period="afternoon",
                timing="2.5-5 seconds"
            )
            scenes.append(afternoon_scene)
        
        # Evening scene
        if evening.get("activity"):
            evening_scene = self._build_vivid_activity_scene(
                activity_text=evening.get("activity", ""),
                time_period="evening",
                timing="5-8 seconds"
            )
            scenes.append(evening_scene)
        
        if not scenes:
            return self._create_fallback_prompt(day_num)
        
        # Combine into complete prompt with emotional energy
        prompt = (
            f"Create a vibrant 8-second travel vlog capturing Day {day_num} - a day filled with excitement, "
            f"wonder, and unforgettable moments. Show the traveler's GENUINE JOY and enthusiasm as they "
            f"experience each activity. This is their adventure coming to life:"
        )
        
        # Add each scene
        for i, scene in enumerate(scenes, 1):
            prompt += f" [{i}] {scene}"
        
        # Add vivid animation and emotional instructions
        prompt += (
            " ANIMATE the traveler's expressions and movements to radiate pure happiness and excitement. "
            "CAMERA: Use dynamic handheld shots that follow their energetic actions, zooming in on joyful expressions, "
            "panning to reveal stunning surroundings that fuel their enthusiasm. STYLE: Bright, saturated colors full of life. "
            "Golden lighting enhancing the warmth and vibrancy of the day. Lens flares adding magical touch. "
            "AUDIO: Include ambient sounds of laughter, cheerful chatter, upbeat music that matches the energetic vibe. "
            "FEELING: This video should make viewers feel the traveler's exhilaration and joy of discovery, "
            "immersing them in the thrill of exploration and memorable experiences."
        )
        
        return prompt
    
    
    def _create_fallback_prompt(self, day_num: int) -> str:
        """Fallback prompt capturing excitement even without specific activities."""
        return (
            f"Create a vibrant 8-second travel video of Day {day_num} showing pure travel joy. "
            "Show the traveler's excitement and enthusiasm as they explore new places. "
            "CAMERA: Dynamic handheld shots capturing joyful expressions and stunning surroundings. "
        )
    
    def _generate_video_with_images(
        self,
        prompt: str,
        image_urls: List[str],
        model: str,
        destination: str,
        duration: int
    ) -> Dict[str, Any]:
        """Call KIE AI API to generate video."""
        try:
            payload = {
                "prompt": prompt,
                "imageUrls": image_urls,
                "model": model,
                "aspectRatio": "16:9",
                "generationType": "REFERENCE_2_VIDEO",
                "enableTranslation": True,
                "enableFallback": True,
                "personGeneration": "allow_adult",
                "generateAudio": True,
                "negativePrompt": (
                    "static image, frozen pose, no movement, lifeless scene, "
                    "unnatural motion, robotic movements, text overlays, watermarks, "
                    "low quality, blurry, distorted faces"
                )
            }
            
            logger.info(f"🔧 API Request: {self.base_url}/generate")
            logger.info(f"🔧 Model: {model} | Images: {len(image_urls)}")
            
            response = requests.post(
                f"{self.base_url}/generate",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if not response.ok:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:500]}"
                }
            
            result = response.json()
            
            if result.get("code") != 200:
                return {
                    "success": False,
                    "error": result.get("msg", "Unknown API error")
                }
            
            # Extract task ID
            task_id = None
            if result.get("data"):
                task_id = (result["data"].get("taskId") or 
                          result["data"].get("task_id") or 
                          result["data"].get("id"))
            
            if not task_id:
                task_id = result.get("taskId") or result.get("task_id")
            
            if not task_id:
                return {"success": False, "error": "No task_id returned"}
            
            return {
                "success": True,
                "task_id": task_id,
                "status": "processing"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_video_status(self, task_id: str) -> Dict[str, Any]:
        """Check video generation status."""
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
                return {"success": False, "status": "error", "error": result.get("msg", "Unknown error")}
            
            data = result.get("data", {})
            success_flag = data.get("successFlag")
            
            if success_flag == 1:
                # Get video URL
                video_url = None
                if data.get("response"):
                    result_urls = data["response"].get("resultUrls")
                    if result_urls and len(result_urls) > 0:
                        video_url = result_urls[0]
                
                if not video_url:
                    result_urls_str = data.get("resultUrls")
                    if result_urls_str:
                        if isinstance(result_urls_str, str):
                            result_urls = json.loads(result_urls_str)
                        else:
                            result_urls = result_urls_str
                        if result_urls and len(result_urls) > 0:
                            video_url = result_urls[0]
                
                return {
                    "success": True,
                    "status": "completed",
                    "video_url": video_url,
                    "task_id": task_id
                }
            
            elif success_flag in [2, 3]:
                return {
                    "success": False,
                    "status": "failed",
                    "error": data.get("errorMessage", "Video generation failed")
                }
            
            else:
                return {"success": True, "status": "processing"}
                
        except Exception as e:
            return {"success": False, "status": "error", "error": str(e)}
    
    def wait_for_video(self, task_id: str, max_wait_time: int = 600, poll_interval: int = 10) -> Dict[str, Any]:
        """Wait for video to complete."""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_result = self.check_video_status(task_id)
            
            if not status_result.get("success"):
                return status_result
            
            if status_result["status"] == "completed":
                return status_result
            elif status_result["status"] == "failed":
                return status_result
            
            time.sleep(poll_interval)
        
        return {
            "success": False,
            "status": "timeout",
            "error": f"Timeout after {max_wait_time}s"
        }
    
    def download_video(self, video_url: str, output_path: str) -> bool:
        """Download video from URL."""
        try:
            response = requests.get(video_url, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"✅ Downloaded: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return False
    
    def _merge_videos(self, video_paths: List[str], output_path: str) -> bool:
        """Merge multiple videos using moviepy."""
        try:
            from moviepy.editor import VideoFileClip, concatenate_videoclips
            
            logger.info(f"🎬 Loading {len(video_paths)} clips...")
            
            clips = [VideoFileClip(path) for path in video_paths]
            final_clip = concatenate_videoclips(clips, method="compose")
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            logger.info(f"💾 Writing final video...")
            final_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=24
            )
            
            final_clip.close()
            for clip in clips:
                clip.close()
            
            return os.path.exists(output_path)
            
        except Exception as e:
            logger.error(f"❌ Merge failed: {e}")
            return False