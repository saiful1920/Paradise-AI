"""
Enhanced Intelligent Destination Parser - FIXED with Intelligent Origin Detection

Key Features:
- Uses ALL cities user provides
- Suggests cities only when user provides country name
- INTELLIGENT FLIGHT ORIGIN DETECTION
- Parses "from X to Y" patterns
- Worldwide destination support
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from openai import OpenAI

logger = logging.getLogger(__name__)


class DestinationParser:
    """Parse ANY destination worldwide using LLM intelligence with smart origin detection"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)
    
    def parse_destination(
        self, 
        user_input: str, 
        duration: int = 3,
        current_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse ANY user input worldwide into structured destination(s) with intelligent origin detection.
        
        ENHANCED: Detects flight origin from:
        1. Explicit "from X" patterns in user input
        2. Provided current_location parameter
        3. Contextual clues
        
        FIXED: If user explicitly provides multiple cities, use ALL of them
        Only suggest cities when user provides just a country name
        """
        logger.info(f"🔍 Parsing: '{user_input}' for {duration} days (user location: {current_location or 'Not provided'})")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a WORLDWIDE travel destination parser with INTELLIGENT ORIGIN DETECTION.

                        ========================
                        DESTINATION PARSING RULES
                        ========================

                        CRITICAL RULES FOR DESTINATION:
                        1. If user provides MULTIPLE CITY NAMES (e.g., "Rome, Florence, Venice" or "Tokyo, Kyoto and Osaka"), return ALL cities they mentioned - DO NOT reduce the list
                        2. If user provides ONLY A COUNTRY NAME (e.g., "Japan", "Italy"), suggest optimal cities based on {duration} days
                        3. Handle destinations from ANY continent worldwide
                        4. Handle misspellings and informal names

                        CITY COUNT LOGIC:
                        - User explicitly lists cities → Use ALL of them (even if it's 3 cities for 2 days)
                        - User gives only country → Suggest cities based on duration:
                        * 1 day → 1 city
                        * 2-3 days → 2 cities
                        * 4-7 days → 3 cities
                        * 7-10 days → 4 cities
                        * 11+ days → 5 cities

                        ========================
                        ORIGIN DETECTION RULES (NEW)
                        ========================

                        INTELLIGENT FLIGHT ORIGIN DETECTION:

                        **PRIORITY ORDER:**
                        1. **Explicit "from" pattern** → "Paris from London" → origin: "London"
                        2. **User location provided** → Use as origin
                        3. **Same country trip** → Use major hub in same country
                        4. **International trip** → Set origin_needs_clarification: true

                        **EXAMPLES:**
                        - "Tokyo" (current_location: "Boston") → origin_city: "Boston", origin_needs_clarification: false
                        - "Bali from Singapore" → origin_city: "Singapore", origin_needs_clarification: false
                        - "Rome to Venice" (multi-city, no origin) → origin_city: null, origin_needs_clarification: true
                        - "Paris" (no current_location) → origin_city: null, origin_needs_clarification: true
                        - "New York to Boston" (domestic) → origin_city: "New York", origin_needs_clarification: false

                        **PATTERNS TO DETECT:**
                        - "X from Y" → origin: Y, destination: X
                        - "from Y to X" → origin: Y, destination: X
                        - "Y to X" → origin: Y, destination: X
                        - "flying from Y" → origin: Y

                        ========================
                        EXAMPLES FOR {duration}-DAY TRIP
                        ========================

                        **User explicitly provides cities (USE ALL):**
                        - "Rome, Florence and Venice" → cities: ["Rome", "Florence", "Venice"], origin_city: null
                        - "Tokyo, Kyoto, Osaka" → cities: ["Tokyo", "Kyoto", "Osaka"], origin_city: null
                        - "Paris and London" → cities: ["Paris", "London"], origin_city: null
                        - "Bangkok from Singapore" → cities: ["Bangkok"], origin_city: "Singapore"

                        **User provides country only (SUGGEST based on duration):**
                        - "Italy" (7 days) → cities: ["Rome", "Florence", "Venice"]
                        - "Italy" (3 days) → cities: ["Rome", "Florence"]
                        - "Japan" (5 days) → cities: ["Tokyo", "Kyoto", "Osaka"]
                        - "Japan" (2 days) → cities: ["Tokyo", "Kyoto"]

                        **With origin detection:**
                        - "Paris from Boston" → cities: ["Paris"], origin_city: "Boston"
                        - "Italy" (current_location: "New York") → cities: ["Rome", "Florence"], origin_city: "New York"

                        Respond ONLY with valid JSON (no markdown):
                        {{
                            "cities": ["City1", "City2", "City3"],
                            "country": "Country Name",
                            "continent": "Asia/Europe/Africa/Americas/Oceania",
                            "is_country_only": true/false,
                            "is_multi_city": true/false,
                            "trip_theme": "beach/cultural/adventure/city/nature/mixed",
                            "confidence": "high/medium/low",
                            "days_per_city": [2, 2, 3],
                            "origin_city": "Detected origin city or null",
                            "origin_needs_clarification": true/false,
                            "origin_detection_confidence": "high/medium/low"
                        }}

                        For days_per_city, distribute {duration} days across cities intelligently.
                        Give priority to first and last cities (arrival/departure)."""
                    },
                    {
                        "role": "user",
                        "content": f"Parse this WORLDWIDE destination for a {duration}-day trip: {user_input}\n\nUser location: {current_location or 'Not provided'}"
                    }
                ],
                temperature=0.1,
                max_tokens=400
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean markdown if present
            if result_text.startswith("```json"):
                result_text = result_text.replace("```json", "").replace("```", "").strip()
            elif result_text.startswith("```"):
                result_text = result_text.replace("```", "").strip()
            
            result = json.loads(result_text)
            
            # ENHANCED: Handle origin detection
            if not result.get('origin_city'):
                if current_location:
                    result['origin_city'] = current_location
                    result['origin_needs_clarification'] = False
                    result['origin_detection_confidence'] = 'high'
                    logger.info(f"✈️ Using provided user location as origin: {current_location}")
                else:
                    result['origin_city'] = None
                    result['origin_needs_clarification'] = True
                    result['origin_detection_confidence'] = 'low'
                    logger.info("⚠️ No origin detected - will need clarification or use default")
            else:
                logger.info(f"✈️ Detected origin from user input: {result['origin_city']}")
            
            # FIXED: Don't limit cities if user explicitly provided them
            cities = result.get("cities", [])
            cities_count = len(cities)
            
            # Adjust days_per_city to match actual cities
            if cities_count > 0:
                days_per_city = result.get("days_per_city", [])
                
                # Recalculate days distribution
                if not days_per_city or len(days_per_city) != cities_count:
                    if duration >= cities_count:
                        # Distribute days evenly
                        base_days = duration // cities_count
                        extra_days = duration % cities_count
                        
                        days_per_city = []
                        for i in range(cities_count):
                            # Give extra days to first/last cities (for arrival/departure)
                            if i == 0 or i == cities_count - 1:
                                days_per_city.append(base_days + (1 if extra_days > 0 else 0))
                                extra_days = max(0, extra_days - 1)
                            else:
                                days_per_city.append(base_days)
                    else:
                        # Duration less than cities (e.g., 3 cities, 2 days)
                        # Give 1 day to most cities, 0 to some
                        days_per_city = [1 if i < duration else 0 for i in range(cities_count)]
                        
                        # If still has extra capacity, add to first city
                        remaining = duration - sum(days_per_city)
                        if remaining > 0 and days_per_city:
                            days_per_city[0] += remaining
                    
                    result["days_per_city"] = days_per_city
            
            result["original_input"] = user_input
            result["duration"] = duration
            
            logger.info(f"✅ Parsed: '{user_input}' → {result['cities']} in {result['country']}")
            logger.info(f"📅 Days per city: {result['days_per_city']}")
            if result.get('origin_city'):
                logger.info(f"✈️ Flight origin: {result['origin_city']}")
            
            return {
                "success": True,
                **result
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing destination: {e}")
            return {
                "success": False,
                "cities": [user_input],
                "country": "Unknown",
                "continent": "Unknown",
                "is_country_only": False,
                "is_multi_city": False,
                "original_input": user_input,
                "confidence": "low",
                "origin_city": current_location,
                "origin_needs_clarification": not bool(current_location),
                "origin_detection_confidence": "high" if current_location else "low",
                "error": str(e)
            }
    
    def get_iata_code(self, city: str, country: str) -> str:
        """
        Get IATA airport code for ANY city worldwide using LLM
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Return ONLY the main airport IATA code (3 letters) for ANY city worldwide.
                        If there are multiple airports, return the main international one.
                        Return ONLY the 3-letter code, nothing else.

                        WORLDWIDE EXAMPLES:

                        **Asia:**
                        - Tokyo, Japan → NRT
                        - Singapore, Singapore → SIN
                        - Bangkok, Thailand → BKK
                        - Dubai, UAE → DXB
                        - Hong Kong, Hong Kong → HKG
                        - Mumbai, India → BOM
                        - Seoul, South Korea → ICN
                        - Beijing, China → PEK
                        - Shanghai, China → PVG
                        - Delhi, India → DEL
                        - Kuala Lumpur, Malaysia → KUL
                        - Manila, Philippines → MNL
                        - Jakarta, Indonesia → CGK
                        - Taipei, Taiwan → TPE
                        - Osaka, Japan → KIX

                        **Europe:**
                        - London, United Kingdom → LHR
                        - Paris, France → CDG
                        - Rome, Italy → FCO
                        - Amsterdam, Netherlands → AMS
                        - Frankfurt, Germany → FRA
                        - Barcelona, Spain → BCN
                        - Madrid, Spain → MAD
                        - Berlin, Germany → BER
                        - Vienna, Austria → VIE
                        - Zurich, Switzerland → ZRH
                        - Brussels, Belgium → BRU
                        - Copenhagen, Denmark → CPH
                        - Stockholm, Sweden → ARN
                        - Oslo, Norway → OSL
                        - Prague, Czech Republic → PRG

                        **Americas:**
                        - New York City, USA → JFK
                        - Los Angeles, USA → LAX
                        - Chicago, USA → ORD
                        - Miami, USA → MIA
                        - San Francisco, USA → SFO
                        - Boston, USA → BOS
                        - Washington DC, USA → IAD
                        - Seattle, USA → SEA
                        - Toronto, Canada → YYZ
                        - Vancouver, Canada → YVR
                        - Mexico City, Mexico → MEX
                        - São Paulo, Brazil → GRU
                        - Buenos Aires, Argentina → EZE
                        - Lima, Peru → LIM
                        - Bogotá, Colombia → BOG

                        **Africa:**
                        - Cairo, Egypt → CAI
                        - Johannesburg, South Africa → JNB
                        - Cape Town, South Africa → CPT
                        - Nairobi, Kenya → NBO
                        - Lagos, Nigeria → LOS
                        - Casablanca, Morocco → CMN
                        - Addis Ababa, Ethiopia → ADD

                        **Oceania:**
                        - Sydney, Australia → SYD
                        - Melbourne, Australia → MEL
                        - Auckland, New Zealand → AKL
                        - Brisbane, Australia → BNE
                        - Perth, Australia → PER

                        If the city is unclear or very small, return the nearest major hub.
                        For example: "Bali" → "DPS" (Denpasar)"""
                    },
                    {
                        "role": "user",
                        "content": f"{city}, {country}"
                    }
                ],
                temperature=0,
                max_tokens=10
            )
            
            code = response.choices[0].message.content.strip().upper()
            if len(code) == 3 and code.isalpha():
                logger.info(f"✈️ IATA code for {city}: {code}")
                return code
            
            logger.warning(f"⚠️ Invalid IATA code returned: {code}")
            return "UNK"
            
        except Exception as e:
            logger.error(f"❌ Error getting IATA code: {e}")
            return "UNK"
    
    def get_country_main_airport(self, country: str) -> str:
        """
        Get the main international airport IATA code for a country using LLM
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Return ONLY the MAIN international airport IATA code (3 letters) for the given country.
                        Return the busiest/most important international hub.
                        Return ONLY the 3-letter code, nothing else.

                        EXAMPLES:
                        - Australia → SYD (Sydney)
                        - Japan → NRT (Tokyo Narita)
                        - United Kingdom → LHR (London Heathrow)
                        - France → CDG (Paris Charles de Gaulle)
                        - Germany → FRA (Frankfurt)
                        - Italy → FCO (Rome Fiumicino)
                        - Spain → MAD (Madrid)
                        - Thailand → BKK (Bangkok)
                        - UAE → DXB (Dubai)
                        - Singapore → SIN (Singapore)
                        - India → DEL (Delhi)
                        - China → PEK (Beijing)
                        - Brazil → GRU (São Paulo)
                        - USA → JFK (New York)
                        - Canada → YYZ (Toronto)
                        - Bangladesh → DAC (Dhaka)
                        - Indonesia → CGK (Jakarta)
                        
                        Return the capital city's airport or the busiest hub."""
                    },
                    {
                        "role": "user",
                        "content": country
                    }
                ],
                temperature=0,
                max_tokens=10
            )
            
            code = response.choices[0].message.content.strip().upper()
            if len(code) == 3 and code.isalpha():
                logger.info(f"🏛️ Country airport for {country}: {code}")
                return code
            
            logger.warning(f"⚠️ Invalid country airport code: {code}")
            return "UNK"
            
        except Exception as e:
            logger.error(f"❌ Error getting country airport: {e}")
            return "UNK"


class SmartDestinationManager:
    """Smart wrapper for WORLDWIDE destination management with intelligent origin detection"""
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None
    ):
        self.parser = DestinationParser(openai_api_key)
        self.openai_api_key = openai_api_key
        self.google_api_key = google_api_key or os.getenv("GOOGLE_PLACES_API_KEY")
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    def process_destination(
        self, 
        user_input: str, 
        duration: int = 3,
        current_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete destination processing for ANY location worldwide with smart origin detection
        """
        
        logger.info("=" * 80)
        logger.info(f"🎯 PROCESSING WORLDWIDE DESTINATION: '{user_input}' for {duration} days")
        if current_location:
            logger.info(f"👤 User location: {current_location}")
        logger.info("=" * 80)
        
        # Parse with LLM (handles worldwide destinations and origin detection)
        parse_result = self.parser.parse_destination(user_input, duration, current_location)
        
        if not parse_result.get("success"):
            logger.warning(f"⚠️ Failed to parse destination, using input as single city")
            parse_result = {
                "success": True,
                "cities": [user_input],
                "country": "Unknown",
                "continent": "Unknown",
                "is_country_only": False,
                "is_multi_city": False,
                "origin_city": current_location,
                "origin_needs_clarification": not bool(current_location)
            }
        
        # Get coordinates for each city using Google Geocoding
        city_details = []
        for i, city in enumerate(parse_result.get("cities", [])):
            city_info = self._get_city_info(city, parse_result.get("country", ""))
            days_list = parse_result.get("days_per_city", [duration])
            city_info["days_allocated"] = days_list[i] if i < len(days_list) else 1
            city_info["order"] = i + 1
            city_details.append(city_info)
        
        # Get IATA codes for flights
        if city_details:
            first_city = city_details[0]
            last_city = city_details[-1] if len(city_details) > 1 else first_city
            
            first_city["iata_code"] = self.parser.get_iata_code(
                first_city["name"], 
                parse_result.get("country", "")
            )
            
            if len(city_details) > 1:
                last_city["iata_code"] = self.parser.get_iata_code(
                    last_city["name"],
                    parse_result.get("country", "")
                )
        
        # NEW: Get country's main airport as fallback
        country = parse_result.get("country", "Unknown")
        country_main_airport = None
        if country and country != "Unknown":
            country_main_airport = self.parser.get_country_main_airport(country)
            logger.info(f"🏛️ Country main airport: {country_main_airport}")
        
        result = {
            "success": True,
            "cities": parse_result.get("cities", []),
            "country": country,
            "continent": parse_result.get("continent", "Unknown"),
            "is_country_only": parse_result.get("is_country_only", False),
            "is_multi_city": parse_result.get("is_multi_city", False) or len(city_details) > 1,
            "trip_theme": parse_result.get("trip_theme", "mixed"),
            "city_details": city_details,
            "primary_city": city_details[0] if city_details else None,
            "total_days": duration,
            "days_per_city": parse_result.get("days_per_city", [duration]),
            "original_input": user_input,
            "confidence": parse_result.get("confidence", "high"),
            
            # Origin detection info
            "origin_city": parse_result.get("origin_city"),
            "origin_needs_clarification": parse_result.get("origin_needs_clarification", True),
            "origin_detection_confidence": parse_result.get("origin_detection_confidence", "low"),
            
            # NEW: Country airport fallback
            "country_main_airport": country_main_airport
        }
        
        logger.info(f"✅ Processed: {len(city_details)} cities for {duration} days")
        for city in city_details:
            logger.info(f"   📍 {city['name']}: {city['days_allocated']} days")
        
        if result.get('origin_city'):
            logger.info(f"✈️ Flight origin detected: {result['origin_city']}")
        elif result.get('origin_needs_clarification'):
            logger.info(f"⚠️ Flight origin needs clarification")
        
        return result
    
    def _get_city_info(self, city: str, country: str) -> Dict[str, Any]:
        """Get detailed city information including coordinates and timezone"""
        try:
            search_query = f"{city}, {country}" if country and country != "Unknown" else city
            
            params = {
                "address": search_query,
                "key": self.google_api_key
            }
            
            response = requests.get(self.geocoding_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                location = result["geometry"]["location"]
                
                timezone = self._get_timezone(location["lat"], location["lng"])
                
                address_components = result.get("address_components", [])
                detected_country = country
                
                for component in address_components:
                    if "country" in component["types"]:
                        detected_country = component["long_name"]
                        break
                
                return {
                    "name": city,
                    "country": detected_country,
                    "formatted_address": result.get("formatted_address", f"{city}, {country}"),
                    "coordinates": {
                        "lat": location["lat"],
                        "lng": location["lng"]
                    },
                    "timezone": timezone,
                    "description": f"A vibrant destination in {detected_country}"
                }
            else:
                logger.warning(f"⚠️ Geocoding failed for {city}: {data.get('status')}")
                return {
                    "name": city,
                    "country": country,
                    "coordinates": None,
                    "timezone": "UTC",
                    "description": f"Destination in {country}"
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting city info for {city}: {e}")
            return {
                "name": city,
                "country": country,
                "coordinates": None,
                "timezone": "UTC",
                "error": str(e)
            }
    
    def _get_timezone(self, lat: float, lng: float) -> str:
        """Get timezone for coordinates"""
        try:
            import time
            url = "https://maps.googleapis.com/maps/api/timezone/json"
            params = {
                "location": f"{lat},{lng}",
                "timestamp": str(int(time.time())),
                "key": self.google_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") == "OK":
                return data.get("timeZoneId", "UTC")
            return "UTC"
            
        except Exception:
            return "UTC"
    
    def get_origin_iata(self, current_location: str) -> str:
        """
        Get IATA code for user's origin location
        
        ENHANCED: Handles any city name worldwide
        """
        if not current_location:
            logger.warning("⚠️ No user location provided, using default: JFK")
            return "JFK"
        
        logger.info(f"✈️ Getting IATA for origin: {current_location}")
        iata = self.parser.get_iata_code(current_location, "")
        
        if iata == "UNK":
            logger.warning(f"⚠️ Could not find IATA for {current_location}, using default: JFK")
            return "JFK"
        
        return iata