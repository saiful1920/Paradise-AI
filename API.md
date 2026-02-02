# 📡 API Documentation

Complete reference for the AI Travel Itinerary Generator REST API.

**Base URL**: `http://localhost:8001`

**Content Type**: `application/json`

## 📋 Table of Contents

- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Create Itinerary](#1-create-itinerary)
  - [Get Itinerary](#2-get-itinerary)
  - [Upload Photo](#3-upload-photo)
  - [Generate Video](#4-generate-video)
  - [Get Video Status](#5-get-video-status)
  - [Chat with AI](#6-chat-with-ai)
  - [Reallocate Budget](#7-reallocate-budget)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Rate Limits](#rate-limits)
- [Examples](#examples)

## 🔐 Authentication

Currently, the API does not require authentication. This should be implemented for production use.

**Future**: Bearer token authentication will be added.

## 🌐 Endpoints

### 1. Create Itinerary

Generate a new personalized travel itinerary.

**Endpoint**: `POST /api/create-itinerary`

**Request Body**:
```json
{
  "destination": "string",          // City, country, or any location
  "budget": 3000.00,                // Total budget in USD
  "duration": 7,                    // Number of days
  "travelers": 2,                   // Number of travelers
  "activity_preference": "moderate", // "relaxed", "moderate", or "high"
  "include_flights": true,          // Include flight costs
  "include_hotels": true,           // Include hotel costs
  "user_location": "New York"       // Optional: Starting location for flights
}
```

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `destination` | string | Yes | Destination (handles any format: "Paris", "Japan", "NYC") |
| `budget` | float | Yes | Total budget in USD (minimum $500) |
| `duration` | integer | Yes | Trip duration in days (1-30) |
| `travelers` | integer | Yes | Number of travelers (1-20) |
| `activity_preference` | string | Yes | Activity level: "relaxed", "moderate", "high" |
| `include_flights` | boolean | Yes | Whether to include flight costs |
| `include_hotels` | boolean | Yes | Whether to include hotel costs |
| `user_location` | string | No | Starting location (default: "New York") |

**Response** (200 OK):
```json
{
  "itinerary_id": "550e8400-e29b-41d4-a716-446655440000",
  "itinerary": {
    "destination": {
      "name": "Paris",
      "country": "France",
      "description": "A vibrant destination in France",
      "timezone": "Europe/Paris",
      "coordinates": {
        "lat": 48.8566,
        "lng": 2.3522
      }
    },
    "duration": 7,
    "travelers": 2,
    "total_budget": 3000.00,
    "activity_preference": "moderate",
    "include_flights": true,
    "include_hotels": true,
    "budget_breakdown": {
      "categories": {
        "flights": {
          "amount": 1000.00,
          "percentage": 33.33
        },
        "hotels": {
          "amount": 840.00,
          "percentage": 28.00
        },
        "food": {
          "amount": 630.00,
          "percentage": 21.00
        },
        "travel": {
          "amount": 270.00,
          "percentage": 9.00
        },
        "activities": {
          "amount": 260.00,
          "percentage": 8.67
        }
      },
      "total_allocated": 3000.00,
      "remaining_budget": 0.00,
      "remaining_percentage": 0.00
    },
    "daily_activities": [
      {
        "day": 1,
        "title": "Day 1 - Arrival in Paris",
        "hotel": "Hotel Eiffel Turenne",
        "morning": {
          "time": "09:00 - 12:00",
          "name": "Eiffel Tower",
          "description": "Start your Paris adventure with a visit to the iconic Eiffel Tower",
          "photo_url": "https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference=..."
        },
        "lunch": {
          "restaurant": "Le Jules Verne",
          "description": "Fine dining with panoramic views"
        },
        "afternoon": {
          "time": "13:00 - 17:00",
          "name": "Louvre Museum",
          "description": "Explore the world's largest art museum",
          "photo_url": "https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference=..."
        },
        "dinner": {
          "restaurant": "Bistrot Paul Bert",
          "description": "Classic Parisian bistro experience"
        },
        "evening": {
          "time": "18:00 - 21:00",
          "name": "Seine River Cruise",
          "description": "Romantic evening cruise",
          "photo_url": "https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference=..."
        }
      }
      // ... more days
    ],
    "attractions_summary": {
      "attractions": {
        "description": "Paris offers world-renowned attractions",
        "items": [
          "Eiffel Tower - Iconic iron lattice tower",
          "Louvre Museum - World's largest art museum",
          "Notre-Dame Cathedral - Gothic masterpiece",
          "Arc de Triomphe - Monumental arch",
          "Sacré-Cœur - Stunning basilica"
        ],
        "photos": [
          "https://maps.googleapis.com/...",
          "https://maps.googleapis.com/..."
        ]
      },
      "activities": {
        "description": "Experience the best of Paris",
        "items": [
          "Seine River Cruise - Romantic boat tour",
          "Montmartre Walking Tour - Artist district",
          "Wine Tasting - French wine experience",
          "Cooking Class - Learn French cuisine",
          "Museum Pass - Access to multiple museums"
        ],
        "photos": [
          "https://maps.googleapis.com/...",
          "https://maps.googleapis.com/..."
        ]
      }
    },
    "hotels": [
      {
        "name": "Hotel Eiffel Turenne",
        "category": "mid_range",
        "rating": 4.5,
        "price_per_night": 120.00,
        "location": {
          "lat": 48.8566,
          "lng": 2.3522
        },
        "address": "20 Avenue de Tourville, 75007 Paris"
      }
      // ... more hotels
    ],
    "restaurants": [
      {
        "name": "Le Jules Verne",
        "cuisine": "French, Fine Dining",
        "price_level": 4,
        "rating": 4.7,
        "avg_price": 100.00,
        "location": {
          "lat": 48.8584,
          "lng": 2.2945
        },
        "address": "Eiffel Tower, 75007 Paris"
      }
      // ... more restaurants
    ],
    "created_at": "2024-12-13T10:30:00Z"
  }
}
```

**Error Response** (400 Bad Request - Insufficient Budget):
```json
{
  "error": "insufficient_budget",
  "message": "Your budget of $1,000.00 is a bit low. We recommend at least $2,500.00 for a comfortable 7-day trip for 2 travelers to Paris.",
  "minimum_budget": 2500.00,
  "current_budget": 1000.00
}
```

**Example cURL**:
```bash
curl -X POST http://localhost:8001/api/create-itinerary \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Paris",
    "budget": 3000,
    "duration": 7,
    "travelers": 2,
    "activity_preference": "moderate",
    "include_flights": true,
    "include_hotels": true,
    "user_location": "New York"
  }'
```

---

### 2. Get Itinerary

Retrieve an existing itinerary by ID.

**Endpoint**: `GET /api/itinerary/{itinerary_id}`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `itinerary_id` | string (UUID) | Yes | Unique itinerary identifier |

**Response** (200 OK):
```json
{
  "destination": { ... },
  "duration": 7,
  "travelers": 2,
  "total_budget": 3000.00,
  "budget_breakdown": { ... },
  "daily_activities": [ ... ],
  "attractions_summary": { ... },
  "hotels": [ ... ],
  "restaurants": [ ... ],
  "created_at": "2024-12-13T10:30:00Z"
}
```

**Error Response** (404 Not Found):
```json
{
  "detail": "Itinerary not found"
}
```

**Example cURL**:
```bash
curl http://localhost:8001/api/itinerary/550e8400-e29b-41d4-a716-446655440000
```

---

### 3. Upload Photo

Upload a user photo for video generation.

**Endpoint**: `POST /api/upload-photo`

**Request**: Multipart form data

**Form Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Image file (JPEG, PNG, GIF, WebP) |

**Response** (200 OK):
```json
{
  "success": true,
  "filename": "a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
  "url": "/uploads/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
}
```

**Error Response** (400 Bad Request):
```json
{
  "detail": "File must be an image"
}
```

**Example cURL**:
```bash
curl -X POST http://localhost:8001/api/upload-photo \
  -F "file=@/path/to/photo.jpg"
```

---

### 4. Generate Video

Start video generation for an itinerary.

**Endpoint**: `POST /api/generate-video`

**Request Body**:
```json
{
  "itinerary_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_photo_filename": "a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
}
```

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `itinerary_id` | string (UUID) | Yes | ID of the itinerary to create video for |
| `user_photo_filename` | string | Yes | Filename from upload-photo endpoint |

**Response** (200 OK):
```json
{
  "success": true,
  "video_id": "video-uuid-1234-5678-90ab-cdef",
  "message": "Video generation started"
}
```

**Error Response** (404 Not Found):
```json
{
  "detail": "Itinerary not found"
}
```

**Example cURL**:
```bash
curl -X POST http://localhost:8001/api/generate-video \
  -H "Content-Type: application/json" \
  -d '{
    "itinerary_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_photo_filename": "a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
  }'
```

---

### 5. Get Video Status

Check the status of video generation.

**Endpoint**: `GET /api/video-status/{video_id}`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `video_id` | string (UUID) | Yes | Video generation task ID |

**Response** (200 OK - Processing):
```json
{
  "status": "processing",
  "progress": 45,
  "total_days": 7,
  "completed_days": 3,
  "current_day": 4,
  "itinerary_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-12-13T10:35:00Z",
  "stage": "processing",
  "message": "Generating Day 4 video...",
  "current_stage": "Generating Day 4 video..."
}
```

**Response** (200 OK - Completed):
```json
{
  "status": "completed",
  "progress": 100,
  "video_url": "/videos/Paris_trip_final.mp4",
  "video_path": "videos/Paris_trip_final.mp4",
  "completed_at": "2024-12-13T10:50:00Z",
  "days_covered": 7,
  "total_days": 7,
  "completed_days": 7,
  "message": "Video complete! 7 days merged into final video",
  "current_stage": "Complete!"
}
```

**Response** (200 OK - Failed):
```json
{
  "status": "failed",
  "error": "Video generation failed: API error",
  "message": "Video generation failed: API error"
}
```

**Error Response** (404 Not Found):
```json
{
  "detail": "Video not found"
}
```

**Example cURL**:
```bash
curl http://localhost:8001/api/video-status/video-uuid-1234-5678-90ab-cdef
```

**Polling Pattern**:
```javascript
// Poll every 5 seconds
const checkStatus = async (videoId) => {
  const response = await fetch(`/api/video-status/${videoId}`);
  const status = await response.json();
  
  if (status.status === 'completed') {
    // Video ready!
    window.location.href = status.video_url;
  } else if (status.status === 'failed') {
    // Handle error
    console.error(status.error);
  } else {
    // Still processing, check again
    setTimeout(() => checkStatus(videoId), 5000);
  }
};
```

---

### 6. Chat with AI

Modify itinerary through conversational interface.

**Endpoint**: `POST /api/chat`

**Request Body**:
```json
{
  "itinerary_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Change destination to Tokyo",
  "conversation_history": [
    {
      "role": "user",
      "content": "What activities are planned for day 2?"
    },
    {
      "role": "assistant",
      "content": "On Day 2, you have morning visit to Louvre, lunch at..."
    }
  ]
}
```

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `itinerary_id` | string (UUID) | Yes | ID of the itinerary to modify |
| `message` | string | Yes | User's chat message |
| `conversation_history` | array | No | Previous conversation messages |

**Response** (200 OK - Question):
```json
{
  "response": "On Day 2, you have a morning visit to the Louvre Museum, lunch at Bistrot Paul Bert, and an afternoon walking tour of Montmartre. Would you like more details about any of these?",
  "modifications_made": false,
  "updated_itinerary": null,
  "requires_confirmation": false,
  "proposed_changes": {}
}
```

**Response** (200 OK - Modification Proposal):
```json
{
  "response": "I'd be happy to change your destination from Paris to Tokyo! I'll keep your current budget of $3,000.00, 7 days, 2 travelers, and moderate activity level. Should I proceed?",
  "modifications_made": false,
  "updated_itinerary": null,
  "requires_confirmation": true,
  "proposed_changes": {
    "destination": "Tokyo",
    "budget": null,
    "duration": null,
    "travelers": null,
    "activity_preference": null,
    "include_flights": null,
    "include_hotels": null
  }
}
```

**Response** (200 OK - Applied Changes):
```json
{
  "response": "Great! I've updated your itinerary to Tokyo.",
  "modifications_made": true,
  "updated_itinerary": {
    "destination": {
      "name": "Tokyo",
      "country": "Japan",
      // ... complete itinerary object
    },
    "duration": 7,
    "travelers": 2,
    // ... rest of itinerary
  },
  "requires_confirmation": false,
  "proposed_changes": {}
}
```

**Response** (200 OK - Budget Warning):
```json
{
  "response": "Your budget of $1,500.00 is a bit low. We recommend at least $2,800.00 for a comfortable 7-day trip for 2 travelers to Tokyo. Would you like to increase your budget or adjust your trip parameters?",
  "modifications_made": false,
  "requires_confirmation": false,
  "proposed_changes": {},
  "budget_warning": true,
  "minimum_budget": 2800.00
}
```

**Example cURL**:
```bash
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "itinerary_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Change destination to Tokyo",
    "conversation_history": []
  }'
```

**Example Conversation Flow**:
```
User: "What's planned for day 3?"
→ Response: Direct answer, no modifications

User: "Change to Tokyo"
→ Response: Proposal with confirmation request

User: "Yes, please"
→ Response: Updated itinerary with Tokyo

User: "Increase budget to $5000"
→ Response: Proposal with new budget

User: "Confirm"
→ Response: Updated itinerary with new budget
```

---

### 7. Reallocate Budget

Redistribute remaining budget to selected categories.

**Endpoint**: `POST /api/reallocate-budget`

**Request Body**:
```json
{
  "itinerary_id": "550e8400-e29b-41d4-a716-446655440000",
  "selected_categories": ["activities", "food"]
}
```

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `itinerary_id` | string (UUID) | Yes | ID of the itinerary |
| `selected_categories` | array of strings | Yes | Categories to receive extra budget |

**Valid Categories**:
- `flights`
- `hotels`
- `food`
- `travel`
- `activities`

**Response** (200 OK):
```json
{
  "success": true,
  "budget_breakdown": {
    "categories": {
      "flights": {
        "amount": 1000.00,
        "percentage": 33.33
      },
      "hotels": {
        "amount": 840.00,
        "percentage": 28.00
      },
      "food": {
        "amount": 730.00,
        "percentage": 24.33
      },
      "travel": {
        "amount": 270.00,
        "percentage": 9.00
      },
      "activities": {
        "amount": 160.00,
        "percentage": 5.33
      }
    },
    "total_allocated": 3000.00,
    "remaining_budget": 0.00
  }
}
```

**Error Response** (404 Not Found):
```json
{
  "detail": "Itinerary not found"
}
```

**Example cURL**:
```bash
curl -X POST http://localhost:8001/api/reallocate-budget \
  -H "Content-Type: application/json" \
  -d '{
    "itinerary_id": "550e8400-e29b-41d4-a716-446655440000",
    "selected_categories": ["activities", "food"]
  }'
```

---

## 📊 Data Models

### Itinerary Object

```typescript
interface Itinerary {
  destination: Destination;
  duration: number;
  travelers: number;
  total_budget: number;
  activity_preference: "relaxed" | "moderate" | "high";
  include_flights: boolean;
  include_hotels: boolean;
  budget_breakdown: BudgetBreakdown;
  daily_activities: DayActivity[];
  attractions_summary: AttractionsSummary;
  hotels: Hotel[];
  restaurants: Restaurant[];
  created_at: string; // ISO timestamp
}
```

### Destination Object

```typescript
interface Destination {
  name: string;
  country: string;
  description: string;
  timezone: string;
  coordinates: {
    lat: number;
    lng: number;
  };
  original_input?: string;
  normalized_name?: string;
  was_country?: boolean;
  suggested_city?: string;
}
```

### Budget Breakdown Object

```typescript
interface BudgetBreakdown {
  categories: {
    flights: BudgetCategory;
    hotels: BudgetCategory;
    food: BudgetCategory;
    travel: BudgetCategory;
    activities: BudgetCategory;
  };
  total_allocated: number;
  remaining_budget: number;
  remaining_percentage: number;
}

interface BudgetCategory {
  amount: number;
  percentage: number;
}
```

### Day Activity Object

```typescript
interface DayActivity {
  day: number;
  title: string;
  hotel?: string;
  morning: Activity;
  lunch: Meal;
  afternoon: Activity;
  dinner: Meal;
  evening: Activity;
}

interface Activity {
  time: string;
  name: string;
  description: string;
  photo_url?: string | null;
}

interface Meal {
  restaurant: string;
  description: string;
}
```

### Hotel Object

```typescript
interface Hotel {
  name: string;
  category: "budget" | "mid_range" | "luxury";
  rating: number;
  price_per_night: number;
  location: {
    lat: number;
    lng: number;
  };
  address: string;
}
```

### Restaurant Object

```typescript
interface Restaurant {
  name: string;
  cuisine: string;
  price_level: number; // 0-4
  rating: number;
  avg_price: number;
  location: {
    lat: number;
    lng: number;
  };
  address: string;
}
```

---

## ⚠️ Error Handling

### Standard Error Response

```json
{
  "detail": "Error message here"
}
```

### Common HTTP Status Codes

| Code | Meaning | When It Occurs |
|------|---------|----------------|
| 200 | OK | Successful request |
| 400 | Bad Request | Invalid input, insufficient budget |
| 404 | Not Found | Itinerary/video not found |
| 500 | Internal Server Error | Server-side error |

### Specific Error Cases

**Insufficient Budget**:
```json
{
  "error": "insufficient_budget",
  "message": "Your budget of $1,000.00 is too low...",
  "minimum_budget": 2500.00,
  "current_budget": 1000.00
}
```

**Invalid File Type**:
```json
{
  "detail": "File must be an image"
}
```

**Video Generation Failed**:
```json
{
  "status": "failed",
  "error": "API error: Image size exceeds limit",
  "message": "Video generation failed: API error"
}
```

---

## 🚦 Rate Limits

Currently, there are no rate limits implemented. For production:

**Recommended Limits**:
- Itinerary generation: 5 requests per minute
- Video generation: 1 request per 5 minutes
- Chat: 10 requests per minute
- Photo upload: 5 uploads per minute

---

## 💡 Examples

### Complete Workflow Example

```javascript
// 1. Upload user photo
const formData = new FormData();
formData.append('file', photoFile);

const uploadResponse = await fetch('/api/upload-photo', {
  method: 'POST',
  body: formData
});
const { filename } = await uploadResponse.json();

// 2. Create itinerary
const itineraryResponse = await fetch('/api/create-itinerary', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    destination: 'Paris',
    budget: 3000,
    duration: 7,
    travelers: 2,
    activity_preference: 'moderate',
    include_flights: true,
    include_hotels: true
  })
});
const { itinerary_id, itinerary } = await itineraryResponse.json();

// 3. Chat to modify
const chatResponse = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    itinerary_id: itinerary_id,
    message: 'Change to Tokyo',
    conversation_history: []
  })
});
const chatResult = await chatResponse.json();

if (chatResult.requires_confirmation) {
  // Show confirmation dialog
  // Then send "yes" to confirm
}

// 4. Generate video
const videoResponse = await fetch('/api/generate-video', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    itinerary_id: itinerary_id,
    user_photo_filename: filename
  })
});
const { video_id } = await videoResponse.json();

// 5. Poll video status
const pollStatus = async () => {
  const statusResponse = await fetch(`/api/video-status/${video_id}`);
  const status = await statusResponse.json();
  
  if (status.status === 'completed') {
    window.location.href = status.video_url;
  } else if (status.status === 'processing') {
    setTimeout(pollStatus, 5000);
  } else {
    console.error('Video failed:', status.error);
  }
};

pollStatus();
```

---

## 📚 Additional Resources

- [README.md](README.md) - Project overview and setup
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture details
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Google Places API Docs](https://developers.google.com/maps/documentation/places/web-service)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

---

**API Version**: 1.0  
**Last Updated**: December 2024  
**Contact**: AI Team - Spartech Agency