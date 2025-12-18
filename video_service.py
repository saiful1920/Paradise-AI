"""
Video Generation Service using KIE AI API (Google Veo 3.1)

ACTIVITY-MATCHED TRAVEL VIDEO WITH TIMELINE GUIDANCE:
- Videos directly reflect the ACTUAL activities from each day's itinerary
- The SAME PERSON from the uploaded photo appears doing those specific activities
- INTELLIGENT TIME ALLOCATION: LLM decides how many seconds each activity gets
- TRAVEL VLOG STYLE: Exciting, fun, energetic short-form content
- Morning/Afternoon/Evening activities visualized with proper pacing
"""

import os
import time
import requests
import logging
import json
from typing import Dict, List, Optional, Any, Callable
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


class VideoGenerationService:
    """Service for generating travel videos that match the actual itinerary activities"""
    
    def __init__(self, api_key: Optional[str] = None, openai_api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KIE_AI_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://api.kie.ai/api/v1/veo"
        self.upload_base_url = "https://kieai.redpandaai.co"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            openai_api_key=self.openai_api_key
        )
    
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
        Generate video prompt with INTELLIGENT TIMELINE GUIDANCE.
        
        The LLM will:
        1. Analyze each activity's visual appeal and importance
        2. Allocate seconds (total = 8 seconds) based on activity weight
        3. Create an exciting travel vlog style narrative
        4. Include timing markers for video generation
        """
        
        # Extract ACTUAL activities from the itinerary
        morning = day_activities.get("morning", {})
        afternoon = day_activities.get("afternoon", {})
        evening = day_activities.get("evening", {})
        
        morning_name = morning.get("name", "")
        morning_desc = morning.get("description", "")
        afternoon_name = afternoon.get("name", "")
        afternoon_desc = afternoon.get("description", "")
        evening_name = evening.get("name", "")
        evening_desc = evening.get("description", "")
        
        # Log the actual activities
        logger.info(f"📋 Day {day_num} ACTUAL Activities:")
        logger.info(f"   Morning: {morning_name}")
        logger.info(f"   Afternoon: {afternoon_name}")
        logger.info(f"   Evening: {evening_name}")
        
        prompt = f"""
        Create an 8-SECOND travel vlog video prompt for Day {day_num}.
        
        🎬 VIDEO STYLE: Exciting, energetic TRAVEL VLOG like popular YouTube/TikTok travel content
        - Fast-paced, dynamic shots
        - Person genuinely enjoying and having FUN
        - Emotional moments: wonder, excitement, joy, awe
        - Movement and energy throughout
        
        ⏱️ CRITICAL: TIMELINE ALLOCATION (MUST TOTAL 8 SECONDS)
        
        Analyze each activity and decide how many seconds it deserves based on:
        - Visual appeal (beaches, sunsets, nature = MORE time)
        - Action intensity (adventure sports, swimming = MORE time)
        - Emotional impact (spiritual places, viewpoints = MORE time)
        - Routine activities (transfers, check-in = LESS time)
        - Meal activities (quick bites = 1-1.5s, fancy dinner = 2s)
        
        TIMING EXAMPLES:
        - Epic beach/waterfall/sunset: 2.5-3.5 seconds
        - Adventure activity (hiking, snorkeling): 2.5-3 seconds
        - Cultural experience (temple, show): 2-2.5 seconds
        - Food/dining experience: 1.5-2 seconds
        - Casual activity (shopping, coffee): 1-1.5 seconds
        - Transit/check-in: 0.5-1 second
        
        📅 DAY {day_num} OF {total_days} - ACTIVITIES TO VISUALIZE:
        
        🌅 MORNING:
        - Activity: {morning_name}
        - Details: {morning_desc}
        
        ☀️ AFTERNOON:
        - Activity: {afternoon_name}
        - Details: {afternoon_desc}
        
        🌙 EVENING:
        - Activity: {evening_name}
        - Details: {evening_desc}
        
        🎬 CREATE THE PROMPT WITH THIS EXACT FORMAT:
        
        "[0:00-X:XX] [MORNING SCENE with exciting action and emotion]. 
        [X:XX-Y:YY] [AFTERNOON SCENE with dynamic movement and joy]. 
        [Y:YY-8:00] [EVENING SCENE with satisfying conclusion]. 
        The same person from the reference photo throughout, travel vlog style with energetic pacing, 
        cinematic transitions, genuine reactions of wonder and excitement, warm vibrant colors."
        
        🎥 VLOG-STYLE VISUAL DESCRIPTIONS - Make it EXCITING:
        
        Instead of: "person at beach"
        Write: "person running excitedly into crystal-clear turquoise waves, splashing water, 
        laughing with pure joy, spinning around with arms wide open"
        
        Instead of: "person at temple"  
        Write: "person's eyes widening in awe at ancient golden architecture, slowly walking 
        through ornate corridors, touching ancient stone walls with wonder, peaceful smile"
        
        Instead of: "person eating food"
        Write: "person's delighted reaction tasting street food, eyes closing in pleasure, 
        giving enthusiastic thumbs up, steam rising from delicious dishes"
        
        Instead of: "person watching sunset"
        Write: "person silhouetted against blazing orange sky, arms raised in triumph, 
        turning to camera with biggest smile, golden light painting their face"
        
        🔥 ENERGY & EMOTION KEYWORDS TO INCLUDE:
        - Actions: running, jumping, spinning, dancing, diving, climbing, exploring
        - Reactions: laughing, gasping, smiling widely, eyes sparkling, pure joy
        - Camera: following, sweeping, revealing, tracking, dynamic angles
        - Mood: excitement, wonder, freedom, adventure, bliss, awe
        
        ⚠️ RULES:
        1. Times MUST add up to exactly 8 seconds
        2. Same person from reference photo in ALL scenes
        3. NO location names - only visual descriptions
        4. Make it feel like an actual exciting travel vlog
        5. Include emotional reactions and genuine enjoyment
        6. Dynamic camera movement descriptions
        
        Generate the prompt now. Return ONLY the prompt text with timeline markers.
        """
        
        messages = [
            SystemMessage(content="""You are a travel vlog director creating short-form viral travel content.
            Your prompts create EXCITING, ENERGETIC videos that make viewers want to book trips immediately.
            
            You excel at:
            - Intelligent time allocation based on activity visual appeal
            - Creating dynamic, fast-paced travel vlog narratives
            - Capturing genuine emotions: joy, wonder, excitement, awe
            - Writing prompts that result in scroll-stopping content
            
            Your videos feel like the best travel TikToks/Reels - full of energy, authentic moments, 
            and that "I NEED to go there" feeling.
            
            CRITICAL: Always include exact timeline markers [X:XX-Y:YY] that total 8 seconds.
            Allocate more time to visually stunning/exciting activities."""),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            matched_prompt = response.content.strip()
            
            # Clean quotes
            if matched_prompt.startswith('"') and matched_prompt.endswith('"'):
                matched_prompt = matched_prompt[1:-1]
            if matched_prompt.startswith("'") and matched_prompt.endswith("'"):
                matched_prompt = matched_prompt[1:-1]
            
            # Ensure it references the person
            if "person from the reference" not in matched_prompt.lower() and "reference photo" not in matched_prompt.lower():
                matched_prompt = "The person from the reference photo: " + matched_prompt
            
            logger.info(f"🎬 Generated TIMELINE-GUIDED vlog prompt for Day {day_num}")
            logger.info(f"📝 Prompt: {matched_prompt[:400]}...")
            
            return matched_prompt
            
        except Exception as e:
            logger.error(f"❌ Error generating prompt: {e}")
            return self._create_fallback_matched_prompt(day_num, day_activities)
    
    def _create_fallback_matched_prompt(self, day_num: int, day_activities: Dict[str, Any]) -> str:
        """Create fallback prompt with timeline based on actual activities"""
        
        morning = day_activities.get("morning", {}).get("name", "morning exploration")
        afternoon = day_activities.get("afternoon", {}).get("name", "afternoon adventure")
        evening = day_activities.get("evening", {}).get("name", "evening relaxation")
        
        def get_activity_weight(activity_name: str) -> float:
            """Determine time weight based on activity type"""
            activity_lower = activity_name.lower()
            
            # High visual impact activities (3+ seconds)
            if any(word in activity_lower for word in ["beach", "waterfall", "sunset", "sunrise", "snorkel", "diving", "hike", "trek"]):
                return 3.0
            # Medium-high impact (2.5 seconds)
            elif any(word in activity_lower for word in ["temple", "rice terrace", "mountain", "lake", "boat", "cruise", "cultural show"]):
                return 2.5
            # Medium impact (2 seconds)
            elif any(word in activity_lower for word in ["spa", "massage", "dinner", "restaurant", "market", "shopping", "museum"]):
                return 2.0
            # Lower impact (1.5 seconds)
            elif any(word in activity_lower for word in ["coffee", "cafe", "breakfast", "lunch", "walk", "stroll"]):
                return 1.5
            # Minimal (1 second)
            elif any(word in activity_lower for word in ["arrival", "check-in", "departure", "transfer", "airport"]):
                return 1.0
            else:
                return 2.0
        
        # Calculate weights
        morning_weight = get_activity_weight(morning)
        afternoon_weight = get_activity_weight(afternoon)
        evening_weight = get_activity_weight(evening)
        
        # Normalize to 8 seconds
        total_weight = morning_weight + afternoon_weight + evening_weight
        morning_time = round((morning_weight / total_weight) * 8, 1)
        afternoon_time = round((afternoon_weight / total_weight) * 8, 1)
        evening_time = round(8 - morning_time - afternoon_time, 1)
        
        # Calculate timestamps
        morning_end = morning_time
        afternoon_end = morning_time + afternoon_time
        
        def activity_to_vlog_visual(activity_name: str) -> str:
            """Convert activity to exciting vlog-style visual"""
            activity_lower = activity_name.lower()
            
            if any(word in activity_lower for word in ["beach", "swimming", "swim"]):
                return "running excitedly into crystal-clear turquoise waves, splashing joyfully, diving under water, emerging with a huge smile, spinning around with arms wide open feeling total freedom"
            elif any(word in activity_lower for word in ["temple", "church", "mosque", "shrine"]):
                return "walking slowly through magnificent ancient architecture, eyes widening in complete awe, gently touching ornate golden carvings, peaceful smile of spiritual wonder"
            elif any(word in activity_lower for word in ["hike", "trek", "hiking", "trekking"]):
                return "conquering scenic mountain trails with determination, reaching a viewpoint and throwing arms up in triumph, spinning to take in the breathtaking panorama, genuine exhilaration on their face"
            elif any(word in activity_lower for word in ["rice", "terrace", "farm"]):
                return "walking through stunning emerald green terraced fields, running fingers through rice stalks, stopping to photograph the incredible layered landscape with pure joy"
            elif any(word in activity_lower for word in ["snorkel", "diving", "dive", "underwater"]):
                return "plunging into crystal waters, swimming alongside colorful tropical fish, pointing excitedly at marine life, underwater twirls of pure happiness"
            elif any(word in activity_lower for word in ["waterfall", "falls"]):
                return "approaching a thundering majestic waterfall, getting splashed by cool mist, laughing with delight, standing with arms outstretched feeling the power of nature"
            elif any(word in activity_lower for word in ["food", "eat", "cuisine", "street food", "taste"]):
                return "eagerly trying sizzling street food, eyes closing in delicious pleasure, giving enthusiastic approval, steam rising from mouthwatering dishes"
            elif any(word in activity_lower for word in ["sunset", "sunrise"]):
                return "silhouetted against a blazing orange and pink sky, arms raised in triumph, spinning to face the camera with the biggest smile, golden light painting their happy face"
            elif any(word in activity_lower for word in ["spa", "massage", "relax"]):
                return "melting into pure relaxation during a traditional spa treatment, expression of complete bliss, emerging refreshed and glowing"
            elif any(word in activity_lower for word in ["shop", "market", "bazaar"]):
                return "excitedly exploring colorful vibrant market stalls, trying on fun items, haggling with big smiles, holding up unique treasures with delight"
            elif any(word in activity_lower for word in ["show", "dance", "performance", "cultural"]):
                return "watching mesmerizing traditional performance with sparkling eyes, clapping along enthusiastically, completely captivated by the artistry"
            elif any(word in activity_lower for word in ["boat", "cruise", "sailing"]):
                return "standing at the bow of a boat with wind in their hair, arms spread wide like flying, huge smile watching stunning scenery glide past"
            elif any(word in activity_lower for word in ["dinner", "restaurant", "dining"]):
                return "savoring an elegant dinner in beautiful ambiance, clinking glasses joyfully, tasting exquisite dishes with expressions of pure delight"
            elif any(word in activity_lower for word in ["night market", "night"]):
                return "excitedly exploring glowing neon-lit night market stalls, trying unusual street foods, dancing slightly to live music, infectious evening energy"
            elif any(word in activity_lower for word in ["coffee", "cafe", "breakfast"]):
                return "savoring the first sip of perfect local coffee, satisfied smile, soaking in the morning atmosphere with contentment"
            elif any(word in activity_lower for word in ["arrival", "check-in", "hotel"]):
                return "arriving with excited anticipation, first glimpse of new surroundings, spontaneous happy dance at the start of adventure"
            elif any(word in activity_lower for word in ["departure", "leaving", "airport"]):
                return "taking one last loving look around, hand on heart with gratitude, bittersweet smile of incredible memories made"
            else:
                return f"enthusiastically enjoying {activity_name}, genuine smile of pure travel happiness, soaking in every moment"
        
        morning_visual = activity_to_vlog_visual(morning)
        afternoon_visual = activity_to_vlog_visual(afternoon)
        evening_visual = activity_to_vlog_visual(evening)
        
        return f"""[0:00-{morning_end:.1f}s] The person from the reference photo {morning_visual}. 
        [{morning_end:.1f}s-{afternoon_end:.1f}s] Then they are {afternoon_visual}. 
        [{afternoon_end:.1f}s-8:00] The day ends with them {evening_visual}. 
        Travel vlog style, the same person throughout all scenes, energetic dynamic camera movements, 
        cinematic transitions between activities, genuine emotional reactions, warm vibrant color grading, 
        excitement and joy radiating from every moment."""
    
    async def generate_full_itinerary_video(
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
        Generate travel vlog videos that MATCH the actual itinerary activities.
        
        Each day's 8-second video shows the person from the photo doing:
        - The actual morning activity (time allocated by importance)
        - The actual afternoon activity (time allocated by importance)
        - The actual evening activity (time allocated by importance)
        
        Style: Exciting travel vlog with genuine emotions and dynamic pacing
        """
        
        logger.info("="*80)
        logger.info("🎥 GENERATING TRAVEL VLOG VIDEO WITH TIMELINE GUIDANCE")
        logger.info(f"📍 Destination: {destination}")
        logger.info(f"📅 Duration: {duration} days")
        logger.info(f"🎬 Style: Exciting travel vlog with smart time allocation")
        logger.info("="*80)
        
        # Upload user photo if localhost
        if user_image_url.startswith("http://localhost") or user_image_url.startswith("http://127.0.0.1"):
            logger.info("🔄 Uploading user photo...")
            filename = user_image_url.split("/uploads/", 1)[-1]
            local_path = f"uploads/{filename}"
            
            public_url = self.upload_file_to_kie(local_path)
            if public_url:
                user_image_url = public_url
            else:
                return {"success": False, "error": "Failed to upload user photo"}
        
        day_video_paths = []
        
        for day_num in range(1, duration + 1):
            logger.info("="*60)
            logger.info(f"🎬 DAY {day_num} - Creating vlog video with timeline guidance")
            logger.info("="*60)
            
            if progress_callback:
                progress_callback({
                    "current_day": day_num,
                    "total_days": duration,
                    "progress": int((day_num - 1) / duration * 90),
                    "current_stage": f"🎬 Creating Day {day_num} travel vlog...",
                    "completed_days": day_num - 1
                })
            
            # Get THIS day's actual activities
            day_idx = day_num - 1
            day_activities_data = daily_activities[day_idx] if day_idx < len(daily_activities) else {}
            
            # Log what activities we're visualizing
            logger.info(f"📋 Activities to visualize with smart timing:")
            logger.info(f"   🌅 Morning: {day_activities_data.get('morning', {}).get('name', 'N/A')}")
            logger.info(f"   ☀️ Afternoon: {day_activities_data.get('afternoon', {}).get('name', 'N/A')}")
            logger.info(f"   🌙 Evening: {day_activities_data.get('evening', {}).get('name', 'N/A')}")
            
            # Generate prompt with timeline guidance
            try:
                matched_prompt = await self.generate_activity_matched_prompt(
                    day_num=day_num,
                    total_days=duration,
                    day_activities=day_activities_data,
                    destination=destination
                )
            except Exception as e:
                logger.error(f"❌ Error generating prompt: {e}")
                matched_prompt = self._create_fallback_matched_prompt(day_num, day_activities_data)
            
            logger.info(f"📝 Timeline-Guided Vlog Prompt: {matched_prompt[:400]}...")
            
            # Save to database
            if video_db and video_id:
                video_db.save_day_video(
                    video_id=video_id,
                    day_number=day_num,
                    prompt=matched_prompt,
                    photos=[user_image_url],
                    status="processing"
                )
            
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
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        status="failed",
                        error_message=result.get('error')
                    )
                continue
            
            task_id = result["task_id"]
            logger.info(f"⏳ Rendering Day {day_num} vlog...")
            
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
            
            video_url = video_result.get("video_url")
            if not video_url:
                logger.error(f"❌ No video URL for Day {day_num}")
                continue
            
            output_filename = f"day_{day_num}_{destination.replace(' ', '_')}.mp4"
            output_path = f"/tmp/{output_filename}"
            
            if self.download_video(video_url, output_path):
                day_video_paths.append(output_path)
                logger.info(f"✅ Day {day_num} vlog video ready!")
                if video_db and video_id:
                    video_db.save_day_video(
                        video_id=video_id,
                        day_number=day_num,
                        video_url=video_url,
                        local_path=output_path,
                        status="completed"
                    )
        
        # Merge videos
        if not day_video_paths:
            return {"success": False, "error": "No day videos generated"}
        
        logger.info("="*60)
        logger.info(f"🎬 Merging {len(day_video_paths)} day vlogs into final video...")
        logger.info("="*60)
        
        if progress_callback:
            progress_callback({
                "current_day": duration,
                "total_days": duration,
                "progress": 92,
                "current_stage": "🎞️ Creating your complete travel vlog...",
                "completed_days": duration
            })
        
        final_video_path = f"videos/{destination.replace(' ', '_')}_trip.mp4"
        merge_success = self._merge_videos(day_video_paths, final_video_path)
        
        # Cleanup
        for temp_path in day_video_paths:
            try:
                os.remove(temp_path)
            except:
                pass
        
        if not merge_success:
            return {"success": False, "error": "Failed to merge videos"}
        
        logger.info("="*80)
        logger.info(f"🎉 YOUR TRAVEL VLOG IS COMPLETE!")
        logger.info(f"📁 Path: {final_video_path}")
        logger.info(f"📅 {len(day_video_paths)} days of exciting travel content")
        logger.info("="*80)
        
        video_filename = os.path.basename(final_video_path)
        
        if progress_callback:
            progress_callback({
                "current_day": duration,
                "total_days": duration,
                "progress": 100,
                "current_stage": "🎬 Your travel vlog is ready!",
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
    
    def _generate_video_with_images(
        self,
        prompt: str,
        image_urls: List[str],
        model: str,
        destination: str,
        duration: int
    ) -> Dict[str, Any]:
        """Generate video with the person from reference photo doing planned activities."""
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
                "negativePrompt": "different person, wrong identity, wrong face, static image, no movement, frozen, text overlay, watermark, logo, boring, dull, lifeless, sad expression"
            }
            
            logger.info(f"🔧 Generating vlog-style video with timeline guidance...")
            
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
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"✅ Downloaded: {output_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return False
    
    def _merge_videos(self, video_paths: List[str], output_path: str) -> bool:
        """Merge day videos with smooth transitions."""
        try:
            from moviepy.editor import VideoFileClip, concatenate_videoclips
            
            clips = [VideoFileClip(p) for p in video_paths]
            final_clip = concatenate_videoclips(clips, method="compose")
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
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
            
            if os.path.exists(output_path):
                logger.info(f"✅ Final vlog video: {output_path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Merge failed: {e}")
            return False