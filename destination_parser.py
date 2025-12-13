"""
Intelligent Destination Parser using LLM

Handles ANY user input:
- "Finland" → "Helsinki, Finland"
- "I want to visit Japan" → "Tokyo, Japan"
- "Take me to NYC" → "New York City, USA"
- "Parris" (misspelling) → "Paris, France"
- "Big Apple" → "New York City, USA"
- "Tokyo" → "Tokyo, Japan" (already a city)
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class DestinationParser:
    """Parse any destination input using LLM intelligence"""
    
    def __init__(self, api_key):
        self.api_key = api_key 
        self.client = OpenAI(api_key=self.api_key)
        
    def parse_destination(self, user_input: str) -> Dict[str, Any]:
        """
        Parse any user input into a structured destination.
        
        Args:
            user_input: Any text like "Finland", "I want to visit Tokyo", "NYC", etc.
            
        Returns:
            Dict with:
                - destination: Cleaned destination name
                - city: Specific city name
                - country: Country name
                - is_country_only: Whether input was just a country
                - suggested_city: If country, the best tourist city
                - original_input: What user typed
                - confidence: How confident the parsing is (high/medium/low)
        """
        logger.info(f"🔍 Parsing destination: '{user_input}'")
        
        try:
            # Use LLM to intelligently parse the destination
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap
                messages=[
                    {
                        "role": "system",
                        "content": """You are a travel destination parser. Extract and normalize destination information from any user input.

                            Rules:
                            1. If user gives a COUNTRY name only, suggest the BEST MAJOR TOURIST CITY in that country
                            2. If user gives a CITY name, keep it as is
                            3. Handle misspellings, nicknames, informal names
                            4. Handle natural language like "I want to visit X" or "Take me to Y"
                            5. Always return valid JSON

                            Examples:
                            - "Finland" → city: "Helsinki", country: "Finland", is_country_only: true
                            - "I want to visit Japan" → city: "Tokyo", country: "Japan", is_country_only: true
                            - "NYC" → city: "New York City", country: "USA", is_country_only: false
                            - "Parris" → city: "Paris", country: "France", is_country_only: false
                            - "Big Apple" → city: "New York City", country: "USA", is_country_only: false
                            - "Tokyo" → city: "Tokyo", country: "Japan", is_country_only: false
                            - "Bali" → city: "Bali", country: "Indonesia", is_country_only: false

                            Respond ONLY with valid JSON in this exact format:
                            {
                                "city": "City Name",
                                "country": "Country Name",
                                "is_country_only": true/false,
                                "confidence": "high/medium/low",
                                "normalized_name": "City, Country"
                            }"""
                    },
                    {
                        "role": "user",
                        "content": f"Parse this destination: {user_input}"
                    }
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=200
            )
            
            # Parse LLM response
            result_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text.replace("```json", "").replace("```", "").strip()
            elif result_text.startswith("```"):
                result_text = result_text.replace("```", "").strip()
            
            result = json.loads(result_text)
            
            # Add original input
            result["original_input"] = user_input
            
            # Log result
            logger.info(f"✅ Parsed: '{user_input}' → {result['normalized_name']}")
            if result.get("is_country_only"):
                logger.info(f"   🌍 Country detected → Suggesting: {result['city']}")
            
            return {
                "success": True,
                "destination": result["normalized_name"],
                "city": result["city"],
                "country": result["country"],
                "is_country_only": result.get("is_country_only", False),
                "suggested_city": result["city"] if result.get("is_country_only") else None,
                "original_input": user_input,
                "confidence": result.get("confidence", "high")
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing destination: {e}")
            # Fallback: use input as-is
            return {
                "success": False,
                "destination": user_input,
                "city": user_input,
                "country": "Unknown",
                "is_country_only": False,
                "suggested_city": None,
                "original_input": user_input,
                "confidence": "low",
                "error": str(e)
            }
    
    def extract_destination_from_sentence(self, sentence: str) -> str:
        """
        Extract just the destination from a full sentence.
        
        Examples:
        - "I want to visit Paris next summer" → "Paris"
        - "Take me to Tokyo please" → "Tokyo"
        - "Planning a trip to Bali" → "Bali"
        
        Args:
            sentence: Natural language sentence
            
        Returns:
            Extracted destination string
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Extract ONLY the destination name from the user's sentence. 
                            Return just the destination name, nothing else.

                            Examples:
                            - "I want to visit Paris next summer" → "Paris"
                            - "Take me to Tokyo please" → "Tokyo"
                            - "Planning a trip to Bali in December" → "Bali"
                            - "Show me Finland" → "Finland"
                            - "New York City vacation" → "New York City"
                            """
                    },
                    {
                        "role": "user",
                        "content": sentence
                    }
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            destination = response.choices[0].message.content.strip()
            logger.info(f"📍 Extracted: '{sentence}' → '{destination}'")
            return destination
            
        except Exception as e:
            logger.error(f"❌ Error extracting destination: {e}")
            return sentence


class SmartDestinationManager:
    """
    Smart wrapper that combines LLM parsing with Google Geocoding.
    This is the main class to use in your application.
    """
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None
    ):
        self.parser = DestinationParser(openai_api_key)
        self.google_api_key = google_api_key or os.getenv("GOOGLE_PLACES_API_KEY")
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    def process_destination(self, user_input: str) -> Dict[str, Any]:
        """
        Complete destination processing:
        1. Parse user input with LLM
        2. Get coordinates with Google Geocoding
        3. Return complete destination info
        
        Args:
            user_input: Any user input about destination
            
        Returns:
            Complete destination info with coordinates, timezone, etc.
        """
        logger.info("="*80)
        logger.info(f"🎯 PROCESSING DESTINATION: '{user_input}'")
        logger.info("="*80)
        
        # Step 1: Parse with LLM
        parse_result = self.parser.parse_destination(user_input)
        
        if not parse_result["success"]:
            logger.warning(f"⚠️ Failed to parse destination, using input as-is")
            search_query = user_input
        else:
            # Use the normalized destination for geocoding
            search_query = parse_result["destination"]
            
            if parse_result.get("is_country_only"):
                logger.info(f"🌍 Country input detected: '{parse_result['original_input']}'")
                logger.info(f"💡 Using suggested city: '{parse_result['suggested_city']}'")
        
        # Step 2: Get coordinates with Google Geocoding
        try:
            import requests
            
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
                
                # Get timezone
                timezone_url = "https://maps.googleapis.com/maps/api/timezone/json"
                tz_params = {
                    "location": f"{location['lat']},{location['lng']}",
                    "timestamp": "1331161200",
                    "key": self.google_api_key
                }
                
                tz_response = requests.get(timezone_url, params=tz_params, timeout=10)
                tz_data = tz_response.json()
                timezone = tz_data.get("timeZoneId", "UTC") if tz_response.ok else "UTC"
                
                logger.info(f"📍 Coordinates found: ({location['lat']}, {location['lng']})")
                logger.info(f"🕐 Timezone: {timezone}")
                logger.info("="*80)
                
                return {
                    "success": True,
                    "name": parse_result.get("city", search_query),
                    "country": parse_result.get("country", "Unknown"),
                    "description": f"A vibrant destination in {parse_result.get('country', 'the world')}",
                    "coordinates": {
                        "lat": location["lat"],
                        "lng": location["lng"]
                    },
                    "timezone": timezone,
                    "original_input": user_input,
                    "normalized_name": search_query,
                    "was_country": parse_result.get("is_country_only", False),
                    "suggested_city": parse_result.get("suggested_city"),
                    "confidence": parse_result.get("confidence", "high")
                }
            else:
                logger.warning(f"⚠️ Geocoding failed: {data.get('status')}")
                # Return without coordinates
                return {
                    "success": False,
                    "name": parse_result.get("city", user_input),
                    "country": parse_result.get("country", "Unknown"),
                    "description": f"Destination in {parse_result.get('country', 'the world')}",
                    "coordinates": None,
                    "timezone": "UTC",
                    "original_input": user_input,
                    "error": "Could not geocode destination"
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting destination info: {e}")
            return {
                "success": False,
                "name": user_input,
                "country": "Unknown",
                "coordinates": None,
                "error": str(e),
                "original_input": user_input
            }
