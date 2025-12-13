from typing import Dict, List, Any, Optional
import os
import requests
from datetime import datetime, timedelta
import logging

# Import LLM-based intelligent destination parser
try:
    from destination_parser import SmartDestinationManager
    SMART_PARSER_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Smart destination parser loaded (LLM-based)")
except ImportError:
    SMART_PARSER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Smart destination parser not found, using basic parsing")

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create a more detailed logger for Google API calls
api_logger = logging.getLogger('google_api')
api_logger.setLevel(logging.DEBUG)


class DemoDataManager:
    """Manages all data for the travel itinerary system using Google Places API"""
    
    def __init__(self, google_api_key, google_maps_key, openai_api_key):
        self.google_api_key = google_api_key
        self.google_maps_key = google_maps_key
        self.openai_api_key = openai_api_key
        
        # Initialize smart destination parser (LLM-based)
        if SMART_PARSER_AVAILABLE and self.openai_api_key:
            self.smart_parser = SmartDestinationManager(
                openai_api_key=self.openai_api_key,
                google_api_key=self.google_api_key
            )
            logger.info("✅ Smart destination parser initialized (LLM-powered)")
        else:
            self.smart_parser = None
            if not self.openai_api_key:
                logger.warning("⚠️ OPENAI_API_KEY not found, smart parsing disabled")
        
        # Google Places API endpoints
        self.places_base_url = "https://maps.googleapis.com/maps/api/place"
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
        
        # Fallback demo data for when API is unavailable
        self.fallback_destinations = self._initialize_fallback_data()
        
        if not self.google_api_key:
            logger.warning("=" * 80)
            logger.warning("⚠️  GOOGLE_PLACES_API_KEY not found in environment variables")
            logger.warning("⚠️  Using FALLBACK DEMO DATA (limited to 5 cities)")
            logger.warning("")
            logger.warning("   To use real Google Places data:")
            logger.warning("   1. Go to: https://console.cloud.google.com/")
            logger.warning("   2. **ENABLE BILLING** (REQUIRED! Add credit card)")
            logger.warning("   3. Enable APIs: Places, Geocoding, Time Zone, Maps JavaScript")
            logger.warning("   4. Create API key")
            logger.warning("   5. Add to .env: GOOGLE_PLACES_API_KEY=your_key")
            logger.warning("")
            logger.warning("   See CRITICAL_SETUP_GUIDE.md for detailed instructions")
            logger.warning("=" * 80)
    
    def get_destination_info(self, destination: str) -> Dict[str, Any]:
        """Get destination information using LLM-based smart parser or manual parsing"""
        if not self.google_api_key:
            return self._get_fallback_destination_info(destination)
        
        # Use smart LLM-based parser if available
        if self.smart_parser:
            logger.info(f"🤖 Using LLM-based smart parser for: '{destination}'")
            result = self.smart_parser.process_destination(destination)
            
            if result.get("success"):
                return result
            else:
                logger.warning(f"⚠️ Smart parser failed, falling back to manual parsing")
        else:
            logger.info(f"📍 Smart parser not available, using manual parsing for: '{destination}'")
        
        # Fallback: Manual parsing
        try:
            params = {
                "address": destination,
                "key": self.google_maps_key
            }
            
            response = requests.get(self.geocoding_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                
                # Extract city, country, and timezone information
                address_components = result.get("address_components", [])
                city = destination
                country = "Unknown"
                
                for component in address_components:
                    if "locality" in component["types"]:
                        city = component["long_name"]
                    if "country" in component["types"]:
                        country = component["long_name"]
                
                # Get timezone
                location = result["geometry"]["location"]
                timezone = self._get_timezone(location["lat"], location["lng"])
                
                logger.info(f"📍 Resolved: '{destination}' → {city}, {country} ({location['lat']}, {location['lng']})")
                
                return {
                    "success": True,
                    "name": city,
                    "description": f"A vibrant destination in {country}",
                    "country": country,
                    "timezone": timezone,
                    "coordinates": {
                        "lat": location["lat"],
                        "lng": location["lng"]
                    },
                    "original_input": destination
                }
            else:
                logger.warning(f"Geocoding failed for {destination}: {data.get('status')}")
                return self._get_fallback_destination_info(destination)
                
        except Exception as e:
            logger.error(f"Error fetching destination info: {e}")
            return self._get_fallback_destination_info(destination)

    def fetch_location_based_data(
        self, 
        destination: str, 
        user_location: Optional[str] = None,
        include_flights: bool = True
    ) -> Dict[str, Any]:
        """Fetch location-based data with TOP 10-15 PHOTOS and hotel/restaurant data for budgeting"""
        logger.info("=" * 80)
        logger.info(f"🌍 FETCHING DATA FOR: {destination}")
        logger.info("=" * 80)
        
        dest_info = self.get_destination_info(destination)
        coordinates = dest_info.get("coordinates", {})
        
        if not coordinates:
            logger.warning(f"⚠️ No coordinates found for {destination}, using fallback data")
            return self._get_fallback_location_data(destination, user_location, include_flights)
        
        lat, lng = coordinates["lat"], coordinates["lng"]
        logger.info(f"📍 Coordinates: {lat}, {lng}")
        
        # Fetch ONLY TOP-RATED attractions and activities with photos (10-15 total)
        logger.info("\n📦 Starting data collection (TOP 10-15 PHOTOS + HOTELS/RESTAURANTS)...")
        
        # Fetch top attractions (aim for 8-10)
        attractions_data = self.fetch_top_attractions(destination, lat, lng, max_results=10)
        logger.info(f"✅ Top Attractions: {len(attractions_data)} items with photos")
        
        # Fetch top activities (aim for 5-7)
        activities_data = self.fetch_top_activities(destination, lat, lng, max_results=7)
        logger.info(f"✅ Top Activities: {len(activities_data)} items with photos")
        
        # Fetch hotels for budget calculation
        hotels_data = self.fetch_hotels(destination, lat, lng)
        logger.info(f"✅ Hotels: {len(hotels_data)} options found")
        
        # Fetch restaurants for budget calculation
        restaurants_data = self.fetch_restaurants(destination, lat, lng)
        logger.info(f"✅ Restaurants: {len(restaurants_data)} options found")
        
        # Count total photos - STRICT LIMIT TO 15
        total_photos = len([a for a in attractions_data if a.get("photo_url")]) + \
                      len([a for a in activities_data if a.get("photo_url")])
        
        if total_photos > 15:
            logger.info(f"📸 Limiting to top 15 photos (had {total_photos})")
            # Keep only top-rated items with photos, limit to 15 total
            all_items = []
            for item in attractions_data + activities_data:
                if item.get("photo_url"):
                    all_items.append(item)
            
            # Sort by rating * review count for best quality
            all_items.sort(key=lambda x: x.get("rating", 0) * min(x.get("user_ratings_total", 0)/100, 10), reverse=True)
            top_items = all_items[:15]
            
            # Split back into attractions and activities
            attractions_data = [item for item in top_items if any(item.get("name") == a.get("name") for a in attractions_data)]
            activities_data = [item for item in top_items if any(item.get("name") == a.get("name") for a in activities_data)]
            
            total_photos = len(top_items)
        
        logger.info(f"📸 Final photo count: {total_photos} (TOP-RATED ONLY)")
        
        # Flight data - ALWAYS generate if include_flights is True
        flight_data = None
        if include_flights:
            if user_location:
                flight_data = self.fetch_flight_info(user_location, destination)
                logger.info(f"✅ Flights: {len(flight_data)} options (from {user_location})")
            else:
                flight_data = self._generate_default_flights(destination)
                logger.info(f"✅ Flights: {len(flight_data)} options (default)")
        else:
            logger.info("⏭️  Flights: Skipped (not requested)")
        
        transport_data = self.fetch_local_transport_info(destination)
        logger.info(f"✅ Transport: {len(transport_data)} options")
        
        logger.info("\n✅ DATA COLLECTION COMPLETE")
        logger.info("=" * 80)
        
        return {
            "destination_info": dest_info,
            "attractions": attractions_data,
            "activities": activities_data,
            "hotels": hotels_data,  # For budget calculation
            "restaurants": restaurants_data,  # For budget calculation
            "flights": flight_data,
            "local_transport": transport_data,
        }
    
    def fetch_top_attractions(
        self,
        destination: str,
        lat: float,
        lng: float,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Fetch TOP attractions with photos based on ratings and reviews"""
        if not self.google_api_key:
            return self._get_fallback_data(destination, "attractions")[:max_results]
        
        try:
            api_logger.info(f"🔍 Fetching TOP {max_results} attractions for {destination}")
            
            attraction_types = [
                "tourist_attraction",
                "museum",
                "park",
                "landmark",
                "point_of_interest"
            ]
            
            all_attractions = []
            url = f"{self.places_base_url}/nearbysearch/json"
            
            for attraction_type in attraction_types[:3]:  # Limit API calls
                params = {
                    "location": f"{lat},{lng}",
                    "radius": 10000,  # 10km for better coverage
                    "type": attraction_type,
                    "key": self.google_api_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "OK":
                    for result in data.get("results", []):
                        # STRICT: Only include if has photo AND good rating
                        if result.get("photos") and result.get("rating", 0) >= 4.0:
                            photo_reference = result["photos"][0].get("photo_reference")
                            
                            attraction_data = {
                                "name": result.get("name"),
                                "type": attraction_type.replace("_", " ").title(),
                                "rating": result.get("rating", 4.0),
                                "user_ratings_total": result.get("user_ratings_total", 0),
                                "location": result.get("geometry", {}).get("location", {}),
                                "photo_url": f"{self.places_base_url}/photo?maxwidth=800&photo_reference={photo_reference}&key={self.google_api_key}" if photo_reference else None
                            }
                            
                            if attraction_data["photo_url"]:
                                all_attractions.append(attraction_data)
            
            # Remove duplicates
            seen = set()
            unique_attractions = []
            for attr in all_attractions:
                if attr["name"] not in seen:
                    seen.add(attr["name"])
                    unique_attractions.append(attr)
            
            # Sort by QUALITY SCORE: rating * (review_count/100)
            unique_attractions.sort(
                key=lambda x: x.get("rating", 0) * min(x.get("user_ratings_total", 0)/100, 10),
                reverse=True
            )
            
            # Keep only top N
            top_attractions = unique_attractions[:max_results]
            
            api_logger.info(f"✅ Found {len(top_attractions)} TOP-RATED attractions with photos")
            return top_attractions
            
        except Exception as e:
            logger.error(f"❌ Error fetching top attractions: {e}")
            return self._get_fallback_data(destination, "attractions")[:max_results]
    
    def fetch_top_activities(
        self,
        destination: str,
        lat: float,
        lng: float,
        max_results: int = 7
    ) -> List[Dict[str, Any]]:
        """Fetch TOP activities with photos based on ratings and reviews"""
        if not self.google_api_key:
            return self._get_fallback_data(destination, "activities")[:max_results]
        
        try:
            api_logger.info(f"🔍 Fetching TOP {max_results} activities for {destination}")
            
            all_activities = []
            url = f"{self.places_base_url}/nearbysearch/json"
            
            activity_keywords = [
                "activities tours experiences",
                "things to do entertainment"
            ]
            
            for keyword in activity_keywords:
                params = {
                    "location": f"{lat},{lng}",
                    "radius": 10000,
                    "keyword": keyword,
                    "key": self.google_api_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "OK":
                    for result in data.get("results", []):
                        # STRICT: Only include if has photo AND good rating
                        if result.get("photos") and result.get("rating", 0) >= 4.0:
                            photo_reference = result["photos"][0].get("photo_reference")
                            
                            activity_data = {
                                "name": result.get("name"),
                                "type": self._categorize_activity(result.get("types", [])),
                                "rating": result.get("rating", 4.0),
                                "user_ratings_total": result.get("user_ratings_total", 0),
                                "price": self._estimate_activity_price(result.get("price_level", 2)),
                                "duration": "2-3 hours",
                                "location": result.get("geometry", {}).get("location", {}),
                                "photo_url": f"{self.places_base_url}/photo?maxwidth=800&photo_reference={photo_reference}&key={self.google_api_key}" if photo_reference else None
                            }
                            
                            if activity_data["photo_url"]:
                                all_activities.append(activity_data)
            
            # Remove duplicates
            seen = set()
            unique_activities = []
            for activity in all_activities:
                if activity["name"] not in seen:
                    seen.add(activity["name"])
                    unique_activities.append(activity)
            
            # Sort by QUALITY SCORE
            unique_activities.sort(
                key=lambda x: x.get("rating", 0) * min(x.get("user_ratings_total", 0)/100, 10),
                reverse=True
            )
            
            # Keep only top N
            top_activities = unique_activities[:max_results]
            
            api_logger.info(f"✅ Found {len(top_activities)} TOP-RATED activities with photos")
            return top_activities
            
        except Exception as e:
            logger.error(f"❌ Error fetching top activities: {e}")
            return self._get_fallback_data(destination, "activities")[:max_results]

    def _generate_default_flights(self, destination: str) -> List[Dict[str, Any]]:
        """Generate realistic default flight data"""
        # More realistic flight prices based on destination
        flight_prices = {
            "bali": 850, "paris": 650, "tokyo": 950,
            "new york": 500, "london": 700, "rome": 600,
            "barcelona": 550, "dubai": 800, "bangkok": 900,
            "singapore": 920, "sydney": 1200, "amsterdam": 680
        }
        
        destination_key = destination.lower()
        base_price = flight_prices.get(destination_key, 600)
        
        return [
            {
                "flight_number": "AA123",
                "airline": "American Airlines",
                "departure": (datetime.now() + timedelta(days=7)).isoformat(),
                "arrival": (datetime.now() + timedelta(days=7, hours=12)).isoformat(),
                "price": base_price,
                "class": "economy"
            },
            {
                "flight_number": "DL456",
                "airline": "Delta Airlines",
                "departure": (datetime.now() + timedelta(days=7, hours=3)).isoformat(),
                "arrival": (datetime.now() + timedelta(days=7, hours=15)).isoformat(),
                "price": base_price - 100,
                "class": "economy"
            },
            {
                "flight_number": "UA789",
                "airline": "United Airlines",
                "departure": (datetime.now() + timedelta(days=7, hours=6)).isoformat(),
                "arrival": (datetime.now() + timedelta(days=7, hours=18)).isoformat(),
                "price": base_price + 200,
                "class": "business"
            }
        ]

    def fetch_flight_info(self, from_location: str, to_location: str) -> List[Dict[str, Any]]:
        """Generate flight data between locations"""
        return self._generate_default_flights(to_location)

    def fetch_local_transport_info(self, destination: str) -> List[Dict[str, Any]]:
        """Fetch local transport information"""
        return [
            {"mode": "Public Transit", "price": 3, "route": "City Center - Tourist Areas"},
            {"mode": "Taxi/Rideshare", "price": 25, "route": "Average city ride"},
            {"mode": "Airport Transfer", "price": 40, "route": "Airport to City Center"}
        ]

    # Helper methods
    
    def _get_timezone(self, lat: float, lng: float) -> str:
        """Get timezone using Google Time Zone API"""
        try:
            url = "https://maps.googleapis.com/maps/api/timezone/json"
            timestamp = int(datetime.now().timestamp())
            params = {
                "location": f"{lat},{lng}",
                "timestamp": timestamp,
                "key": self.google_maps_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK":
                return data.get("timeZoneId", "UTC")
            else:
                return "UTC"
        except Exception as e:
            logger.error(f"Error fetching timezone: {e}")
            return "UTC"

    def fetch_hotels(self, destination: str, lat: float, lng: float) -> List[Dict[str, Any]]:
        """Fetch hotel data using Google Places API for budget calculations"""
        if not self.google_api_key:
            logger.info(f"🏨 Using fallback hotel data for {destination}")
            return self._get_fallback_data(destination, "hotels")
        
        try:
            api_logger.info(f"🔍 Fetching hotels for {destination}")
            url = f"{self.places_base_url}/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "radius": 5000,
                "type": "lodging",
                "key": self.google_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK":
                api_logger.info(f"✅ Successfully fetched {len(data.get('results', []))} hotels")
                hotels = []
                for result in data.get("results", [])[:12]:
                    price_level = result.get("price_level", 2)
                    category = self._categorize_hotel(price_level)
                    price_per_night = self._estimate_hotel_price(price_level)
                    
                    hotel_data = {
                        "name": result.get("name"),
                        "category": category,
                        "rating": result.get("rating", 4.0),
                        "price_per_night": price_per_night,
                        "location": result.get("geometry", {}).get("location", {}),
                        "address": result.get("vicinity", "")
                    }
                    hotels.append(hotel_data)
                
                return hotels
            else:
                logger.warning(f"⚠️ Hotels API returned status: {data.get('status')}")
                return self._get_fallback_data(destination, "hotels")
                
        except Exception as e:
            logger.error(f"❌ Error fetching hotels: {e}")
            return self._get_fallback_data(destination, "hotels")

    def fetch_restaurants(self, destination: str, lat: float, lng: float) -> List[Dict[str, Any]]:
        """Fetch restaurant data using Google Places API for budget calculations"""
        if not self.google_api_key:
            logger.info(f"🍽️ Using fallback restaurant data for {destination}")
            return self._get_fallback_data(destination, "restaurants")
        
        try:
            api_logger.info(f"🔍 Fetching restaurants for {destination}")
            url = f"{self.places_base_url}/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "radius": 3000,
                "type": "restaurant",
                "key": self.google_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK":
                api_logger.info(f"✅ Successfully fetched {len(data.get('results', []))} restaurants")
                restaurants = []
                for result in data.get("results", [])[:15]:
                    # Estimate price level and average price
                    price_level = result.get("price_level", 2)
                    avg_price = self._estimate_meal_price(price_level)
                    
                    restaurant_data = {
                        "name": result.get("name"),
                        "cuisine": ", ".join(result.get("types", [])[:2]),
                        "price_level": price_level,
                        "rating": result.get("rating", 4.0),
                        "avg_price": avg_price,
                        "location": result.get("geometry", {}).get("location", {}),
                        "address": result.get("vicinity", "")
                    }
                    restaurants.append(restaurant_data)
                
                return restaurants
            else:
                logger.warning(f"⚠️ Restaurants API returned status: {data.get('status')}")
                return self._get_fallback_data(destination, "restaurants")
                
        except Exception as e:
            logger.error(f"❌ Error fetching restaurants: {e}")
            return self._get_fallback_data(destination, "restaurants")

    def _categorize_hotel(self, price_level: int) -> str:
        """Categorize hotel based on price level"""
        if price_level <= 1:
            return "budget"
        elif price_level == 2:
            return "mid_range"
        else:
            return "luxury"

    def _estimate_hotel_price(self, price_level: int) -> float:
        """Estimate hotel price per night based on price level"""
        price_map = {0: 30, 1: 60, 2: 120, 3: 250, 4: 400}
        return price_map.get(price_level, 120)

    def _estimate_meal_price(self, price_level: int) -> float:
        """Estimate meal price based on Google price level (0-4)"""
        price_map = {0: 5, 1: 10, 2: 25, 3: 50, 4: 100}
        return price_map.get(price_level, 25)

    def _estimate_activity_price(self, price_level: int) -> float:
        """Estimate activity price based on price level"""
        price_map = {0: 0, 1: 15, 2: 35, 3: 75, 4: 150}
        return price_map.get(price_level, 35)

    def _categorize_activity(self, types: List[str]) -> str:
        """Categorize activity based on types"""
        if "spa" in types:
            return "Wellness"
        elif any(x in types for x in ["amusement_park", "aquarium", "zoo"]):
            return "Entertainment"
        elif "art_gallery" in types or "museum" in types:
            return "Cultural"
        else:
            return "Sightseeing"

    # Fallback data methods
    
    def _get_fallback_destination_info(self, destination: str) -> Dict[str, Any]:
        """Return fallback destination info when API is unavailable"""
        destination_info = {
            "bali": {"name": "Bali", "description": "A tropical paradise in Indonesia", "country": "Indonesia", "timezone": "Asia/Makassar"},
            "paris": {"name": "Paris", "description": "The capital of France, city of lights", "country": "France", "timezone": "Europe/Paris"},
            "tokyo": {"name": "Tokyo", "description": "Japan's bustling capital city", "country": "Japan", "timezone": "Asia/Tokyo"},
            "new york": {"name": "New York", "description": "The city that never sleeps", "country": "USA", "timezone": "America/New_York"},
            "london": {"name": "London", "description": "Historic capital of the United Kingdom", "country": "United Kingdom", "timezone": "Europe/London"}
        }
        
        return destination_info.get(destination.lower(), {
            "name": destination.title(),
            "description": f"Beautiful destination",
            "country": "Unknown",
            "timezone": "UTC"
        })

    def _get_fallback_location_data(self, destination: str, user_location: Optional[str], include_flights: bool) -> Dict[str, Any]:
        """Return complete fallback data set"""
        dest_info = self._get_fallback_destination_info(destination)
        
        return {
            "destination_info": dest_info,
            "attractions": self._get_fallback_data(destination, "attractions"),
            "activities": self._get_fallback_data(destination, "activities"),
            "flights": self._generate_default_flights(destination) if include_flights else None,
            "local_transport": self.fetch_local_transport_info(destination)
        }

    def _get_fallback_data(self, destination: str, data_type: str) -> List[Dict[str, Any]]:
        """Get fallback data for specific type"""
        return self.fallback_destinations.get(destination.lower(), {}).get(data_type, 
            self.fallback_destinations.get("bali", {}).get(data_type, []))

    def _initialize_fallback_data(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Initialize comprehensive fallback data for all destinations"""
        return {
            "bali": {
                "attractions": [
                    {"name": "Ubud Rice Terraces", "type": "Natural Wonder", "rating": 4.7, "user_ratings_total": 5000, "photo_url": None},
                    {"name": "Tanah Lot Temple", "type": "Historical", "rating": 4.6, "user_ratings_total": 4500, "photo_url": None},
                ],
                "activities": [
                    {"name": "Balinese Cooking Class", "type": "Cultural", "price": 35, "duration": "4 hours", "rating": 4.8, "user_ratings_total": 2000, "photo_url": None},
                    {"name": "Yoga Retreat", "type": "Wellness", "price": 25, "duration": "2 hours", "rating": 4.7, "user_ratings_total": 1500, "photo_url": None},
                ],
                "hotels": [
                    {"name": "Bali Budget Inn", "category": "budget", "rating": 4.2, "price_per_night": 35},
                    {"name": "Komaneka Resort", "category": "mid_range", "rating": 4.6, "price_per_night": 80},
                    {"name": "Four Seasons Bali", "category": "luxury", "rating": 4.9, "price_per_night": 250}
                ],
                "restaurants": [
                    {"name": "Warung Biah Biah", "cuisine": "Balinese", "price_level": 1, "rating": 4.5, "avg_price": 8},
                    {"name": "Locavore", "cuisine": "Modern Indonesian", "price_level": 3, "rating": 4.8, "avg_price": 45}
                ]
            }
        }