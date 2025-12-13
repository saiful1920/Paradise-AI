"""
Database module for storing video generation data
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoDatabase:
    """SQLite database for video generation tracking"""
    
    def __init__(self, db_path: str = "video_db.sqlite"):
        self.db_path = db_path
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Video generation sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS video_sessions (
                    video_id TEXT PRIMARY KEY,
                    itinerary_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    total_days INTEGER NOT NULL,
                    user_photo_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    current_day INTEGER DEFAULT 0,
                    completed_days INTEGER DEFAULT 0,
                    current_stage TEXT,
                    final_video_url TEXT,
                    final_video_path TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Day videos table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS day_videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    day_number INTEGER NOT NULL,
                    task_id TEXT,
                    video_url TEXT,
                    local_path TEXT,
                    prompt TEXT,
                    photos_json TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES video_sessions(video_id),
                    UNIQUE(video_id, day_number)
                )
            """)
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise
    
    def create_session(
        self,
        video_id: str,
        itinerary_id: str,
        destination: str,
        total_days: int,
        user_photo_url: str
    ) -> bool:
        """Create new video generation session"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO video_sessions 
                (video_id, itinerary_id, destination, total_days, user_photo_url, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (video_id, itinerary_id, destination, total_days, user_photo_url, "processing"))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Session created: {video_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create session: {e}")
            return False
    
    def update_session(
        self,
        video_id: str,
        **kwargs
    ) -> bool:
        """Update video session"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build update query
            updates = []
            values = []
            
            for key, value in kwargs.items():
                updates.append(f"{key} = ?")
                values.append(value)
            
            # Add updated_at
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            query = f"UPDATE video_sessions SET {', '.join(updates)} WHERE video_id = ?"
            values.append(video_id)
            
            cursor.execute(query, values)
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update session: {e}")
            return False
    
    def get_session(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video session"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM video_sessions WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get session: {e}")
            return None
    
    def save_day_video(
        self,
        video_id: str,
        day_number: int,
        task_id: Optional[str] = None,
        video_url: Optional[str] = None,
        local_path: Optional[str] = None,
        prompt: Optional[str] = None,
        photos: Optional[List[str]] = None,
        status: str = "processing",
        error_message: Optional[str] = None
    ) -> bool:
        """Save or update day video"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            photos_json = json.dumps(photos) if photos else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO day_videos 
                (video_id, day_number, task_id, video_url, local_path, prompt, 
                 photos_json, status, error_message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (video_id, day_number, task_id, video_url, local_path, 
                  prompt, photos_json, status, error_message))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Day {day_number} video saved")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save day video: {e}")
            return False
    
    def get_day_videos(self, video_id: str) -> List[Dict[str, Any]]:
        """Get all day videos for a session"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM day_videos 
                WHERE video_id = ? 
                ORDER BY day_number
            """, (video_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to get day videos: {e}")
            return []
    
    def get_completed_day_videos(self, video_id: str) -> List[Dict[str, Any]]:
        """Get only completed day videos"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM day_videos 
                WHERE video_id = ? AND status = 'completed' AND local_path IS NOT NULL
                ORDER BY day_number
            """, (video_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to get completed day videos: {e}")
            return []