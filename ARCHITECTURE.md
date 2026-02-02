# 🏗️ Architecture Documentation

## System Overview

The AI Travel Itinerary Generator is a full-stack application that combines multiple AI services, external APIs, and database systems to create personalized travel experiences with video generation capabilities.

## 📐 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Web Browser                                                     │   │
│  │  • HTML5/CSS3/JavaScript                                         │   │
│  │  • Responsive Design                                             │   │
│  │  • Real-time Updates (via polling)                               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                            HTTP/REST API
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                                │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Web Framework (main.py)                                 │   │
│  │  • RESTful API Endpoints                                         │   │
│  │  • Request/Response Handling                                     │   │
│  │  • File Upload Management                                        │   │
│  │  • Background Task Orchestration                                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                          Service Layer
                                    │
┌───────────────────────────────────────────────────────────────────────┐
│                          BUSINESS LOGIC LAYER                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │ItineraryService  │  │ DemoDataManager  │  │VideoGenService   │     │
│  │                  │  │                  │  │                  │     │
│  │• Generate plans  │  │• Google Places   │  │• KIE AI API      │     │
│  │• Budget calc     │  │• Geocoding       │  │• Video merge     │     │
│  │• Chat handler    │  │• Smart parsing   │  │• Progress track  │     │
│  │• Validation      │  │• Photo fetch     │  │• File management │     │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘     │
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐                           │
│  │DestinationParser │  │VideoDatabase     │                           │
│  │                  │  │                  │                           │
│  │• LLM parsing     │  │• Session track   │                           │
│  │• Smart matching  │  │• Progress store  │                           │
│  │• Normalization   │  │• Video metadata  │                           │
│  └──────────────────┘  └──────────────────┘                           │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                          External APIs
                                    │
┌──────────────────────────────────────────────────────────────────────┐
│                         DATA/SERVICE LAYER                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ OpenAI   │  │ Google   │  │  KIE AI  │  │  SQLite  │  │  File  │  │
│  │ GPT-4    │  │ Places   │  │  Veo 3.1 │  │    DB    │  │ System │  │
│  │          │  │ Maps     │  │          │  │          │  │        │  │
│  │• Content │  │• Places  │  │• Video   │  │• Sessions│  │•Uploads│  │
│  │  gen     │  │• Geocode │  │  gen     │  │• Videos  │  │•Videos │  │
│  │• Parsing │  │• Timezone│  │• Status  │  │• Tracking│  │        │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

## 🔧 Component Details

### 1. Main Application (`main.py`)

**Purpose**: FastAPI application entry point and orchestration

**Key Responsibilities**:
- HTTP endpoint definitions
- Request validation with Pydantic
- CORS middleware configuration
- Static file serving
- Background task management
- Session state management

**Code Structure**:
```python
app = FastAPI()

# Middleware
app.add_middleware(CORSMiddleware, ...)

# Static files
app.mount("/static", StaticFiles(...))

# Endpoints
@app.post("/api/create-itinerary")
async def create_itinerary(request: ItineraryRequest)

@app.post("/api/generate-video")
async def generate_video(request: VideoGenerationRequest)

# Background tasks
async def generate_video_background(...)
```

**Data Flow**:
```
Request → Validation → Service Call → Response
                ↓
         Background Task (for videos)
```

### 2. Itinerary Service (`itinerary_service.py`)

**Purpose**: Core business logic for itinerary generation and management

**Key Components**:

#### Budget Validation
```python
async def validate_budget(
    destination: str,
    budget: float,
    duration: int,
    travelers: int,
    include_flights: bool,
    include_hotels: bool
) -> Dict[str, Any]
```

**Logic**:
1. Fetch destination data
2. Calculate minimum costs based on real data
3. Validate budget ≥ 90% of minimum
4. Return breakdown and recommendations

#### Itinerary Generation
```python
async def generate_itinerary(
    destination: str,
    budget: float,
    duration: int,
    travelers: int,
    activity_preference: str,
    include_flights: bool,
    include_hotels: bool
) -> Dict[str, Any]
```

**Process**:
1. Fetch comprehensive location data
2. Generate realistic budget breakdown
3. Create day-by-day activities using LLM
4. Generate attractions summary
5. Return complete itinerary with photos

#### Budget Breakdown Algorithm
```python
async def _generate_realistic_budget_breakdown(...)
```

**Algorithm**:
```
1. IF include_flights:
   - Find cheapest flight from location_data
   - Allocate: cheapest_price × travelers
   
2. IF include_hotels:
   - Get budget hotels from Google Places
   - Calculate: avg_price × duration × rooms
   - Cap at 40% of remaining budget
   
3. Food allocation:
   - Get restaurant data from Google Places
   - Calculate: avg_meal × 3 × duration × travelers
   - Cap at 35% of remaining budget
   
4. Remaining budget distribution:
   - Travel: 20% of remaining
   - Activities: 35% of remaining
   - Buffer: 10% of remaining
```

#### Chat-Based Modifications
```python
async def process_chat_message(
    message: str,
    current_itinerary: Dict[str, Any],
    conversation_history: List[Dict[str, str]]
) -> Dict[str, Any]
```

**Workflow**:
```
1. Parse user message with LLM
2. Identify modification intent:
   - Question → Answer directly
   - Modification → Propose changes
   - Confirmation → Apply changes
3. Preserve unchanged parameters
4. Validate new budget if changed
5. Regenerate itinerary if confirmed
```

### 3. Demo Data Manager (`demo_data.py`)

**Purpose**: Interface with Google APIs for real destination data

**Key Features**:

#### Smart Destination Resolution
```python
def get_destination_info(destination: str) -> Dict[str, Any]
```

**Process**:
1. Use LLM-based smart parser (if available)
2. Fallback to manual geocoding
3. Extract city, country, coordinates
4. Get timezone information
5. Return structured data

#### Data Fetching Methods

**Top Attractions**:
```python
def fetch_top_attractions(
    destination: str,
    lat: float,
    lng: float,
    max_results: int = 10
) -> List[Dict[str, Any]]
```

**Quality Algorithm**:
```
1. Query multiple attraction types
2. Filter: rating ≥ 4.0 AND has photo
3. Calculate quality score: rating × min(reviews/100, 10)
4. Sort by quality score
5. Remove duplicates
6. Return top N
```

**Hotels & Restaurants**:
```python
def fetch_hotels(destination, lat, lng)
def fetch_restaurants(destination, lat, lng)
```

**Process**:
1. Nearby search within radius
2. Extract price level
3. Calculate average prices
4. Categorize by budget/mid-range/luxury
5. Return with ratings and locations

### 4. Destination Parser (`destination_parser.py`)

**Purpose**: Intelligent destination parsing using LLM

**Architecture**:
```python
class DestinationParser:
    def parse_destination(user_input: str) -> Dict[str, Any]
    
class SmartDestinationManager:
    def process_destination(user_input: str) -> Dict[str, Any]
```

**Parsing Logic**:
```
Input: Any text (country, city, sentence, nickname)
       ↓
    LLM Analysis
       ↓
    Normalize to: "City, Country"
       ↓
    Google Geocoding
       ↓
    Complete destination info with coordinates
```

**Examples**:
```
"Finland" → Helsinki, Finland (suggests capital)
"I want to visit Japan" → Tokyo, Japan
"NYC" → New York City, USA
"Parris" → Paris, France (corrects spelling)
"Big Apple" → New York City, USA
```

### 5. Video Generation Service (`video_service.py`)

**Purpose**: Generate day-by-day travel videos using Google Veo 3.1

**Architecture**:

#### Main Workflow
```python
def generate_full_itinerary_video(
    user_image_url: str,
    destination: str,
    duration: int,
    daily_activities: List[Dict],
    model: str,
    progress_callback: Callable
) -> Dict[str, Any]
```

**Process**:
```
1. Upload user photo to KIE AI (if localhost)
2. For each day (1 to duration):
   a. Collect photos (user + 1-2 location photos)
   b. Create simple prompt
   c. Generate 8-second video via KIE AI API
   d. Wait for completion
   e. Download video
   f. Save to database
3. Merge all day videos with MoviePy
4. Save final video
5. Update database
```

#### Photo Collection Strategy
```python
def _collect_day_photos(
    user_image_url: str,
    day_activities: Dict
) -> List[str]
```

**Rules**:
- 1 user photo (always first)
- 1-2 location photos from Google Places
- Max 3 photos per day
- Use 400px resolution for Google Places photos
- Skip localhost URLs

#### Video Generation
```python
def _generate_video_with_images(
    prompt: str,
    image_urls: List[str],
    model: str
) -> Dict[str, Any]
```

**API Call**:
```json
{
  "prompt": "...",
  "imageUrls": ["photo1", "photo2", "photo3"],
  "model": "veo3_fast",
  "aspectRatio": "16:9",
  "generationType": "REFERENCE_2_VIDEO",
  "enableTranslation": true,
  "generateAudio": true
}
```

#### Video Merging
```python
def _merge_videos(
    video_paths: List[str],
    output_path: str
) -> bool
```

**Process**:
1. Load all day videos with MoviePy
2. Concatenate with "compose" method
3. Write to output with codec settings
4. Clean up temp files

### 6. Video Database (`video_database.py`)

**Purpose**: Track video generation progress and metadata

**Schema**:

#### Video Sessions Table
```sql
CREATE TABLE video_sessions (
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
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

#### Day Videos Table
```sql
CREATE TABLE day_videos (
    id INTEGER PRIMARY KEY,
    video_id TEXT NOT NULL,
    day_number INTEGER NOT NULL,
    task_id TEXT,
    video_url TEXT,
    local_path TEXT,
    prompt TEXT,
    photos_json TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES video_sessions(video_id),
    UNIQUE(video_id, day_number)
)
```

**Key Methods**:
```python
def create_session(video_id, itinerary_id, ...)
def update_session(video_id, **kwargs)
def get_session(video_id)
def save_day_video(video_id, day_number, ...)
def get_completed_day_videos(video_id)
```

## 🔄 Data Flow Diagrams

### Itinerary Generation Flow

```
User Input
    │
    ├─→ Destination Parsing (LLM + Geocoding)
    │   └─→ Coordinates, Timezone
    │
    ├─→ Google Places Data Fetch
    │   ├─→ Attractions (top 10)
    │   ├─→ Activities (top 7)
    │   ├─→ Hotels (for budget)
    │   └─→ Restaurants (for budget)
    │
    ├─→ Budget Validation
    │   └─→ Calculate minimum costs
    │       └─→ Pass/Fail
    │
    └─→ LLM Itinerary Generation
        ├─→ Budget breakdown
        ├─→ Day-by-day activities
        └─→ Attractions summary
            │
            └─→ JSON Response with Photos
```

### Video Generation Flow

```
User Photo Upload
    │
    ├─→ Upload to KIE AI
    │   └─→ Public URL
    │
    └─→ For Each Day:
        │
        ├─→ Collect Photos
        │   ├─→ User photo
        │   └─→ Location photos (1-2)
        │
        ├─→ Create Prompt
        │
        ├─→ Call KIE AI API
        │   └─→ Task ID
        │
        ├─→ Poll Status (every 10s)
        │   └─→ Wait for completion
        │
        ├─→ Download Video
        │
        └─→ Save to Database
            │
            └─→ After All Days:
                │
                ├─→ Merge Videos (MoviePy)
                │
                └─→ Final Video
```

### Chat Modification Flow

```
User Message
    │
    ├─→ LLM Analysis
    │   ├─→ Intent Recognition
    │   │   ├─→ Question
    │   │   ├─→ Modification
    │   │   └─→ Confirmation
    │   │
    │   └─→ Parameter Extraction
    │       └─→ Preserve unchanged params
    │
    ├─→ IF Question:
    │   └─→ Answer directly
    │
    ├─→ IF Modification:
    │   ├─→ Propose changes
    │   └─→ Ask for confirmation
    │
    └─→ IF Confirmation:
        ├─→ Validate budget
        ├─→ Regenerate itinerary
        └─→ Return updated data
```

## 🗄️ State Management

### In-Memory State
```python
# Active itineraries (user sessions)
active_itineraries = {
    "uuid-1": {itinerary_data},
    "uuid-2": {itinerary_data},
    ...
}

# Video generation tasks
video_tasks = {
    "video-uuid-1": {
        "status": "processing",
        "progress": 45,
        "current_day": 3,
        ...
    },
    ...
}
```

### Database State
- Video sessions (persistent)
- Day videos metadata (persistent)
- Progress tracking (persistent)

### File System State
- User uploads: `/uploads/`
- Generated videos: `/videos/`
- Temporary files: `/tmp/`

## 🔐 Security Considerations

### API Key Management
```python
# Environment variables (never hardcoded)
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
KIE_AI_API_KEY = os.getenv("KIE_AI_API_KEY")
```

### Input Validation
```python
# Pydantic models for request validation
class ItineraryRequest(BaseModel):
    destination: str
    budget: float
    duration: int
    travelers: int
    # ...
```

### CORS Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### File Upload Security
```python
# Validate file types
if not file.content_type.startswith("image/"):
    raise HTTPException(400, "File must be an image")

# Generate unique filenames
unique_filename = f"{uuid.uuid4()}.{file_extension}"
```

## 📊 Performance Optimizations

### 1. Photo Management
- Limit to top 10-15 photos total
- Quality scoring: rating × min(reviews/100, 10)
- Remove duplicates
- Direct URLs for Google Places (no downloads)

### 2. API Call Optimization
- Single search for simple queries
- Batch photo fetching
- Efficient prompt engineering

### 3. Video Generation
- Fast model option (`veo3_fast`)
- Parallel day generation (future)
- Efficient merging with MoviePy

### 4. Database
- Indexed queries on video_id
- Efficient session tracking
- Minimal writes per operation

## 🔄 Background Task Management

### Video Generation Background Task
```python
async def generate_video_background(
    video_id: str,
    user_photo_url: str,
    daily_activities: List[Dict],
    destination: str,
    duration: int,
    itinerary_id: str
):
    # Create DB session
    # For each day:
    #   - Generate video
    #   - Update progress
    #   - Save to DB
    # Merge all videos
    # Update final status
```

**Key Features**:
- Runs asynchronously via `asyncio.create_task()`
- Updates progress in real-time
- Database persistence for recovery
- Error handling and logging

## 🧪 Error Handling Strategy

### Graceful Degradation
```python
# LLM parser not available → Manual parsing
if self.smart_parser:
    result = self.smart_parser.process_destination(...)
else:
    result = self._manual_geocoding(...)

# Google API fails → Fallback data
if not self.google_api_key:
    return self._get_fallback_data(...)
```

### Comprehensive Logging
```python
logger.info(f"📍 Resolved: '{destination}' → {city}, {country}")
logger.warning(f"⚠️ Geocoding failed: {status}")
logger.error(f"❌ Error: {error_message}")
```

### Database Tracking
- All video generation steps logged
- Status updates for debugging
- Error messages stored

## 🚀 Deployment Considerations

### Production Checklist
- [ ] Configure CORS properly
- [ ] Set up environment variables
- [ ] Enable database backups
- [ ] Configure logging to files
- [ ] Set up monitoring
- [ ] Use production ASGI server (Gunicorn/Uvicorn)
- [ ] Implement rate limiting
- [ ] Set up CDN for videos
- [ ] Configure proper error pages

### Scalability
- Use Redis for session state
- Implement queue system for video generation
- Separate video processing workers
- Database connection pooling
- Load balancing

## 📈 Monitoring & Observability

### Key Metrics
- Itinerary generation time
- Video generation success rate
- API call latency
- Error rates
- User session duration

### Logging Levels
```python
logging.INFO:  # Normal operations
logging.WARNING:  # Degraded functionality
logging.ERROR:  # Errors requiring attention
logging.DEBUG:  # Detailed debugging info
```