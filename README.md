# 🌍 AI Travel Itinerary Generator

An intelligent travel planning application that generates personalized itineraries with AI-powered video generation capabilities. Built with FastAPI, OpenAI GPT-4, and Google Veo 3.1 for creating immersive travel experiences.

![Project Banner](https://img.shields.io/badge/AI-Travel%20Planner-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-orange)

## 🌟 Features

### Core Functionality
- **🤖 AI-Powered Itinerary Generation**: Uses GPT-4o-mini to create personalized day-by-day travel plans
- **🎥 Video Generation**: Creates travel videos using Google Veo 3.1 via KIE AI API
- **💰 Smart Budget Planning**: Realistic budget allocation using actual Google Places data
- **🗺️ Intelligent Destination Parsing**: Handles any input format (countries, cities, nicknames, misspellings)
- **📸 Photo Integration**: Combines user photos with location images from Google Places
- **💬 Interactive Chat**: Modify itineraries through natural conversation

### Data Sources
- **Google Places API**: Real attraction, activity, hotel, and restaurant data
- **Google Maps Geocoding**: Accurate coordinates and location information
- **Google Time Zone API**: Proper timezone handling
- **OpenAI GPT-4**: Intelligent content generation and parsing

### Advanced Features
- **Day-by-Day Video Generation**: Individual videos for each day that merge into a complete travel video
- **Budget Validation**: Ensures budgets are realistic before generating itineraries
- **Photo Uploading**: Users can upload their photos for personalized videos
- **Database Tracking**: SQLite database tracks video generation progress
- **Responsive Design**: Clean, modern UI that works on all devices

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Jinja2 Templates)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  index.html  │  │itinerary.html│  │  video.html  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (main.py)                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  REST API Endpoints                                  │  │
│  │  • POST /api/create-itinerary                       │  │
│  │  • POST /api/generate-video                         │  │
│  │  • POST /api/chat                                   │  │
│  │  • GET  /api/video-status/{video_id}               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ ItineraryService │  │ DemoDataManager  │  │ VideoGeneration  │
│                  │  │                  │  │     Service      │
│ • Generate plans │  │ • Google Places  │  │                  │
│ • Budget calc    │  │ • Geocoding      │  │ • KIE AI API     │
│ • Chat handler   │  │ • Smart parser   │  │ • Veo 3.1        │
│ • Validation     │  │ • Photo fetch    │  │ • Video merge    │
└──────────────────┘  └──────────────────┘  └──────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Services                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ OpenAI   │  │ Google   │  │  KIE AI  │  │  SQLite  │   │
│  │ GPT-4    │  │ Places   │  │  Veo 3.1 │  │    DB    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.8+
- Google Cloud Platform account with billing enabled
- OpenAI API key
- KIE AI API key (for video generation)

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd ai-travel-itinerary
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up API Keys

Create a `.env` file in the project root:

```env
# Google APIs (REQUIRED)
GOOGLE_PLACES_API_KEY=your_google_places_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key

# OpenAI (REQUIRED)
OPENAI_API_KEY=your_openai_api_key

# KIE AI for Video Generation
KIE_AI_API_KEY=your_kie_ai_api_key
```

### 5. Google Cloud Setup (CRITICAL)

⚠️ **IMPORTANT**: You MUST enable billing on your Google Cloud account!

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **Enable Billing** (add a credit card)
3. Enable these APIs:
   - Places API (New)
   - Geocoding API
   - Time Zone API
   - Maps JavaScript API
4. Create an API key
5. Add to `.env` file

**Without billing enabled, the APIs will not work!**

## 🎯 Quick Start

### 1. Run the Application
```bash
python main.py
```

The server will start at `http://localhost:8001`

### 2. Access the Web Interface
Open your browser and navigate to:
```
http://localhost:8001
```

### 3. Create Your First Itinerary

1. Enter a destination (e.g., "Paris", "Japan", "NYC")
2. Set your budget (e.g., $3000)
3. Choose duration (e.g., 7 days)
4. Select number of travelers
5. Choose activity preference (relaxed/moderate/high)
6. Toggle flights and hotels inclusion
7. Click "Generate Itinerary"

### 4. Generate Travel Video (Optional)

1. Upload your photo
2. Click "Generate Travel Video"
3. Wait for video generation (1-2 minutes per day)
4. Watch your personalized travel video!

## 📁 Project Structure

```
ai-travel-itinerary/
│
├── main.py                      # FastAPI application entry point
├── itinerary_service.py         # Itinerary generation logic
├── demo_data.py                 # Google Places data manager
├── destination_parser.py        # Smart destination parsing (LLM)
├── video_service.py             # Video generation service
├── video_database.py            # SQLite database for video tracking
│
├── static/                      # Static files
│   ├── css/
│   │   ├── itinerary.css       # Itinerary page styles
│   │   └── style.css           # Main page styles
│   └── js/
│       ├── itinerary.js        # Itinerary page logic
│       └── main.js             # Main page logic
│
├── templates/                   # HTML templates
│   ├── index.html              # Home page
│   ├── itinerary.html          # Itinerary display
│   └── video.html              # Video player page
│
├── uploads/                     # User uploaded photos
├── videos/                      # Generated videos
├── requirements.txt             # Python dependencies
├── .env                        # Environment variables (create this)
└── README.md                   # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_PLACES_API_KEY` | Yes | Google Places API key |
| `GOOGLE_MAPS_API_KEY` | Yes | Google Maps API key |
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4 |
| `KIE_AI_API_KEY` | Optional | KIE AI API key for video generation |

### Application Settings

You can modify settings in `main.py`:

```python
# Server configuration
HOST = "0.0.0.0"
PORT = 8001

# Video generation settings
VIDEO_MODEL = "veo3_fast"  # or "veo3" for higher quality
MAX_VIDEO_WAIT_TIME = 600  # seconds
```

## 🎨 Features in Detail

### 1. Intelligent Destination Parsing

The system handles any input format:

```python
"Finland" → "Helsinki, Finland"
"I want to visit Japan" → "Tokyo, Japan"
"NYC" → "New York City, USA"
"Parris" (misspelling) → "Paris, France"
"Big Apple" → "New York City, USA"
```

### 2. Smart Budget Allocation

Budget is allocated based on actual data:

- **Flights**: Real pricing from destination
- **Hotels**: Google Places hotel prices
- **Food**: Restaurant average prices
- **Activities**: Activity cost estimates
- **Transport**: Local transport costs

### 3. Day-by-Day Video Generation

Videos are generated with:

1. User's uploaded photo
2. Location photos from Google Places (top-rated)
3. Cinematic transitions
4. Background music/ambient sounds
5. All days merged into final video

### 4. Interactive Chat Modifications

Users can modify itineraries through chat:

```
User: "Change destination to Paris"
Bot: "I'll update to Paris while keeping your budget..."

User: "Increase duration to 10 days"
Bot: "I'll extend to 10 days. Should I keep the budget?"
```

## 📊 API Endpoints

### Create Itinerary
```http
POST /api/create-itinerary
Content-Type: application/json

{
  "destination": "Paris",
  "budget": 3000,
  "duration": 7,
  "travelers": 2,
  "activity_preference": "moderate",
  "include_flights": true,
  "include_hotels": true
}
```

### Generate Video
```http
POST /api/generate-video
Content-Type: application/json

{
  "itinerary_id": "uuid-here",
  "user_photo_filename": "photo.jpg"
}
```

### Chat with AI
```http
POST /api/chat
Content-Type: application/json

{
  "itinerary_id": "uuid-here",
  "message": "Change to Tokyo",
  "conversation_history": []
}
```

See [API.md](API.md) for complete API documentation.

## 🎥 Video Generation Details

### Workflow

1. **Photo Collection**: User photo + location photos
2. **Day Videos**: Generate 8-second video per day
3. **Merge**: Combine all days into final video
4. **Database**: Track progress in SQLite

### Models Available

- `veo3_fast`: Fast generation (recommended)
- `veo3`: Higher quality, slower

### Requirements

- User photo (uploaded)
- Location photos (from Google Places)
- 8 seconds per day video
- Final video: merged output

## 🐛 Troubleshooting

### Google API Issues

**Problem**: "Geocoding failed" or "No results"
**Solution**: 
1. Verify billing is enabled
2. Check API key has proper permissions
3. Ensure APIs are enabled

### Budget Validation Fails

**Problem**: "Budget insufficient" 
**Solution**: 
- Increase budget
- Reduce duration
- Disable flights/hotels

### Video Generation Issues

**Problem**: Video fails to generate
**Solution**:
1. Check KIE AI API key
2. Verify photo URLs are accessible
3. Check video_db.sqlite database

### Import Errors

**Problem**: Module not found
**Solution**:
```bash
pip install -r requirements.txt
```

## 📈 Performance

### Response Times

- Itinerary generation: 10-30 seconds
- Video generation (per day): 1-2 minutes
- Full video (7 days): 7-14 minutes

### Optimizations

- Caching of Google Places data
- Parallel video generation (future)
- Database indexing for quick lookups

## 🔒 Security

- API keys stored in `.env` (never commit)
- CORS middleware for safe requests
- Input validation on all endpoints
- Secure file uploads

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- **OpenAI**: GPT-4 for intelligent content generation
- **Google**: Places, Maps, and Geocoding APIs
- **KIE AI**: Google Veo 3.1 video generation
- **FastAPI**: Modern Python web framework
- **MoviePy**: Video editing and merging

## 📞 Support

For issues or questions:

1. Check [Troubleshooting](#-troubleshooting)
2. Review [API Documentation](API.md)
3. Check [Architecture](ARCHITECTURE.md)
4. Open an issue on GitHub

## 🚀 Future Enhancements

- [ ] Multi-language support
- [ ] Collaborative trip planning
- [ ] Real-time flight price integration
- [ ] Hotel booking integration
- [ ] Mobile app (Flutter)
- [ ] Social sharing features
- [ ] User accounts and saved trips
- [ ] Payment integration
- [ ] Travel insurance recommendations

## 📊 Tech Stack

### Backend
- Python 3.8+
- FastAPI
- SQLite
- Pydantic

### AI/ML
- OpenAI GPT-4o-mini
- Google Veo 3.1 (via KIE AI)
- LangChain

### APIs
- Google Places API
- Google Maps Geocoding API
- Google Time Zone API
- KIE AI Video API

### Frontend
- HTML5
- CSS3
- JavaScript (Vanilla)
- Jinja2 Templates

### Video Processing
- MoviePy
- FFmpeg (required by MoviePy)

---

**Made with ❤️ for travelers worldwide** 🌍✈️