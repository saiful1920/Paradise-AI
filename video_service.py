"""
Video Generation Service using KIE AI API (Google Veo 3.1)

REDESIGNED APPROACH:
- Generate ONE video per day with user + day's location photos
- Use simple, effective prompts for realistic travel videos
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
        """
        Upload a local file to KIE AI and get a public URL.
        
        Files are temporary and automatically deleted after 3 days.
        
        Args:
            local_file_path: Path to local file (e.g., /path/to/photo.jpg)
            
        Returns:
            Public URL of uploaded file, or None if upload fails
        """
        try:
            import os
            
            if not os.path.exists(local_file_path):
                logger.error(f"❌ File not found: {local_file_path}")
                return None
            
            # Get filename
            filename = os.path.basename(local_file_path)
            
            logger.info(f"📤 Uploading file to KIE AI: {filename}")
            
            # Prepare multipart form data
            with open(local_file_path, 'rb') as f:
                files = {
                    'file': (filename, f, 'image/jpeg')
                }
                
                # Add uploadPath as form data (required by KIE AI)
                data = {
                    'uploadPath': 'travel-videos'  # Organize uploads in folder
                }
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                    # Don't set Content-Type, requests will set it with boundary
                }
                
                response = requests.post(
                    f"{self.upload_base_url}/api/file-stream-upload",
                    headers=headers,
                    files=files,
                    data=data,  # Add form data
                    timeout=30
                )
            
            logger.info(f"📡 Upload HTTP Status: {response.status_code}")
            
            if not response.ok:
                logger.error(f"❌ Upload failed: {response.status_code}")
                logger.error(f"❌ Response: {response.text[:500]}")
                return None
            
            result = response.json()
            
            # Check for success
            if result.get("code") != 200:
                error_msg = result.get("msg", "Unknown error")
                logger.error(f"❌ Upload API error: {error_msg}")
                return None
            
            # Extract file URL
            data = result.get("data", {})
            file_url = (data.get("downloadUrl") or 
                       data.get("url") or 
                       data.get("fileUrl") or 
                       data.get("file_url"))
            
            if not file_url:
                logger.error(f"❌ No URL in upload response: {result}")
                return None
            
            logger.info(f"✅ File uploaded successfully!")
            logger.info(f"🔗 Public URL: {file_url}")
            
            return file_url
            
        except Exception as e:
            logger.error(f"❌ Upload exception: {e}")
            return None
    
    def generate_full_itinerary_video(
        self,
        user_image_url: str,
        destination: str,
        duration: int,
        daily_activities: List[Dict[str, Any]],
        model: str = "veo3",
        progress_callback: Optional[Callable] = None,
        video_id: Optional[str] = None,
        video_db: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Generate day-by-day videos and merge them into final video.
        
        SIMPLE APPROACH:
        - Generate one video per day with user + day's location photos
        - Use simple, effective prompts
        - Merge all day videos using moviepy
        
        Args:
            user_image_url: User's photo URL
            destination: Destination name  
            duration: Number of days
            daily_activities: All day activities with photos
            model: "veo3" or "veo3_fast"
            progress_callback: Callback function for progress updates
            
        Returns:
            Dict with success, video_url, merged video info
        """
        logger.info("="*80)
        logger.info("🎥 GENERATING DAY-BY-DAY TRAVEL VIDEOS")
        logger.info(f"📍 Destination: {destination}")
        logger.info(f"📅 Duration: {duration} days")
        logger.info(f"🎬 Strategy: One video per day + merge")
        logger.info("="*80)
        
        # Step 0: Upload user photo if localhost
        if user_image_url.startswith("http://localhost") or user_image_url.startswith("http://127.0.0.1"):
            logger.info("🔄 Uploading user photo to KIE AI...")
            filename = user_image_url.split("/uploads/", 1)[-1]
            local_path = f"uploads/{filename}"
            
            public_url = self.upload_file_to_kie(local_path)
            if public_url:
                logger.info(f"✅ Using public URL")
                user_image_url = public_url
            else:
                logger.error("❌ Upload failed!")
                return {"success": False, "error": "Failed to upload photo"}
        
        # Step 1: Generate videos for each day
        day_video_paths = []
        
        for day_num in range(1, duration + 1):
            logger.info("="*60)
            logger.info(f"🎬 GENERATING VIDEO FOR DAY {day_num}")
            logger.info("="*60)
            
            # Update progress
            if progress_callback:
                progress_callback({
                    "current_day": day_num,
                    "total_days": duration,
                    "progress": int((day_num - 1) / duration * 90),  # 0-90%
                    "current_stage": f"Generating Day {day_num} video...",
                    "completed_days": day_num - 1
                })
            
            # Get day's activities and photos
            day_idx = day_num - 1
            if day_idx >= len(daily_activities):
                logger.warning(f"⚠️ No activities for day {day_num}, skipping")
                continue
            
            day_activities = daily_activities[day_idx]
            
            # Collect photos for this day (user + day's locations)
            day_photos = self._collect_day_photos(user_image_url, day_activities)
            
            if not day_photos:
                logger.warning(f"⚠️ No photos for day {day_num}, skipping")
                
                # Save failed day to database
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        status="failed",
                        error_message="No photos available"
                    )
                continue
            
            logger.info(f"📸 Day {day_num} photos: {len(day_photos)} images")
            
            # Create simple prompt
            prompt = self._create_simple_day_prompt(destination, day_num, day_activities)
            logger.info(f"📝 Prompt: {prompt}")
            
            # Save day video as processing in database
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
                duration=1  # Single day
            )
            
            if not result["success"]:
                logger.error(f"❌ Day {day_num} video generation failed: {result.get('error')}")
                
                # Update database
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
            logger.info(f"⏳ Waiting for Day {day_num} video...")
            
            # Update database with task_id
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
                
                # Update database
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
                
                # Update database
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        status="failed",
                        error_message="No video URL returned"
                    )
                continue
            
            output_filename = f"day_{day_num}_{destination.replace(' ', '_')}.mp4"
            output_path = f"/tmp/{output_filename}"
            
            download_success = self.download_video(video_url, output_path)
            
            if download_success:
                day_video_paths.append(output_path)
                logger.info(f"✅ Day {day_num} video downloaded: {output_path}")
                
                # Update database with completed video
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        video_url=video_url,
                        local_path=output_path,
                        status="completed"
                    )
            else:
                logger.error(f"❌ Failed to download Day {day_num} video")
                
                # Update database
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        video_url=video_url,
                        status="failed",
                        error_message="Download failed"
                    )
        
        # Step 2: Merge all day videos
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
        
        # Merge videos - save in current directory
        final_video_path = f"videos/{destination.replace(' ', '_')}_trip_final.mp4"
        merge_success = self._merge_videos(day_video_paths, final_video_path)
        
        # Cleanup temp files
        for temp_path in day_video_paths:
            try:
                os.remove(temp_path)
                logger.info(f"🗑️ Cleaned up: {temp_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to cleanup {temp_path}: {e}")
        
        if not merge_success:
            logger.error("❌ Video merging failed!")
            return {
                "success": False,
                "error": "Failed to merge day videos"
            }
        
        logger.info("="*80)
        logger.info(f"🎉 FINAL VIDEO COMPLETE!")
        logger.info(f"📁 Path: {final_video_path}")
        logger.info(f"📅 Days covered: {len(day_video_paths)}")
        logger.info("="*80)
        
        # Get video filename
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
    
    def _download_and_upload_photo(self, photo_url: str, filename: str) -> Optional[str]:
        """
        For Google Places photos, just return the URL as-is.
        KIE AI should be able to fetch public Google Places photos.
        
        Args:
            photo_url: URL of photo
            filename: Name for the file (unused now)
            
        Returns:
            Original photo URL
        """
        # Return Google Places URL directly
        return photo_url
    
    def _collect_day_photos(
        self,
        user_image_url: str,
        day_activities: Dict[str, Any]
    ) -> List[str]:
        """
        Collect photos for a single day.
        
        Strategy:
        - User photo (uploaded to KIE AI)
        - 1-2 location photos (Google Places URLs)
        - Use URLs directly
        
        Returns:
            List of photo URLs (2-3 max)
        """
        photos = []
        
        # Add user photo first (already uploaded to KIE AI)
        photos.append(user_image_url)
        logger.info(f"📸 User photo: {user_image_url[:50]}...")
        
        # Add 1-2 location photos
        location_count = 0
        
        for period in ["morning", "afternoon", "evening"]:
            if location_count >= 2:  # MAX 2 location photos
                break
                
            if day_activities.get(period) and day_activities[period].get("photo_url"):
                photo_url = day_activities[period]["photo_url"]
                
                # Skip local/relative URLs
                if photo_url.startswith("/") or "localhost" in photo_url or "127.0.0.1" in photo_url:
                    logger.warning(f"⚠️ Skipping local URL: {photo_url[:50]}...")
                    continue
                
                # Use Google Places photos directly with good resolution
                if "maps.googleapis.com" in photo_url or "googleusercontent.com" in photo_url:
                    # Use 400px for good quality
                    if "?" in photo_url:
                        base_url = photo_url.split("?")[0]
                        params = photo_url.split("?")[1]
                        # Update maxwidth if exists
                        if "maxwidth" in params:
                            params = "maxwidth=400&" + "&".join([p for p in params.split("&") if "maxwidth" not in p])
                        else:
                            params += "&maxwidth=400"
                        photo_url = f"{base_url}?{params}"
                    else:
                        photo_url += "?maxwidth=400"
                    
                    logger.info(f"📸 Using 400px Google Places photo")
                
                photos.append(photo_url)
                logger.info(f"📸 {period}: {photo_url[:80]}...")
                location_count += 1
        
        logger.info(f"📸 Total for day: {len(photos)} images (1 user + {location_count} locations)")
        
        return photos
    
    def _create_simple_day_prompt(
        self,
        destination: str,
        day_num: int,
        day_activities: Dict[str, Any]
    ) -> str:
        """
        Create simple, generic prompt that avoids content policy issues.
        
        Focus on the visual storytelling using photos, not specific place names.
        """
        # Simple, safe prompt - no specific place names
        prompt = (
            f"""
            Create an 8-second travel highlight video for Day {day_num} using the three uploaded photos (one user photo and two location photos). 
            1) Begin with the first location photo as a wide establishing shot. Add a slow cinematic push-in and slight movement in clouds or water to bring it to life. 
            2) Transition to the user photo combined with the second location photo: animate subtle parallax, small motions (like gentle head turn or body shift), and environmental animation (like waving foliage or drifting light) to evoke the experience of visiting and enjoying the place. 
            3) End with a blended wide view of the location photos with gentle camera movement and ambient travel sounds or soft background music. 
            Use warm, cinematic color tones with smooth transitions and natural motion focusing on scenery and atmosphere.
            """
        )

        return prompt
    
    def _generate_video_with_images(
        self,
        prompt: str,
        image_urls: List[str],
        model: str,
        destination: str,
        duration: int
    ) -> Dict[str, Any]:
        """
        Call KIE AI API to generate video with multiple reference images.
        """
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
                "negativePrompt": "Exclude any harmful, unsafe, violent, or sensitive visual content"
            }
            
            logger.info(f"🔧 API Request: POST {self.base_url}/generate")
            logger.info(f"🔧 Model: {model}")
            logger.info(f"🔧 Images: {len(image_urls)}")
            logger.info(f"🔧 Aspect Ratio: 16:9")
            
            response = requests.post(
                f"{self.base_url}/generate",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            logger.info(f"📡 HTTP Status: {response.status_code}")
            
            if not response.ok:
                error_text = response.text[:500]
                logger.error(f"❌ HTTP Error: {response.status_code}")
                logger.error(f"❌ Response: {error_text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {error_text}"
                }
            
            result = response.json()
            api_code = result.get("code")
            logger.info(f"📡 API Code: {api_code}")
            
            # Check API error
            if api_code != 200:
                error_msg = result.get("msg", "Unknown API error")
                logger.error(f"❌ API Error: {error_msg}")
                
                # Provide helpful guidance for common errors
                if "size exceeds limit" in error_msg.lower():
                    logger.error("💡 Image size too large. Using optimized images.")
                    return {
                        "success": False,
                        "error": "Image size exceeds KIE AI limit.",
                        "api_response": result
                    }
                
                return {
                    "success": False,
                    "error": error_msg,
                    "api_response": result
                }
            
            # Extract task ID
            task_id = None
            if result.get("data") and isinstance(result["data"], dict):
                task_id = (result["data"].get("taskId") or 
                          result["data"].get("task_id") or 
                          result["data"].get("id"))
            
            if not task_id:
                task_id = result.get("taskId") or result.get("task_id")
            
            if not task_id:
                logger.error(f"❌ No task_id in response: {result}")
                return {
                    "success": False,
                    "error": "No task_id returned",
                    "api_response": result
                }
            
            return {
                "success": True,
                "task_id": task_id,
                "status": "processing",
                "images_used": len(image_urls),
                "destination": destination,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"❌ Exception: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_video_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check video generation status.
        
        Returns:
            Dict with status, video_url if complete, error if failed
        """
        try:
            response = requests.get(
                f"{self.base_url}/record-info?taskId={task_id}",
                headers=self.headers,
                timeout=10
            )
            
            if not response.ok:
                return {
                    "success": False,
                    "status": "error",
                    "error": f"HTTP {response.status_code}",
                    "task_id": task_id
                }
            
            result = response.json()
            
            if result.get("code") != 200:
                error_msg = result.get("msg", "Unknown error")
                return {
                    "success": False,
                    "status": "error",
                    "error": error_msg,
                    "task_id": task_id
                }
            
            data = result.get("data", {})
            success_flag = data.get("successFlag")
            
            # successFlag: 0 = processing, 1 = completed, 2/3 = failed
            if success_flag == 1:
                # Parse video URL - try multiple possible locations
                video_url = None
                
                # Try 1: data['response']['resultUrls']
                if data.get("response") and isinstance(data["response"], dict):
                    result_urls = data["response"].get("resultUrls")
                    if result_urls and isinstance(result_urls, list) and len(result_urls) > 0:
                        video_url = result_urls[0]
                        logger.info(f"✅ Video URL from response.resultUrls")
                
                # Try 2: data['resultUrls']
                if not video_url:
                    result_urls_str = data.get("resultUrls")
                    if result_urls_str:
                        try:
                            if isinstance(result_urls_str, str):
                                result_urls = json.loads(result_urls_str)
                            else:
                                result_urls = result_urls_str
                            
                            if result_urls and len(result_urls) > 0:
                                video_url = result_urls[0]
                                logger.info(f"✅ Video URL from resultUrls")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to parse resultUrls: {e}")
                
                # Try 3: Other possible field names
                if not video_url:
                    video_url = (data.get("videoUrl") or 
                                data.get("video_url") or 
                                data.get("url") or
                                data.get("downloadUrl"))
                
                if not video_url:
                    logger.error(f"❌ No video URL found in response!")
                
                return {
                    "success": True,
                    "status": "completed",
                    "video_url": video_url,
                    "task_id": task_id,
                    "data": data
                }
            
            elif success_flag in [2, 3]:
                error_msg = data.get("errorMessage", "Video generation failed")
                logger.error(f"❌ Video failed: {error_msg}")
                return {
                    "success": False,
                    "status": "failed",
                    "error": error_msg,
                    "task_id": task_id
                }
            
            else:  # Processing
                return {
                    "success": True,
                    "status": "processing",
                    "progress": 0,
                    "task_id": task_id
                }
                
        except Exception as e:
            logger.error(f"❌ Error checking status: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "task_id": task_id
            }
    
    def wait_for_video(
        self,
        task_id: str,
        max_wait_time: int = 600,
        poll_interval: int = 10
    ) -> Dict[str, Any]:
        """
        Wait for video to complete, polling status.
        
        Args:
            task_id: Video task ID
            max_wait_time: Maximum seconds to wait (default 10 minutes)
            poll_interval: Seconds between polls (default 10 seconds)
            
        Returns:
            Dict with success, status, video_url
        """
        start_time = time.time()
        checks = 0
        
        while time.time() - start_time < max_wait_time:
            checks += 1
            
            status_result = self.check_video_status(task_id)
            
            if not status_result.get("success"):
                return status_result
            
            current_status = status_result["status"]
            
            if current_status == "completed":
                elapsed = int(time.time() - start_time)
                logger.info(f"✅ Video completed after {elapsed}s ({checks} checks)")
                return status_result
            
            elif current_status == "failed":
                return status_result
            
            # Still processing
            elapsed = int(time.time() - start_time)
            logger.info(f"⏳ Still processing... ({elapsed}s elapsed)")
            time.sleep(poll_interval)
        
        # Timeout
        elapsed = int(time.time() - start_time)
        logger.error(f"❌ Timeout after {elapsed}s")
        return {
            "success": False,
            "status": "timeout",
            "error": f"Video generation exceeded {max_wait_time}s timeout",
            "task_id": task_id
        }
    
    def download_video(self, video_url: str, output_path: str) -> bool:
        """
        Download video from URL to local file.
        
        Args:
            video_url: URL to video
            output_path: Local path to save video
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"📥 Downloading video from: {video_url[:80]}...")
            
            response = requests.get(video_url, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            logger.info(f"✅ Video downloaded: {output_path} ({file_size:.2f} MB)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return False
    
    def _merge_videos(self, video_paths: List[str], output_path: str) -> bool:
        """
        Merge multiple day videos into one final video using moviepy.
        
        Args:
            video_paths: List of paths to day videos
            output_path: Path for merged output video
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from moviepy.editor import VideoFileClip, concatenate_videoclips
            
            logger.info(f"🎬 Loading {len(video_paths)} video clips...")
            
            # Load all video clips
            clips = []
            for i, video_path in enumerate(video_paths, 1):
                logger.info(f"📼 Loading clip {i}/{len(video_paths)}: {video_path}")
                clip = VideoFileClip(video_path)
                clips.append(clip)
            
            logger.info(f"🔗 Concatenating {len(clips)} clips...")
            
            # Concatenate all clips
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            logger.info(f"💾 Writing final video: {output_path}")
            
            # Write output video
            final_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                fps=24
            )
            
            # Clean up
            final_clip.close()
            for clip in clips:
                clip.close()
            
            # Verify output
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path) / (1024 * 1024)
                logger.info(f"✅ Final video created: {output_path} ({file_size:.2f} MB)")
                return True
            else:
                logger.error(f"❌ Output file not created: {output_path}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Video merge failed: {e}")
            import traceback
            traceback.print_exc()
            return False