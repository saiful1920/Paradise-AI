"""
Enhanced Demo Data Manager for Travel Itinerary System

Features:
- DYNAMIC worldwide pricing using LLM (no hardcoded lists)
- Multi-city support with intelligent data fetching
- Always fetches: 10 experiences, 5 hotels, 5 restaurants
- Attractions scale based on days per city
- Real pricing from Google Places API with regional adjustments
"""

from typing import Dict, List, Any, Optional
import os
import traceback
import requests
from datetime import datetime, timedelta
import logging
from openai import OpenAI

# Import components
try:
    from destination_parser import SmartDestinationManager
    SMART_PARSER_AVAILABLE = True
except ImportError:
    SMART_PARSER_AVAILABLE = False

try:
    from flight_data import AviasalesFlightFormatter
    FLIGHT_SERVICE_AVAILABLE = True
except ImportError:
    FLIGHT_SERVICE_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DemoDataManager:
    """
    Manages all data for WORLDWIDE travel itinerary with DYNAMIC pricing
    """
    
    # Base price conversion from Google price_level (0-4) to USD
    BASE_PRICE_CONVERSION = {
        "hotel": {0: 25, 1: 50, 2: 100, 3: 200, 4: 350},
        "meal": {0: 5, 1: 12, 2: 25, 3: 50, 4: 100},
        "activity": {0: 0, 1: 15, 2: 35, 3: 75, 4: 150},
        "tour": {0: 20, 1: 40, 2: 80, 3: 150, 4: 300},
        "experience": {0: 25, 1: 50, 2: 100, 3: 180, 4: 350}
    }
    
    def __init__(self, google_api_key: str, google_maps_key: str, openai_api_key: str):
        self.google_api_key = google_api_key
        self.google_maps_key = google_maps_key
        self.openai_api_key = openai_api_key
        
        # Initialize OpenAI client for dynamic pricing
        self.openai_client = OpenAI(api_key=self.openai_api_key) if openai_api_key else None
        
        # Cache for region multipliers (to avoid repeated LLM calls)
        self.region_multiplier_cache = {}
        
        if SMART_PARSER_AVAILABLE and self.openai_api_key:
            self.smart_parser = SmartDestinationManager(
                openai_api_key=self.openai_api_key,
                google_api_key=self.google_api_key
            )
            logger.info("✅ Smart destination parser initialized")
        else:
            self.smart_parser = None
        
        if FLIGHT_SERVICE_AVAILABLE:
            self.flight_service = AviasalesFlightFormatter()
            logger.info("✅ Flight service initialized")
        else:
            self.flight_service = None
        
        self.places_base_url = "https://maps.googleapis.com/maps/api/place"
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
        
        if not self.google_api_key:
            logger.warning("⚠️ GOOGLE_PLACES_API_KEY not found - using fallback data")
    
    def _get_region_multipliers(self, city: str, country: str, timezone: str) -> Dict[str, float]:
        """
        DYNAMIC: Get price multipliers for ANY location worldwide using LLM
        Uses cost of living data to determine accurate pricing
        """
        # Check cache first
        cache_key = f"{city}_{country}".lower().replace(" ", "_")
        if cache_key in self.region_multiplier_cache:
            return self.region_multiplier_cache[cache_key]
        
        if not self.openai_client:
            logger.warning("⚠️ OpenAI not available, using default multipliers")
            return {"hotel": 1.0, "meal": 1.0, "activity": 1.0, "tour": 1.0}
        
        try:
            logger.info(f"💰 Calculating price multipliers for {city}, {country}")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a travel pricing expert with knowledge of cost of living worldwide.

                        Calculate price multipliers for different travel expense categories based on the destination's cost of living.

                        Base reference: USA average city = 1.0 multiplier

                        GUIDELINES:
                        - Very expensive (Zurich, Singapore, Tokyo, NYC, London, Dubai): 1.4-1.8
                        - Expensive (Paris, Sydney, Oslo, Copenhagen, Toronto): 1.2-1.4
                        - Above average (Rome, Madrid, Barcelona, Seoul): 0.9-1.2
                        - Average (Prague, Budapest, Lisbon, Athens): 0.7-0.9
                        - Budget-friendly (Bangkok, Mexico City, Cairo, Istanbul): 0.4-0.7
                        - Very budget-friendly (Vietnam, India, Egypt, Cambodia, Nepal): 0.3-0.5

                        Consider:
                        - Local economy and GDP per capita
                        - Tourist infrastructure costs
                        - Currency strength and exchange rates
                        - Regional economic development

                        Return ONLY valid JSON (no markdown):
                        {
                            "hotel": 1.0,
                            "meal": 1.0,
                            "activity": 1.0,
                            "tour": 1.0,
                            "confidence": "high"
                        }"""
                    },
                    {
                        "role": "user",
                        "content": f"Calculate price multipliers for: {city}, {country}"
                    }
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            import json
            result = json.loads(result_text)
            
            multipliers = {
                "hotel": float(result.get("hotel", 1.0)),
                "meal": float(result.get("meal", 1.0)),
                "activity": float(result.get("activity", 1.0)),
                "tour": float(result.get("tour", 1.0))
            }
            
            # Cache the result
            self.region_multiplier_cache[cache_key] = multipliers
            
            logger.info(f"✅ Multipliers for {city}: hotel={multipliers['hotel']}, meal={multipliers['meal']}, activity={multipliers['activity']}, tour={multipliers['tour']}")
            
            return multipliers
            
        except Exception as e:
            logger.error(f"❌ Error calculating multipliers: {e}")
            # Fallback to default
            default = {"hotel": 1.0, "meal": 1.0, "activity": 1.0, "tour": 1.0}
            self.region_multiplier_cache[cache_key] = default
            return default
    
    def _convert_price_level_to_usd(
        self,
        price_level: int,
        category: str,
        city: str,
        country: str,
        timezone: str
    ) -> float:
        """
        Convert Google Places price_level to actual USD using DYNAMIC regional pricing
        """
        base_price = self.BASE_PRICE_CONVERSION.get(category, {}).get(price_level, 50)
        
        # Get dynamic multipliers
        multipliers = self._get_region_multipliers(city, country, timezone)
        multiplier = multipliers.get(category, 1.0)
        
        return round(base_price * multiplier, 2)
    
    def _calculate_data_limits(self, duration: int, num_cities: int) -> Dict[str, int]:
        """
        Calculate optimal data limits to ensure NO REPETITION
        
        Rules:
        - Need 3 activities per day (morning, afternoon, evening)
        - Total slots = duration × 3
        - Fetch MORE than needed to have variety
        """
        total_slots_needed = duration * 3
        
        # Add 50% buffer for variety and categorization
        buffer_multiplier = 1.5
        
        days_per_city = max(1, duration / num_cities)
        
        # Attractions: More based on duration
        if days_per_city <= 2:
            attractions_per_city = max(10, int(total_slots_needed * 0.4))
        elif days_per_city <= 4:
            attractions_per_city = max(15, int(total_slots_needed * 0.5))
        else:
            attractions_per_city = max(20, int(total_slots_needed * 0.6))
        
        return {
            "attractions": attractions_per_city,
            "experiences": max(15, int(total_slots_needed * 0.4 * buffer_multiplier)), 
            "hotels": 5,
            "restaurants": 5
        }
    
    def get_destination_info(
        self,
        destination: str,
        duration: int = 3,
        current_location: Optional[str] = None  
    ) -> Dict[str, Any]:
        """Get destination information with multi-city support"""
        if not self.google_api_key:
            return self._get_fallback_destination_info(destination)
        
        if self.smart_parser:
            logger.info(f"🤖 Using smart parser for: '{destination}' ({duration} days)")
            if current_location:  # ← ADDED THIS LOG
                logger.info(f"👤 User location: {current_location}")
            
            # ← CHANGED THIS LINE - added current_location parameter
            result = self.smart_parser.process_destination(
                destination, 
                duration,
                current_location=current_location
            )
            
            if result.get("success"):
                return result
        
        return self._basic_geocoding(destination)
    
    def _basic_geocoding(self, destination: str) -> Dict[str, Any]:
        """Basic geocoding fallback"""
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
                location = result["geometry"]["location"]
                
                city = destination
                country = "Unknown"
                for component in result.get("address_components", []):
                    if "locality" in component["types"]:
                        city = component["long_name"]
                    if "country" in component["types"]:
                        country = component["long_name"]
                
                timezone = self._get_timezone(location["lat"], location["lng"])
                
                return {
                    "success": True,
                    "cities": [city],
                    "country": country,
                    "is_multi_city": False,
                    "city_details": [{
                        "name": city,
                        "country": country,
                        "coordinates": {"lat": location["lat"], "lng": location["lng"]},
                        "timezone": timezone,
                        "days_allocated": 3
                    }],
                    "primary_city": {
                        "name": city,
                        "country": country,
                        "coordinates": {"lat": location["lat"], "lng": location["lng"]},
                        "timezone": timezone
                    }
                }
            
            return self._get_fallback_destination_info(destination)
            
        except Exception as e:
            logger.error(f"❌ Geocoding error: {e}")
            return self._get_fallback_destination_info(destination)
    
    def _get_timezone(self, lat: float, lng: float) -> str:
        """Get timezone for coordinates"""
        try:
            import time
            url = "https://maps.googleapis.com/maps/api/timezone/json"
            params = {
                "location": f"{lat},{lng}",
                "timestamp": str(int(time.time())),
                "key": self.google_maps_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") == "OK":
                return data.get("timeZoneId", "UTC")
            return "UTC"
        except Exception:
            return "UTC"
    
    def fetch_location_based_data(
        self,
        destination: str,
        current_location: Optional[str] = None,
        include_flights: bool = True,
        duration: int = 3
    ) -> Dict[str, Any]:
        logger.info("=" * 80)
        logger.info(f"🌍 FETCHING DATA FOR: {destination} ({duration} days)")
        if current_location:  
            logger.info(f"📍 User Location: {current_location}")
        logger.info("=" * 80)
        
        dest_info = self.get_destination_info(destination, duration, current_location)
        
        if not dest_info.get("success"):
            logger.warning("⚠️ Destination parsing failed, using fallback")
            return self._get_fallback_location_data(destination, current_location, include_flights)
        
        num_cities = len(dest_info.get("cities", [1]))
        data_limits = self._calculate_data_limits(duration, num_cities)
        
        logger.info(f"📊 Data limits: {data_limits}")
        logger.info(f"🏙️ Cities: {dest_info.get('cities', [])}")
        
        # Collect data for multi-city
        all_attractions = []
        all_experiences = []
        all_hotels = []
        all_restaurants = []
        
        # Calculate per-city limits for attractions only
        attractions_per_city = max(3, data_limits["attractions"] // num_cities)
        
        for city_detail in dest_info.get("city_details", []):
            city_name = city_detail.get("name", destination)
            country = city_detail.get("country", "Unknown")
            coordinates = city_detail.get("coordinates", {})
            timezone = city_detail.get("timezone", "UTC")
            days_for_city = city_detail.get("days_allocated", duration)
            
            if not coordinates:
                continue
            
            lat, lng = coordinates["lat"], coordinates["lng"]
            logger.info(f"\n📍 Fetching data for {city_name}, {country} ({days_for_city} days)")
            
            # Fetch attractions (scaled by city) with DYNAMIC pricing
            city_attractions = self._fetch_attractions(
                city_name, country, lat, lng, timezone, attractions_per_city
            )
            
            # Tag with city name
            for item in city_attractions:
                item["city"] = city_name
                item["days_in_city"] = days_for_city
            
            all_attractions.extend(city_attractions)
        
        # Fetch experiences, hotels, restaurants ONCE for primary city
        primary_city = dest_info.get("primary_city", {})
        if primary_city.get("coordinates"):
            lat = primary_city["coordinates"]["lat"]
            lng = primary_city["coordinates"]["lng"]
            timezone = primary_city.get("timezone", "UTC")
            city_name = primary_city.get("name", destination)
            country = primary_city.get("country", "Unknown")
            
            logger.info(f"\n🎭 Fetching experiences, hotels, restaurants for {city_name}, {country}")
            
            all_experiences = self._fetch_experiences_and_tours(
                city_name, country, lat, lng, timezone, 10
            )
            
            all_hotels = self._fetch_hotels(
                city_name, country, lat, lng, timezone, 5
            )
            
            all_restaurants = self._fetch_restaurants(
                city_name, country, lat, lng, timezone, 5
            )
        
        # Log results
        logger.info(f"\n✅ Total Attractions: {len(all_attractions)}")
        logger.info(f"✅ Total Experiences: {len(all_experiences)}")
        logger.info(f"✅ Total Hotels: {len(all_hotels)}")
        logger.info(f"✅ Total Restaurants: {len(all_restaurants)}")
        
        # Fetch flights
        flights_data = None
        if include_flights:
            flights_data = self._fetch_flights(dest_info, current_location, duration)
            logger.info(f"✅ Flights: {len(flights_data) if flights_data else 0} options")
        
        # Get transport info with DYNAMIC pricing
        transport_data = self._fetch_local_transport(
            primary_city.get("name", destination),
            primary_city.get("country", "Unknown"),
            primary_city.get("timezone", "UTC")
        )
        
        logger.info("=" * 80)
        
        return {
            "destination_info": dest_info,
            "attractions": all_attractions,
            "activities": all_attractions,
            "experiences": all_experiences,
            "hotels": all_hotels,
            "restaurants": all_restaurants,
            "flights": flights_data,
            "local_transport": transport_data
        }
    
    def _fetch_attractions(
        self,
        city: str,
        country: str,
        lat: float,
        lng: float,
        timezone: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch attractions with photos and DYNAMIC pricing"""
        if not self.google_api_key:
            return []
        
        try:
            attractions = []
            url = f"{self.places_base_url}/nearbysearch/json"
            
            search_queries = [
                {"type": "tourist_attraction"},
                {"type": "museum"},
                {"keyword": "landmark"}
            ]
            
            for query in search_queries[:2]:
                params = {
                    "location": f"{lat},{lng}",
                    "radius": 15000,
                    "key": self.google_api_key,
                    **query
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code != 200:
                    continue
                
                data = response.json()
                if data.get("status") != "OK":
                    continue
                
                for result in data.get("results", []):
                    # Quality filter: Minimum rating and reviews
                    if result.get("rating", 0) < 4.0:
                        continue
                    if result.get("user_ratings_total", 0) < 100:  
                        continue
                    if not result.get("photos"):
                        continue
                    
                    photo_ref = result["photos"][0].get("photo_reference")
                    price_level = result.get("price_level", 1)
                    
                    # DYNAMIC pricing
                    estimated_cost = self._convert_price_level_to_usd(
                        price_level, "activity", city, country, timezone
                    )
                    
                    attractions.append({
                        "name": result.get("name"),
                        "type": self._categorize_place(result.get("types", [])),
                        "rating": result.get("rating", 4.0),
                        "user_ratings_total": result.get("user_ratings_total", 0),
                        "location": result.get("geometry", {}).get("location", {}),
                        "address": result.get("vicinity", ""),
                        "photo_url": f"{self.places_base_url}/photo?maxwidth=800&photo_reference={photo_ref}&key={self.google_api_key}" if photo_ref else None,
                        "price_level": price_level,
                        "estimated_cost": estimated_cost,
                        "cost_breakdown": {
                            "base_price": self.BASE_PRICE_CONVERSION["activity"].get(price_level, 35),
                            "region_multiplier": self._get_region_multipliers(city, country, timezone).get("activity", 1.0),
                            "price_level": price_level,
                            "city": city,
                            "country": country
                        }
                    })
            
            # Deduplicate and sort
            seen = set()
            unique = []
            for a in attractions:
                if a["name"] not in seen:
                    seen.add(a["name"])
                    unique.append(a)
            
            unique.sort(
                key=lambda x: x["rating"] * x["user_ratings_total"],
                reverse=True
            )
            
            return unique[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error fetching attractions: {e}")
            return []
    
    def _fetch_experiences_and_tours(
        self,
        city: str,
        country: str,
        lat: float,
        lng: float,
        timezone: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        FIXED: Fetch diverse experiences and tours
        
        Target: 15 total experiences
        - 5 tours (walking, guided, food, etc.)
        - 5 excursions (day trips, adventures)
        - 5 classes/workshops
        """
        if not self.google_api_key:
            return []
        
        try:
            experiences = []
            url = f"{self.places_base_url}/textsearch/json"
            
            # FIXED: More diverse search queries to get different types
            search_queries = [
                # Tours (5)
                f"guided tours in {city}",
                f"walking tours {city}",
                f"food tours {city}",
                
                # Excursions (5)
                f"day trips from {city}",
                f"excursions {city}",
                f"adventure activities {city}",
                
                # Classes/Workshops (5)
                f"cooking class {city}",
                f"workshop {city}",
                f"cultural experiences {city}"
            ]
            
            for query in search_queries[:6]:  # Use 6 queries to get variety
                params = {
                    "query": query,
                    "location": f"{lat},{lng}",
                    "radius": 25000,  # Increased radius
                    "key": self.google_api_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code != 200:
                    continue
                
                data = response.json()
                if data.get("status") != "OK":
                    continue
                
                for result in data.get("results", [])[:3]:
                    # Quality filter
                    if result.get("rating", 0) < 4.0:
                        continue
                    
                    photo_ref = result.get("photos", [{}])[0].get("photo_reference") if result.get("photos") else None
                    price_level = result.get("price_level", 2)
                    
                    exp_type = self._determine_experience_type(result.get("name", ""), result.get("types", []))
                    duration = self._estimate_experience_duration(exp_type)
                    
                    # DYNAMIC pricing
                    base_cost = self._convert_price_level_to_usd(
                        price_level, "tour", city, country, timezone
                    )
                    
                    experiences.append({
                        "name": result.get("name"),
                        "type": exp_type,
                        "category": self._categorize_experience(exp_type),  
                        "rating": result.get("rating", 4.0),
                        "user_ratings_total": result.get("user_ratings_total", 0),
                        "location": result.get("geometry", {}).get("location", {}),
                        "address": result.get("formatted_address", ""),
                        "photo_url": f"{self.places_base_url}/photo?maxwidth=800&photo_reference={photo_ref}&key={self.google_api_key}" if photo_ref else None,
                        "price": base_cost,
                        "price_level": price_level,
                        "duration": duration,
                        "is_experience": True,
                        "cost_breakdown": {
                            "base_price": self.BASE_PRICE_CONVERSION["tour"].get(price_level, 80),
                            "region_multiplier": self._get_region_multipliers(city, country, timezone).get("tour", 1.0),
                            "price_level": price_level,
                            "includes": self._get_tour_inclusions(exp_type)
                        }
                    })
            
            # Deduplicate
            seen = set()
            unique = []
            for e in experiences:
                if e["name"] not in seen:
                    seen.add(e["name"])
                    unique.append(e)
            
            unique.sort(
                key=lambda x: x["rating"] * x["user_ratings_total"],
                reverse=True
            )
            
            # Return up to limit
            return unique[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error fetching experiences: {e}")
            return []

    def _categorize_experience(self, exp_type: str) -> str:
        """
        NEW: Categorize experience into tour/excursion/class
        """
        tours = ["Walking Tour", "Guided Tour", "Food Tour", "Bike Tour", "Boat Tour"]
        excursions = ["Day Excursion", "Adventure Activity", "Safari", "Hiking"]
        classes = ["Cooking Class", "Workshop", "Wellness Experience", "Art Class"]
        
        if exp_type in tours:
            return "tour"
        elif exp_type in excursions:
            return "excursion"
        elif exp_type in classes:
            return "class"
        else:
            return "experience"
    
    def _fetch_hotels(
        self,
        city: str,
        country: str,
        lat: float,
        lng: float,
        timezone: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch hotels with DYNAMIC pricing"""
        if not self.google_api_key:
            return []
        
        try:
            url = f"{self.places_base_url}/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "radius": 8000,
                "type": "lodging",
                "key": self.google_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") != "OK":
                return []
            
            hotels = []
            for result in data.get("results", [])[:limit * 2]:
                # Quality filter
                if result.get("rating", 0) < 4.0:
                    continue
                if result.get("user_ratings_total", 0) < 1000:  
                    continue
                
                price_level = result.get("price_level", 2)
                
                # DYNAMIC pricing
                price_per_night = self._convert_price_level_to_usd(
                    price_level, "hotel", city, country, timezone
                )
                
                photo_ref = result.get("photos", [{}])[0].get("photo_reference") if result.get("photos") else None
                
                hotels.append({
                    "name": result.get("name"),
                    "category": self._categorize_hotel(price_level),
                    "rating": result.get("rating", 4.0),
                    "user_ratings_total": result.get("user_ratings_total", 0),
                    "price_per_night": price_per_night,
                    "price_level": price_level,
                    "location": result.get("geometry", {}).get("location", {}),
                    "address": result.get("vicinity", ""),
                    "photo_url": f"{self.places_base_url}/photo?maxwidth=800&photo_reference={photo_ref}&key={self.google_api_key}" if photo_ref else None,
                    "cost_breakdown": {
                        "base_rate": self.BASE_PRICE_CONVERSION["hotel"].get(price_level, 100),
                        "region_multiplier": self._get_region_multipliers(city, country, timezone).get("hotel", 1.0),
                        "taxes_fees_estimate": round(price_per_night * 0.15, 2),
                        "total_per_night": round(price_per_night * 1.15, 2)
                    }
                })
            
            hotels.sort(key=lambda x: x["rating"], reverse=True)
            return hotels[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error fetching hotels: {e}")
            return []
    
    def _fetch_restaurants(
        self,
        city: str,
        country: str,
        lat: float,
        lng: float,
        timezone: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch restaurants with DYNAMIC pricing"""
        if not self.google_api_key:
            return []
        
        try:
            url = f"{self.places_base_url}/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "radius": 5000,
                "type": "restaurant",
                "key": self.google_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") != "OK":
                return []
            
            restaurants = []
            for result in data.get("results", [])[:limit * 2]:
                # Quality filter
                if result.get("rating", 0) < 4.0:
                    continue
                if result.get("user_ratings_total", 0) < 1000:  
                    continue
                
                price_level = result.get("price_level", 2)
                
                # DYNAMIC pricing
                avg_price = self._convert_price_level_to_usd(
                    price_level, "meal", city, country, timezone
                )
                
                photo_ref = result.get("photos", [{}])[0].get("photo_reference") if result.get("photos") else None
                
                types = result.get("types", [])
                cuisine = self._determine_cuisine(types, result.get("name", ""))
                
                restaurants.append({
                    "name": result.get("name"),
                    "cuisine": cuisine,
                    "rating": result.get("rating", 4.0),
                    "user_ratings_total": result.get("user_ratings_total", 0),
                    "price_level": price_level,
                    "avg_price": avg_price,
                    "location": result.get("geometry", {}).get("location", {}),
                    "address": result.get("vicinity", ""),
                    "photo_url": f"{self.places_base_url}/photo?maxwidth=800&photo_reference={photo_ref}&key={self.google_api_key}" if photo_ref else None,
                    "cost_breakdown": {
                        "avg_meal_price": avg_price,
                        "appetizer_estimate": round(avg_price * 0.4, 2),
                        "main_course_estimate": round(avg_price * 0.7, 2),
                        "drinks_estimate": round(avg_price * 0.3, 2),
                        "tip_suggestion": round(avg_price * 0.18, 2)
                    }
                })
            
            restaurants.sort(key=lambda x: x["rating"], reverse=True)
            return restaurants[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error fetching restaurants: {e}")
            return []
    
    def _fetch_flights(
        self,
        dest_info: Dict[str, Any],
        current_location: str,
        duration: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch flights with proper origin detection and country fallback
        """
        if not self.flight_service:
            logger.warning("⚠️ No flight service available")
            return []
        
        try:
            # STEP 1: Get origin
            origin_city = dest_info.get('origin_city')
            
            if not origin_city and current_location:
                origin_city = current_location
                logger.info(f"📍 Using user location as origin: {current_location}")
            
            if not origin_city:
                logger.warning("⚠️ No flight origin available - cannot fetch flights")
                return []
            
            # STEP 2: Get origin IATA
            if self.smart_parser:
                origin_iata = self.smart_parser.parser.get_iata_code(origin_city, "")
            else:
                origin_iata = self._get_iata_fallback(origin_city)
            
            # STEP 3: Get destination IATA
            city_details = dest_info.get("city_details", [])
            destination_city = dest_info.get('cities', ['Unknown'])[0]
            destination_country = dest_info.get('country', 'Unknown')
            
            if city_details:
                dest_iata = city_details[0].get("iata_code", "")
                if not dest_iata and self.smart_parser:
                    dest_iata = self.smart_parser.parser.get_iata_code(
                        city_details[0].get("name", ""),
                        destination_country
                    )
            else:
                dest_iata = "UNK"
            
            # NEW: Get country airport as fallback
            country_airport = dest_info.get("country_main_airport", "")
            
            # STEP 4: Validate IATA codes
            if origin_iata == "UNK" or not origin_iata:
                logger.warning(f"⚠️ Invalid origin IATA: {origin_city} ({origin_iata})")
                return []
            
            if dest_iata == "UNK" or not dest_iata:
                if country_airport and country_airport != "UNK":
                    logger.info(f"⚠️ Invalid city IATA, will use country airport: {country_airport}")
                    dest_iata = country_airport
                else:
                    logger.warning(f"⚠️ Invalid destination IATA and no country fallback")
                    return []
            
            # STEP 5: Calculate dates
            departure_date = None
            return_date = None
            
            logger.info(f"✈️ Fetching flights: {origin_city} ({origin_iata}) → {destination_city} ({dest_iata})")
            if country_airport and country_airport != dest_iata:
                logger.info(f"🏛️ Country fallback available: {country_airport}")
            
            # STEP 6: Fetch flights with country fallback
            flights = self.flight_service.get_flights(
                origin=origin_iata,
                destination=dest_iata,
                departure_date=departure_date,
                return_date=return_date,
                limit=5,
                destination_country_iata=country_airport  
            )
            
            if not flights:
                logger.info("📭 No flights found")
                return []
            
            # STEP 7: Update with actual city names
            for flight in flights:
                flight['origin'] = origin_iata
                flight['destination'] = flight.get('destination', dest_iata)  
                flight['origin_city'] = origin_city
                flight['destination_city'] = destination_city
                
                # Mark if using country airport
                if flight.get('is_country_level'):
                    flight['destination_note'] = f"Flight to {destination_country} (nearest airport)"
            
            logger.info(f"✅ Returning {len(flights)} flights")
            if flights[0].get('is_country_level'):
                logger.info(f"ℹ️ Using country-level airport: {flights[0].get('destination')}")
            
            return flights
            
        except Exception as e:
            logger.error(f"❌ Error fetching flights: {e}")
            import traceback
            traceback.print_exc()
            return []


    # Also add this helper method to demo_data.py:
    def _get_iata_fallback(self, city: str) -> str:
        """Fallback IATA mapping for common cities"""
        common_cities = {
            # US Cities
            "new york": "JFK",
            "los angeles": "LAX",
            "chicago": "ORD",
            "san francisco": "SFO",
            "boston": "BOS",
            "miami": "MIA",
            "seattle": "SEA",
            "washington": "IAD",
            "atlanta": "ATL",
            
            # European Cities
            "london": "LHR",
            "paris": "CDG",
            "amsterdam": "AMS",
            "frankfurt": "FRA",
            "rome": "FCO",
            "madrid": "MAD",
            "barcelona": "BCN",
            
            # Asian Cities
            "tokyo": "NRT",
            "dubai": "DXB",
            "singapore": "SIN",
            "hong kong": "HKG",
            "bangkok": "BKK",
            "seoul": "ICN",
            "beijing": "PEK",
            "shanghai": "PVG",
            
            # Bangladesh Cities
            "dhaka": "DAC",
            "chittagong": "CGP",
            "sylhet": "ZYL",
            "cox's bazar": "CXB"
        }
        return common_cities.get(city.lower(), "UNK")

    
    def _fetch_local_transport(self, city: str, country: str, timezone: str) -> List[Dict[str, Any]]:
        """Get local transport options with DYNAMIC pricing"""
        multipliers = self._get_region_multipliers(city, country, timezone)
        multiplier = multipliers.get("activity", 1.0)
        
        return [
            {
                "mode": "Public Transit (Metro/Bus)",
                "price": round(3 * multiplier, 2),
                "route": "City-wide coverage",
                "cost_breakdown": {
                    "single_trip": round(3 * multiplier, 2),
                    "day_pass": round(10 * multiplier, 2),
                    "weekly_pass": round(35 * multiplier, 2)
                }
            },
            {
                "mode": "Taxi/Rideshare",
                "price": round(20 * multiplier, 2),
                "route": "Average city ride (5-10km)",
                "cost_breakdown": {
                    "base_fare": round(4 * multiplier, 2),
                    "per_km": round(2 * multiplier, 2),
                    "airport_ride": round(45 * multiplier, 2)
                }
            },
            {
                "mode": "Airport Transfer",
                "price": round(40 * multiplier, 2),
                "route": "Airport ↔ City Center",
                "cost_breakdown": {
                    "shared_shuttle": round(20 * multiplier, 2),
                    "private_transfer": round(50 * multiplier, 2),
                    "public_transport": round(8 * multiplier, 2)
                }
            }
        ]
    
    # Helper methods
    
    def _categorize_place(self, types: List[str]) -> str:
        """Categorize a place based on its types"""
        if "museum" in types:
            return "Museum"
        if "art_gallery" in types:
            return "Art Gallery"
        if "park" in types or "natural_feature" in types:
            return "Nature"
        if "church" in types or "hindu_temple" in types or "mosque" in types:
            return "Religious Site"
        if "amusement_park" in types:
            return "Entertainment"
        return "Landmark"
    
    def _categorize_hotel(self, price_level: int) -> str:
        """Categorize hotel by price level"""
        if price_level <= 1:
            return "budget"
        elif price_level == 2:
            return "mid_range"
        else:
            return "luxury"
    
    def _determine_experience_type(self, name: str, types: List[str]) -> str:
        """Determine the type of experience/tour"""
        name_lower = name.lower()
        
        if "cooking" in name_lower or "culinary" in name_lower:
            return "Cooking Class"
        if "walking" in name_lower:
            return "Walking Tour"
        if "bike" in name_lower or "cycling" in name_lower:
            return "Bike Tour"
        if "food" in name_lower:
            return "Food Tour"
        if "day trip" in name_lower or "excursion" in name_lower:
            return "Day Excursion"
        if "boat" in name_lower or "cruise" in name_lower:
            return "Boat Tour"
        if "workshop" in name_lower:
            return "Workshop"
        if "spa" in name_lower or "wellness" in name_lower:
            return "Wellness Experience"
        
        return "Guided Tour"
    
    def _estimate_experience_duration(self, exp_type: str) -> str:
        """Estimate duration based on experience type"""
        durations = {
            "Cooking Class": "3-4 hours",
            "Walking Tour": "2-3 hours",
            "Bike Tour": "3-4 hours",
            "Food Tour": "3-4 hours",
            "Day Excursion": "8-10 hours",
            "Boat Tour": "2-4 hours",
            "Workshop": "2-3 hours",
            "Wellness Experience": "2-3 hours",
            "Guided Tour": "2-3 hours"
        }
        return durations.get(exp_type, "2-3 hours")
    
    def _get_tour_inclusions(self, exp_type: str) -> List[str]:
        """Get typical inclusions for tour type"""
        inclusions = {
            "Cooking Class": ["Ingredients", "Recipe booklet", "Meal tasting"],
            "Walking Tour": ["Expert guide", "Entry fees", "Small group"],
            "Food Tour": ["Food tastings (6-8 stops)", "Local guide", "Drinks"],
            "Day Excursion": ["Transport", "Lunch", "Entry fees", "Guide"],
            "Boat Tour": ["Boat ride", "Refreshments", "Commentary"],
            "Guided Tour": ["Expert guide", "Entry fees", "Headsets"]
        }
        return inclusions.get(exp_type, ["Guide", "Entry fees"])
    
    def _determine_cuisine(self, types: List[str], name: str) -> str:
        """Determine cuisine type from place data"""
        name_lower = name.lower()
        
        cuisine_keywords = {
            "Italian": ["italian", "pizza", "pasta", "trattoria"],
            "Japanese": ["japanese", "sushi", "ramen", "izakaya"],
            "Chinese": ["chinese", "dim sum", "szechuan", "cantonese"],
            "French": ["french", "bistro", "brasserie"],
            "Indian": ["indian", "curry", "tandoori"],
            "Thai": ["thai", "pad thai"],
            "Mexican": ["mexican", "taco", "burrito"],
            "Mediterranean": ["mediterranean", "greek", "turkish"],
            "American": ["american", "burger", "steakhouse", "bbq"],
            "Seafood": ["seafood", "fish", "oyster"]
        }
        
        for cuisine, keywords in cuisine_keywords.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return cuisine
        
        return "Local Cuisine"
    
    def _get_fallback_destination_info(self, destination: str) -> Dict[str, Any]:
        """Fallback destination info"""
        return {
            "success": True,
            "cities": [destination],
            "country": "Unknown",
            "is_multi_city": False,
            "city_details": [{
                "name": destination,
                "country": "Unknown",
                "coordinates": None,
                "timezone": "UTC",
                "days_allocated": 3
            }],
            "primary_city": {"name": destination, "timezone": "UTC"}
        }
    
    def _get_fallback_location_data(
        self,
        destination: str,
        current_location: str,
        include_flights: bool
    ) -> Dict[str, Any]:
        """Complete fallback data"""
        dest_info = self._get_fallback_destination_info(destination)
        
        return {
            "destination_info": dest_info,
            "attractions": [],
            "activities": [],
            "experiences": [],
            "hotels": [],
            "restaurants": [],
            "flights": [],
            "local_transport": self._fetch_local_transport(destination, "Unknown", "UTC")
        }