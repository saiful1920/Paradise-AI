import json
import os
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage
import re
import logging
import traceback
import requests

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ItineraryService:
    def __init__(self, demo_data_manager, api_key: str):
        self.demo_data = demo_data_manager
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            openai_api_key=api_key
        )
    
    async def validate_budget(
        self,
        destination: str,
        budget: float,
        duration: int,
        travelers: int,
        include_flights: bool,
        include_hotels: bool
    ) -> Dict[str, Any]:
        """Validate if the budget is sufficient using REAL PRICING from Google Places API"""
        
        # Extract city name from "City, Country" format if needed
        destination_city = destination.split(',')[0].strip()
        
        # Get comprehensive destination data with REAL PRICES
        location_data = self.demo_data.fetch_location_based_data(destination_city, None, include_flights)
        
        # Calculate minimum realistic costs based on REAL DATA
        min_costs = self._calculate_minimum_costs_from_real_data(
            location_data, duration, travelers, include_flights, include_hotels
        )
        total_min_cost = sum(min_costs.values())
        
        # Budget is sufficient if it covers at least 90% of minimum costs
        sufficient = budget >= (total_min_cost * 0.90)
        
        breakdown = {
            "flights": min_costs.get("flights", 0),
            "hotels": min_costs.get("hotels", 0),
            "food": min_costs.get("food", 0),
            "transport": min_costs.get("transport", 0),
            "activities": min_costs.get("activities", 0)
        }
        
        if sufficient:
            message = f"Your budget of ${budget:,.2f} is sufficient for this {duration}-day trip to {destination}!"
        else:
            message = f"Your budget of ${budget:,.2f} is a bit low. We recommend at least ${total_min_cost:,.2f} for a comfortable {duration}-day trip for {travelers} travelers to {destination}."
        
        return {
            "sufficient": sufficient,
            "minimum_budget": total_min_cost,
            "current_budget": budget,
            "message": message,
            "breakdown": breakdown
        }
    
    def _calculate_minimum_costs_from_real_data(
        self, 
        location_data: Dict[str, Any], 
        duration: int, 
        travelers: int, 
        include_flights: bool, 
        include_hotels: bool
    ) -> Dict[str, float]:
        """Calculate REALISTIC minimum costs using REAL PRICING from Google Places API"""
        costs = {}
        
        logger.info("=" * 80)
        logger.info("💰 CALCULATING MINIMUM COSTS FROM REAL DATA")
        logger.info("=" * 80)
        
        # Flights (if included)
        if include_flights and location_data.get("flights"):
            cheapest_flight = min(location_data["flights"], key=lambda x: x["price"])
            costs["flights"] = cheapest_flight["price"] * travelers
            logger.info(f"✈️  Flights: ${costs['flights']:.2f} ({travelers} travelers × ${cheapest_flight['price']:.2f})")
        else:
            costs["flights"] = 0
            logger.info(f"✈️  Flights: Not included")
        
        # Hotels (if included) - USE REAL GOOGLE PLACES PRICING
        if include_hotels:
            hotels = location_data.get("hotels", [])
            if hotels:
                # Get cheapest hotel with real pricing
                cheapest_hotel = min(hotels, key=lambda x: x.get("price_per_night", 100))
                avg_hotel_cost = cheapest_hotel["price_per_night"]
                
                rooms_needed = (travelers + 1) // 2  # 2 people per room
                costs["hotels"] = avg_hotel_cost * duration * rooms_needed
                
                logger.info(f"🏨 Hotels (REAL PRICING from Google Places):")
                logger.info(f"   - Cheapest: {cheapest_hotel['name']} - ${avg_hotel_cost:.2f}/night")
                logger.info(f"   - Rooms needed: {rooms_needed}")
                logger.info(f"   - Duration: {duration} nights")
                logger.info(f"   - Total: ${costs['hotels']:.2f}")
            else:
                # Fallback
                avg_hotel_cost = 100
                rooms_needed = (travelers + 1) // 2
                costs["hotels"] = avg_hotel_cost * duration * rooms_needed
                logger.info(f"🏨 Hotels (Fallback): ${costs['hotels']:.2f}")
        else:
            costs["hotels"] = 0
            logger.info(f"🏨 Hotels: Not included")
        
        # Food - USE REAL RESTAURANT PRICING from Google Places
        restaurants = location_data.get("restaurants", [])
        if restaurants:
            # Calculate average meal price from real restaurant data
            budget_restaurants = [r for r in restaurants if r.get("price_level", 2) <= 2]
            
            if budget_restaurants:
                avg_meal_cost = sum(r["avg_price"] for r in budget_restaurants) / len(budget_restaurants)
            else:
                avg_meal_cost = sum(r["avg_price"] for r in restaurants) / len(restaurants)
            
            # 3 meals per day
            costs["food"] = avg_meal_cost * 3 * duration * travelers
            
            logger.info(f"🍽️  Food (REAL PRICING from Google Places):")
            logger.info(f"   - Avg meal cost: ${avg_meal_cost:.2f}")
            logger.info(f"   - Total: ${costs['food']:.2f} (3 meals/day × {duration} days × {travelers} travelers)")
        else:
            # Fallback
            avg_meal_cost = 25
            costs["food"] = avg_meal_cost * 3 * duration * travelers
            logger.info(f"🍽️  Food (Fallback): ${costs['food']:.2f}")
        
        # Transport - USE REAL LOCAL TRANSPORT PRICING
        transport_options = location_data.get("local_transport", [])
        if transport_options:
            # Use average of public transit and taxi
            avg_transport_cost = sum(t["price"] for t in transport_options[:2]) / 2
            costs["transport"] = avg_transport_cost * duration * travelers
            
            logger.info(f"🚕 Transport (REAL PRICING):")
            logger.info(f"   - Avg daily cost: ${avg_transport_cost:.2f}")
            logger.info(f"   - Total: ${costs['transport']:.2f}")
        else:
            costs["transport"] = 15 * duration * travelers
            logger.info(f"🚕 Transport (Fallback): ${costs['transport']:.2f}")
        
        # Activities - USE REAL ACTIVITY PRICING from Google Places
        activities = location_data.get("activities", [])
        attractions = location_data.get("attractions", [])
        
        if activities or attractions:
            all_activities = activities + attractions
            # Calculate average activity cost
            avg_activity_cost = sum(a.get("price", a.get("estimated_cost", 0)) for a in all_activities) / len(all_activities)
            
            # Assume 2 activities per day
            costs["activities"] = avg_activity_cost * 2 * duration * travelers
            
            logger.info(f"🎭 Activities (REAL PRICING from Google Places):")
            logger.info(f"   - Avg activity cost: ${avg_activity_cost:.2f}")
            logger.info(f"   - Total: ${costs['activities']:.2f} (2 activities/day × {duration} days × {travelers} travelers)")
        else:
            costs["activities"] = 30 * duration * travelers
            logger.info(f"🎭 Activities (Fallback): ${costs['activities']:.2f}")
        
        total = sum(costs.values())
        logger.info(f"\n💵 TOTAL MINIMUM COST (REAL DATA): ${total:,.2f}")
        logger.info("=" * 80)
        
        return costs
    
    async def generate_itinerary(
        self,
        destination: str,
        budget: float,
        duration: int,
        travelers: int,
        activity_preference: str,
        include_flights: bool,
        include_hotels: bool,
        user_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a complete itinerary using REAL PRICING from Google Places API"""
        
        # Get current date for dynamic departure date
        current_date = datetime.now()
        
        # Calculate departure date (typically 30 days from now for planning)
        departure_date = current_date + timedelta(days=30)
        
        # Calculate return date
        return_date = departure_date + timedelta(days=duration-1)
        
        # Extract city name from "City, Country" format if needed
        destination_city = destination.split(',')[0].strip()
        
        # Fetch comprehensive location data with REAL PRICES - ALWAYS pass include_flights flag
        logger.info(f"🌍 Fetching location data with REAL PRICES for {destination_city}")
        location_data = self.demo_data.fetch_location_based_data(
            destination_city, 
            user_location or "New York",
            include_flights
        )
        
        # Get destination name
        destination_name = location_data["destination_info"]["name"]
        
        # Generate main title for the itinerary
        if duration == 1:
            main_title = f"{duration} - Day {destination_name} Itinerary"
            trip_dates = f"{departure_date.strftime('%b %d, %Y')}"
        else:
            main_title = f"{duration} - Days {destination_name} Itinerary"
            trip_dates = f"{departure_date.strftime('%b %d')} - {return_date.strftime('%b %d, %Y')}"
        
        # Generate REALISTIC budget breakdown using REAL PRICING
        logger.info("💰 Generating budget breakdown with REAL PRICES...")
        budget_breakdown = await self._generate_realistic_budget_breakdown_from_real_data(
            destination=destination_city,
            budget=budget,
            duration=duration,
            travelers=travelers,
            include_flights=include_flights,
            include_hotels=include_hotels,
            location_data=location_data
        )
        
        # Generate daily activities with REAL DATA, dates, and images
        logger.info("📅 Generating daily activities with real hotels and restaurants...")
        daily_activities = await self._generate_daily_activities_with_data(
            destination=destination_city,
            duration=duration,
            activity_preference=activity_preference,
            budget_breakdown=budget_breakdown,
            location_data=location_data,
            travelers=travelers,
            departure_date=departure_date,
            return_date=return_date
        )
        
        # Generate attractions summary
        attractions_summary = await self._generate_attractions_summary_with_data(
            destination=destination_city,
            location_data=location_data,
            activity_preference=activity_preference
        )
        
        # Prepare hotel and restaurant recommendations with images
        hotel_recommendations = self._prepare_hotel_recommendations_with_images(location_data, departure_date, duration)
        restaurant_recommendations = self._prepare_restaurant_recommendations_with_images(location_data)
        
        # Generate destination highlights with images
        destination_highlights = self._prepare_destination_highlights(location_data)
        
        # Update flight data with actual dates
        if include_flights and location_data.get("flights"):
            updated_flights = self._update_flight_dates(location_data["flights"], departure_date, return_date)
        else:
            updated_flights = None
        
        return {
            "main_title": main_title,  
            "current_date": current_date.strftime("%B %d, %Y"),
            "departure_date": departure_date.strftime("%B %d, %Y"),
            "return_date": return_date.strftime("%B %d, %Y"),
            "trip_dates": trip_dates,
            "duration_days": duration,
            "destination": location_data["destination_info"],
            "duration": duration,
            "travelers": travelers,
            "total_budget": budget,
            "activity_preference": activity_preference,
            "include_flights": include_flights,
            "include_hotels": include_hotels,
            "budget_breakdown": budget_breakdown,
            "daily_activities": daily_activities,
            "attractions_summary": attractions_summary,
            "hotel_recommendations": hotel_recommendations,
            "restaurant_recommendations": restaurant_recommendations,
            "destination_highlights": destination_highlights,
            "updated_flights": updated_flights,
            "created_at": current_date.isoformat(),
            "itinerary_summary": f"A {duration}-day {activity_preference}-paced itinerary for {travelers} traveler(s) to {destination_name} from {departure_date.strftime('%B %d')} to {return_date.strftime('%B %d, %Y')}" if duration > 1 else f"A {duration}-day {activity_preference}-paced itinerary for {travelers} traveler(s) to {destination_name} on {departure_date.strftime('%B %d, %Y')}"
        }
    
    def _update_flight_dates(self, flights: List[Dict[str, Any]], departure_date: datetime, return_date: datetime) -> List[Dict[str, Any]]:
        """Update flight dates to reflect actual departure and return dates"""
        updated_flights = []
        
        # Create departure flights (first 2 flights are outbound)
        for i, flight in enumerate(flights[:2]):
            updated_flight = flight.copy()
            
            # Set departure flight dates
            flight_departure = departure_date + timedelta(hours=i*3)  # Stagger departure times
            flight_arrival = flight_departure + timedelta(hours=12)  # Typical 12-hour flight
            
            updated_flight.update({
                "departure_date": flight_departure.strftime("%B %d, %Y %I:%M %p"),
                "arrival_date": flight_arrival.strftime("%B %d, %Y %I:%M %p"),
                "departure": flight_departure.isoformat(),
                "arrival": flight_arrival.isoformat(),
                "type": "outbound" if i == 0 else "outbound_alternative",
                "duration": "12h 00m"
            })
            updated_flights.append(updated_flight)
        
        # Create return flights (last flight is return)
        if len(flights) >= 3:
            return_flight = flights[2].copy()
            return_departure = return_date.replace(hour=18, minute=0)  # Evening return
            return_arrival = return_departure + timedelta(hours=10)  # Shorter return
            
            return_flight.update({
                "departure_date": return_departure.strftime("%B %d, %Y %I:%M %p"),
                "arrival_date": return_arrival.strftime("%B %d, %Y %I:%M %p"),
                "departure": return_departure.isoformat(),
                "arrival": return_arrival.isoformat(),
                "type": "return",
                "duration": "10h 00m"
            })
            updated_flights.append(return_flight)
        
        return updated_flights
    
    def _prepare_hotel_recommendations_with_images(self, location_data: Dict[str, Any], departure_date: datetime, duration: int) -> List[Dict[str, Any]]:
        """Prepare hotel recommendations with photos, dates, and REAL PRICES"""
        hotels = location_data.get("hotels", [])
        enriched_hotels = []
        
        # Calculate check-in and check-out dates
        check_in_date = departure_date
        check_out_date = departure_date + timedelta(days=duration)
        
        logger.info(f"🏨 Preparing hotel recommendations with images and real prices...")
        
        # Try to get hotel photos from Google Places
        for hotel in hotels[:3]:  # Limit to top 3 hotels
            enriched_hotel = hotel.copy()
            
            # Add dates
            enriched_hotel["check_in_date"] = check_in_date.strftime("%B %d, %Y")
            enriched_hotel["check_out_date"] = check_out_date.strftime("%B %d, %Y")
            enriched_hotel["duration_nights"] = duration
            
            # If no photo exists, try to fetch one based on hotel name
            if not enriched_hotel.get("photo_url") and self.demo_data.google_api_key:
                photo_url = self._fetch_place_photo(
                    enriched_hotel.get("name", ""), 
                    enriched_hotel.get("location", {}),
                    "lodging"
                )
                if photo_url:
                    enriched_hotel["photo_url"] = photo_url
                    logger.info(f"   ✓ Got photo for: {enriched_hotel['name']}")
            
            logger.info(f"   Hotel: {enriched_hotel['name']} - ${enriched_hotel['price_per_night']:.2f}/night")
            enriched_hotels.append(enriched_hotel)
        
        return enriched_hotels
    
    def _prepare_restaurant_recommendations_with_images(self, location_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepare restaurant recommendations with photos and REAL PRICES"""
        restaurants = location_data.get("restaurants", [])
        enriched_restaurants = []
        
        logger.info(f"🍽️  Preparing restaurant recommendations with images and real prices...")
        
        # Try to get restaurant photos from Google Places
        for restaurant in restaurants[:5]:  # Limit to top 5 restaurants
            enriched_restaurant = restaurant.copy()
            
            # If no photo exists, try to fetch one based on restaurant name
            if not enriched_restaurant.get("photo_url") and self.demo_data.google_api_key:
                photo_url = self._fetch_place_photo(
                    enriched_restaurant.get("name", ""),
                    enriched_restaurant.get("location", {}),
                    "restaurant"
                )
                if photo_url:
                    enriched_restaurant["photo_url"] = photo_url
                    logger.info(f"   ✓ Got photo for: {enriched_restaurant['name']}")
            
            logger.info(f"   Restaurant: {enriched_restaurant['name']} - ${enriched_restaurant['avg_price']:.2f}/meal")
            enriched_restaurants.append(enriched_restaurant)
        
        return enriched_restaurants
    
    def _prepare_destination_highlights(self, location_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare destination highlights with best images"""
        attractions = location_data.get("attractions", [])
        activities = location_data.get("activities", [])
        
        # Get top-rated items with photos
        highlights = []
        
        # Add top attractions with photos
        for attraction in attractions:
            if attraction.get("photo_url"):
                highlights.append({
                    "name": attraction["name"],
                    "type": "attraction",
                    "photo_url": attraction["photo_url"],
                    "rating": attraction.get("rating", 4.5)
                })
                if len(highlights) >= 3:
                    break
        
        # Add top activities with photos
        for activity in activities:
            if activity.get("photo_url"):
                highlights.append({
                    "name": activity["name"],
                    "type": "activity",
                    "photo_url": activity["photo_url"],
                    "rating": activity.get("rating", 4.5)
                })
                if len(highlights) >= 6:
                    break
        
        return {
            "count": len(highlights),
            "items": highlights[:6]
        }
    
    def _fetch_place_photo(self, place_name: str, location: Dict[str, float], place_type: str) -> Optional[str]:
        """Fetch place photo from Google Places API"""
        try:
            if not self.demo_data.google_api_key:
                return None
            
            # Search for the place by name and location
            url = f"{self.demo_data.places_base_url}/findplacefromtext/json"
            params = {
                "input": place_name,
                "inputtype": "textquery",
                "fields": "photos,formatted_address,name,rating",
                "locationbias": f"circle:5000@{location.get('lat', 0)},{location.get('lng', 0)}",
                "key": self.demo_data.google_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK" and data.get("candidates"):
                candidate = data["candidates"][0]
                if candidate.get("photos"):
                    photo_reference = candidate["photos"][0].get("photo_reference")
                    return f"{self.demo_data.places_base_url}/photo?maxwidth=800&photo_reference={photo_reference}&key={self.demo_data.google_api_key}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching place photo for {place_name}: {e}")
            return None
    
    async def _generate_daily_activities_with_data(
        self,
        destination: str,
        duration: int,
        activity_preference: str,
        budget_breakdown: Dict[str, Any],
        location_data: Dict[str, Any],
        travelers: int,
        departure_date: datetime,
        return_date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate daily activities including hotels and restaurants with photos, dates, and REAL PRICES"""
        
        activities_budget = budget_breakdown["categories"]["activities"]["amount"]
        
        # Prepare comprehensive data for LLM
        attractions_data = location_data.get("attractions", [])
        activities_data = location_data.get("activities", [])
        hotels_data = location_data.get("hotels", [])
        restaurants_data = location_data.get("restaurants", [])
        
        # Get hotel recommendations with images, dates, and REAL PRICES
        check_out_date = departure_date + timedelta(days=duration)
        recommended_hotels = self._prepare_hotel_recommendations_with_images(location_data, departure_date, duration)
        recommended_restaurants = self._prepare_restaurant_recommendations_with_images(location_data)
        
        # Create photo lookup for activities
        photo_lookup = {}
        for attraction in attractions_data:
            if attraction.get("photo_url"):
                photo_lookup[attraction["name"]] = attraction["photo_url"]
        for activity in activities_data:
            if activity.get("photo_url"):
                photo_lookup[activity["name"]] = activity["photo_url"]
        
        # Format dates for the prompt
        if duration == 1:
            date_info = f"TRIP DATE: {departure_date.strftime('%A, %B %d, %Y')}"
        else:
            date_info = f"TRIP DATES: {departure_date.strftime('%B %d')} - {return_date.strftime('%B %d, %Y')} (Starting on {departure_date.strftime('%A, %B %d')})"
        
        # Format hotel and restaurant data for the prompt with REAL PRICES
        hotel_info = ""
        if recommended_hotels:
            hotel_info = "RECOMMENDED HOTELS WITH DATES AND REAL PRICES:\n"
            for hotel in recommended_hotels[:2]:
                hotel_info += f"- {hotel['name']} (${hotel.get('price_per_night', 0):.2f}/night - REAL PRICE from Google Places)\n"
                hotel_info += f"  Check-in: {hotel.get('check_in_date')}, Check-out: {hotel.get('check_out_date')}\n"
                if hotel.get('photo_url'):
                    hotel_info += f"  [Has photo available]\n"
                hotel_info += f"  Category: {hotel.get('category', 'mid-range')}, Rating: {hotel.get('rating', 4.0)}/5\n"
        
        restaurant_info = ""
        if recommended_restaurants:
            restaurant_info = "TOP RESTAURANTS WITH PHOTOS AND REAL PRICES:\n"
            for restaurant in recommended_restaurants[:5]:
                restaurant_info += f"- {restaurant['name']} (${restaurant.get('avg_price', 0):.2f} avg/meal - REAL PRICE from Google Places)"
                if restaurant.get('photo_url'):
                    restaurant_info += f" [Has photo available]"
                restaurant_info += f"\n  Cuisine: {restaurant.get('cuisine', 'Various')}, Rating: {restaurant.get('rating', 4.0)}/5\n"
        
        prompt = f"""
        Create a detailed {duration}-day itinerary for {destination} for {travelers} traveler(s) with {activity_preference} activity level.
        
        {date_info}
        
        BUDGET FOR ACTIVITIES: ${activities_budget:.2f} total (${activities_budget/duration:.2f} per day)
        
        {hotel_info}
        
        {restaurant_info}
        
        AVAILABLE TOP-RATED ATTRACTIONS WITH REAL PRICES:
        {json.dumps([a for a in attractions_data[:6] if a.get('photo_url')], indent=2)}
        
        AVAILABLE TOP-RATED ACTIVITIES WITH REAL PRICES:
        {json.dumps([a for a in activities_data[:4] if a.get('photo_url')], indent=2)}
        
        IMPORTANT INSTRUCTIONS:
        1. Create exactly {duration} days of activities starting from {departure_date.strftime('%A, %B %d')}
        2. Use SPECIFIC names from the provided hotels and restaurants data
        3. Include the recommended hotels for accommodation with their REAL PRICES
        4. Mention specific restaurants for lunch and dinner EACH DAY with their REAL PRICES
        5. For activities, use names from the attractions and activities data provided
        6. Match the {activity_preference} activity level
        7. Include photo opportunities for popular spots
        8. Make each day unique with morning, afternoon, and evening activities
        9. Include the specific date for each day (Day 1 = {departure_date.strftime('%B %d, %Y')})
        10. All prices shown are REAL prices from Google Places API
        
        ACTIVITY LEVEL GUIDELINES:
        - "relaxed": 1-2 activities per day, plenty of free time
        - "moderate": 2-3 activities per day, balanced pace  
        - "high": 3-4 activities per day, packed schedule
        
        FORMAT: Return ONLY valid JSON array with this structure:
        [
            {{
                "day": 1,
                "date": "{departure_date.strftime('%A, %B %d, %Y')}",
                "title": "Day 1 - Arrival and First Impressions of {destination}",
                "hotel": {{
                    "name": "Specific hotel name from recommendations",
                    "price_per_night": 100.00,
                    "check_in_date": "{departure_date.strftime('%B %d, %Y')}",
                    "check_out_date": "{check_out_date.strftime('%B %d, %Y')}",
                    "photo_url": "Photo URL if available"
                }},
                "morning": {{
                    "time": "09:00 - 12:00",
                    "name": "Specific activity name from data",
                    "description": "Detailed description including photo opportunities",
                    "photo_url": "Photo URL from available data if possible"
                }}
                "afternoon": {{
                    "time": "14:00 - 17:00", 
                    "name": "Specific activity name from data",
                    "description": "Detailed description with sightseeing highlights",
                    "photo_url": "Photo URL from available data if possible"
                }},
                "dinner": {{
                    "time": "19:00 - 21:00",
                    "restaurant": "Specific restaurant name from data",
                    "average_price": 25.00,
                    "description": "Evening dining experience, recommended dishes",
                    "restaurant_photo_url": "Photo URL if available"
                }},
                "evening": {{
                    "time": "21:00 - 23:00",
                    "name": "Evening activity or leisure time",
                    "description": "Evening experience description"
                }},
            }}
        ]
        
        For Day 2 and beyond, calculate the date by adding days to {departure_date.strftime('%B %d, %Y')}.
        Be specific with restaurant and hotel names. Include photo URLs when available in the data.
        Include REAL PRICES from the data provided.
        """
        
        messages = [
            SystemMessage(content="You are an expert travel planner who creates detailed itineraries with specific hotel and restaurant recommendations using real pricing data."),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            
            # Clean JSON response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Enhance with actual photos from our lookup and ensure dates are correct
            for i, day in enumerate(result):
                # Set correct date for each day
                day_date = departure_date + timedelta(days=i)
                day["date"] = day_date.strftime("%A, %B %d, %Y")
                day["date_short"] = day_date.strftime("%b %d")
                
                # Match hotel photo and real price
                if day.get("hotel") and isinstance(day["hotel"], dict):
                    for hotel in recommended_hotels:
                        if hotel["name"].lower() in day["hotel"]["name"].lower() or day["hotel"]["name"].lower() in hotel["name"].lower():
                            if hotel.get("photo_url"):
                                day["hotel"]["photo_url"] = hotel["photo_url"]
                            day["hotel"]["price_per_night"] = hotel["price_per_night"]
                            break
                
                # Match activity photos
                for period in ["morning", "afternoon", "evening"]:
                    if day.get(period) and day[period].get("name"):
                        activity_name = day[period]["name"]
                        # Try to find photo URL by matching activity name
                        for key in photo_lookup:
                            if key.lower() in activity_name.lower() or activity_name.lower() in key.lower():
                                day[period]["photo_url"] = photo_lookup[key]
                                break
                
                # Match restaurant photos and real prices
                for meal in ["lunch", "dinner"]:
                    if day.get(meal) and day[meal].get("restaurant"):
                        restaurant_name = day[meal]["restaurant"]
                        for restaurant in recommended_restaurants:
                            if restaurant["name"].lower() in restaurant_name.lower() or restaurant_name.lower() in restaurant["name"].lower():
                                if restaurant.get("photo_url"):
                                    day[meal]["restaurant_photo_url"] = restaurant["photo_url"]
                                day[meal]["average_price"] = restaurant["avg_price"]
                                break
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating activities: {e}")
            return self._create_fallback_itinerary_with_dates(duration, destination, activity_preference, departure_date, recommended_hotels, recommended_restaurants)
    
    def _create_fallback_itinerary_with_dates(self, duration: int, destination: str, activity_preference: str, departure_date: datetime, hotels: List[Dict], restaurants: List[Dict]) -> List[Dict[str, Any]]:
        """Create a fallback itinerary with dates, images, and real prices"""
        itinerary = []
        
        # Select hotel and restaurants with photos if available
        selected_hotel = hotels[0] if hotels else None
        selected_restaurants = restaurants[:3] if len(restaurants) >= 3 else restaurants
        
        # Calculate check-out date
        check_out_date = departure_date + timedelta(days=duration)
        
        for day in range(1, duration + 1):
            # Calculate date for this day
            day_date = departure_date + timedelta(days=day-1)
            
            # Select different restaurants for each day
            lunch_restaurant = selected_restaurants[day % len(selected_restaurants)] if selected_restaurants else None
            dinner_restaurant = selected_restaurants[(day + 1) % len(selected_restaurants)] if len(selected_restaurants) > 1 else lunch_restaurant
            
            if day == 1:
                title = f"Day {day} - Arrival in {destination}"
                morning = {"time": "09:00 - 12:00", "name": "Arrival and Hotel Check-in", "description": "Settle in and get acquainted with your accommodation"}
                afternoon = {"time": "13:00 - 17:00", "name": "Local Area Exploration", "description": "Take a walk around your neighborhood and visit nearby attractions"}
                evening = {"time": "18:00 - 21:00", "name": "Welcome Dinner", "description": "Enjoy your first meal in the city at a local restaurant"}
            elif day == duration:
                title = f"Day {day} - Departure from {destination}"
                morning = {"time": "09:00 - 12:00", "name": "Last Minute Sightseeing", "description": "Visit any remaining spots on your list"}
                afternoon = {"time": "13:00 - 17:00", "name": "Final Experiences", "description": "Enjoy your last activities before departure"}
                evening = {"time": "18:00 - 21:00", "name": "Farewell Dinner", "description": "One last memorable meal in the city"}
            else:
                title = f"Day {day} - Exploring {destination}"
                morning = {"time": "09:00 - 12:00", "name": "Morning Activities", "description": "Explore local attractions and sights"}
                afternoon = {"time": "13:00 - 17:00", "name": "Afternoon Adventures", "description": "Continue discovering the city's highlights"}
                evening = {"time": "18:00 - 21:00", "name": "Evening Relaxation", "description": "Dinner and evening activities"}
            
            day_entry = {
                "day": day,
                "date": day_date.strftime("%A, %B %d, %Y"),
                "date_short": day_date.strftime("%b %d"),
                "title": title,
                "hotel": {
                    "name": selected_hotel["name"] if selected_hotel else "Your Hotel",
                    "price_per_night": selected_hotel.get("price_per_night", 100) if selected_hotel else 100,
                    "check_in_date": departure_date.strftime("%B %d, %Y"),
                    "check_out_date": check_out_date.strftime("%B %d, %Y"),
                    "photo_url": selected_hotel.get("photo_url") if selected_hotel else None
                },
                "morning": morning,
                "afternoon": afternoon,
                "evening": evening,
                "daily_tip": "Make sure to bring your camera for great photo opportunities!",
                "estimated_cost": "$50-100"
            }
            
            # Add restaurants with photos and real prices if available
            if lunch_restaurant:
                day_entry["lunch"] = {
                    "time": "12:30 - 14:00",
                    "restaurant": lunch_restaurant["name"],
                    "average_price": lunch_restaurant.get("avg_price", 25),
                    "description": f"Enjoy local cuisine at {lunch_restaurant['name']}",
                    "restaurant_photo_url": lunch_restaurant.get("photo_url")
                }
            
            if dinner_restaurant:
                day_entry["dinner"] = {
                    "time": "19:00 - 21:00",
                    "restaurant": dinner_restaurant["name"],
                    "average_price": dinner_restaurant.get("avg_price", 25),
                    "description": f"Dine at {dinner_restaurant['name']} for a memorable evening",
                    "restaurant_photo_url": dinner_restaurant.get("photo_url")
                }
            
            itinerary.append(day_entry)
        
        return itinerary
    
    async def _generate_realistic_budget_breakdown_from_real_data(
        self,
        destination: str,
        budget: float,
        duration: int,
        travelers: int,
        include_flights: bool,
        include_hotels: bool,
        location_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate REALISTIC budget breakdown using REAL PRICING from Google Places API"""
        
        allocations = {}
        total_allocated = 0
        
        logger.info("=" * 80)
        logger.info("💰 GENERATING BUDGET BREAKDOWN FROM REAL PRICING DATA")
        logger.info("=" * 80)
        
        # Step 1: Flights allocation (if included)
        if include_flights:
            if location_data.get("flights") and len(location_data["flights"]) > 0:
                cheapest_flight = min(location_data["flights"], key=lambda x: x["price"])
                allocations["flights"] = cheapest_flight["price"] * travelers
            else:
                allocations["flights"] = 500 * travelers  # Default reasonable flight cost
            total_allocated += allocations["flights"]
            logger.info(f"✈️  Flights: ${allocations['flights']:.2f}")
        else:
            allocations["flights"] = 0
            logger.info(f"✈️  Flights: Not included")
        
        # Step 2: Hotels allocation using REAL Google Places pricing
        if include_hotels:
            hotels = location_data.get("hotels", [])
            if hotels:
                # Get budget hotels
                budget_hotels = [h for h in hotels if h.get("category") == "budget"]
                
                if budget_hotels:
                    avg_budget_price = sum(h["price_per_night"] for h in budget_hotels) / len(budget_hotels)
                else:
                    avg_budget_price = min(h["price_per_night"] for h in hotels)
                
                # Calculate rooms needed
                rooms_needed = (travelers + 1) // 2
                hotel_total = avg_budget_price * duration * rooms_needed
                
                # Ensure doesn't exceed 40% of remaining budget
                remaining = budget - total_allocated
                max_hotel_budget = remaining * 0.40
                
                allocations["hotels"] = min(hotel_total, max_hotel_budget)
                total_allocated += allocations["hotels"]
                
                logger.info(f"🏨 Hotels (REAL Google Places pricing):")
                logger.info(f"   - Avg budget price: ${avg_budget_price:.2f}/night")
                logger.info(f"   - Total allocated: ${allocations['hotels']:.2f}")
            else:
                avg_hotel_cost = 100
                rooms_needed = (travelers + 1) // 2
                allocations["hotels"] = avg_hotel_cost * duration * rooms_needed
                total_allocated += allocations["hotels"]
                logger.info(f"🏨 Hotels (Fallback): ${allocations['hotels']:.2f}")
        else:
            allocations["hotels"] = 0
            logger.info(f"🏨 Hotels: Not included")
        
        # Step 3: Food allocation using REAL restaurant pricing
        restaurants = location_data.get("restaurants", [])
        if restaurants:
            budget_restaurants = [r for r in restaurants if r.get("price_level", 2) <= 2]
            
            if budget_restaurants:
                avg_meal_cost = sum(r["avg_price"] for r in budget_restaurants) / len(budget_restaurants)
            else:
                avg_meal_cost = sum(r["avg_price"] for r in restaurants) / len(restaurants)
            
            # 3 meals per day
            food_cost = avg_meal_cost * 3 * duration * travelers
            
            logger.info(f"🍽️  Food (REAL Google Places pricing):")
            logger.info(f"   - Avg meal: ${avg_meal_cost:.2f}")
        else:
            avg_meal_cost = 25
            food_cost = avg_meal_cost * 3 * duration * travelers
            logger.info(f"🍽️  Food (Fallback): ${avg_meal_cost:.2f}/meal")
        
        # Allocate remaining budget
        remaining_budget = budget - total_allocated
        
        # Food gets calculated amount or 35% of remaining (whichever is lower)
        food_allocated = min(food_cost, remaining_budget * 0.35)
        allocations["food"] = food_allocated
        
        # Calculate how much budget is left AFTER food
        budget_after_food = remaining_budget - food_allocated
        
        # Distribute the REST proportionally
        total_ratio = 0.20 + 0.35 + 0.10  # travel + activities + buffer
        
        allocations["travel"] = budget_after_food * (0.20 / total_ratio)
        allocations["activities"] = budget_after_food * (0.35 / total_ratio)
        remaining_buffer = budget_after_food * (0.10 / total_ratio)
        
        # Calculate total including remaining buffer
        total_allocated = sum(allocations.values())
        grand_total = total_allocated + remaining_buffer
        
        # Calculate percentages based on ORIGINAL BUDGET
        percentages = {cat: (amt / budget * 100) if budget > 0 else 0 
                      for cat, amt in allocations.items()}
        remaining_percentage = (remaining_buffer / budget * 100) if budget > 0 else 0
        
        logger.info(f"\n💵 FINAL BUDGET BREAKDOWN (REAL PRICING):")
        logger.info(f"   - Flights: ${allocations.get('flights', 0):.2f} ({percentages.get('flights', 0):.1f}%)")
        logger.info(f"   - Hotels: ${allocations.get('hotels', 0):.2f} ({percentages.get('hotels', 0):.1f}%)")
        logger.info(f"   - Food: ${allocations.get('food', 0):.2f} ({percentages.get('food', 0):.1f}%)")
        logger.info(f"   - Travel: ${allocations.get('travel', 0):.2f} ({percentages.get('travel', 0):.1f}%)")
        logger.info(f"   - Activities: ${allocations.get('activities', 0):.2f} ({percentages.get('activities', 0):.1f}%)")
        logger.info(f"   - Remaining: ${remaining_buffer:.2f} ({remaining_percentage:.1f}%)")
        logger.info(f"   - Grand Total: ${grand_total:.2f}")
        logger.info("=" * 80)
        
        return {
            "categories": {
                "flights": {"amount": round(allocations.get("flights", 0), 2), "percentage": round(percentages.get("flights", 0), 2)},
                "hotels": {"amount": round(allocations.get("hotels", 0), 2), "percentage": round(percentages.get("hotels", 0), 2)},
                "food": {"amount": round(allocations.get("food", 0), 2), "percentage": round(percentages.get("food", 0), 2)},
                "travel": {"amount": round(allocations.get("travel", 0), 2), "percentage": round(percentages.get("travel", 0), 2)},
                "activities": {"amount": round(allocations.get("activities", 0), 2), "percentage": round(percentages.get("activities", 0), 2)}
            },
            "total_allocated": round(total_allocated, 2),
            "remaining_budget": round(remaining_buffer, 2),
            "remaining_percentage": round(remaining_percentage, 2),
            "grand_total": round(grand_total, 2),
            "original_budget": round(budget, 2)
        }
    
    async def _generate_attractions_summary_with_data(
        self,
        destination: str,
        location_data: Dict[str, Any],
        activity_preference: str
    ) -> Dict[str, Any]:
        """Generate attractions summary using actual data with photos"""
        
        attractions = location_data.get("attractions", [])
        activities = location_data.get("activities", [])
        
        # Extract photo URLs
        attraction_photos = [attr.get("photo_url") for attr in attractions[:5] if attr.get("photo_url")]
        activity_photos = [act.get("photo_url") for act in activities[:5] if act.get("photo_url")]
        
        logger.info(f"📸 Found {len(attraction_photos)} attraction photos and {len(activity_photos)} activity photos")
        
        prompt = f"""
        Create an engaging summary of top attractions and activities for {destination}.
        
        AVAILABLE DATA:
        
        ATTRACTIONS:
        {json.dumps(attractions[:5], indent=2)}
        
        ACTIVITIES:
        {json.dumps(activities[:5], indent=2)}
        
        Return ONLY valid JSON:
        {{
            "attractions": {{
                "description": "Brief engaging description of {destination}'s attractions",
                "items": [
                    "Specific attraction 1 with brief highlight",
                    "Specific attraction 2 with brief highlight", 
                    "Specific attraction 3 with brief highlight",
                    "Specific attraction 4 with brief highlight",
                    "Specific attraction 5 with brief highlight"
                ]
            }},
            "activities": {{
                "description": "Brief engaging description of popular activities in {destination}",
                "items": [
                    "Specific activity 1 with brief description",
                    "Specific activity 2 with brief description",
                    "Specific activity 3 with brief description", 
                    "Specific activity 4 with brief description",
                    "Specific activity 5 with brief description"
                ]
            }}
        }}
        
        Use SPECIFIC names from the provided data.
        """
        
        messages = [
            SystemMessage(content="You create engaging travel content using specific destination information."),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            
            # Clean JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Add photo URLs to the result
            result["attractions"]["photos"] = attraction_photos
            result["activities"]["photos"] = activity_photos
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {
                "attractions": {
                    "description": f"Discover the amazing attractions of {destination}",
                    "items": [
                        "Iconic landmarks and historical sites",
                        "Beautiful natural landscapes and parks", 
                        "Cultural and architectural wonders",
                        "Local markets and shopping districts",
                        "Museums and educational experiences"
                    ],
                    "photos": attraction_photos
                },
                "activities": {
                    "description": f"Experience the best activities in {destination}",
                    "items": [
                        "Guided tours and sightseeing",
                        "Local cuisine and food experiences",
                        "Outdoor adventures and nature activities",
                        "Cultural workshops and classes",
                        "Evening entertainment and nightlife"
                    ],
                    "photos": activity_photos
                }
            }
    
    async def reallocate_budget(
        self,
        current_itinerary: Dict[str, Any],
        selected_categories: List[str]
    ) -> Dict[str, Any]:
        """Reallocate remaining budget to selected categories"""
        budget_breakdown = current_itinerary["budget_breakdown"]
        remaining_budget = budget_breakdown["remaining_budget"]
        
        if remaining_budget <= 0:
            return budget_breakdown
        
        categories = budget_breakdown["categories"].copy()
        
        # Calculate total of selected categories
        selected_total = sum(categories[cat]["amount"] for cat in selected_categories)
        
        if selected_total > 0:
            for category in selected_categories:
                proportion = categories[category]["amount"] / selected_total
                categories[category]["amount"] += remaining_budget * proportion
        else:
            equal_share = remaining_budget / len(selected_categories)
            for category in selected_categories:
                categories[category]["amount"] += equal_share
        
        # Recalculate total and percentages
        total_allocated = sum(cat["amount"] for cat in categories.values())
        for category in categories:
            categories[category]["percentage"] = (categories[category]["amount"] / total_allocated) * 100
        
        return {
            "categories": categories,
            "total_allocated": total_allocated,
            "remaining_budget": 0
        }
    
    async def process_chat_message(
        self,
        message: str,
        current_itinerary: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Process chat messages using LLM for friendly, conversational interactions"""
        
        destination = current_itinerary["destination"]["name"]
        
        # Extract city name for data fetching
        destination_city = destination.split(',')[0].strip()
        
        # Build detailed conversation context
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversation_history[-10:]  # Last 10 messages for context
        ]) if conversation_history else "No previous conversation"
        
        # Format current itinerary details for context - INCLUDING ALL SETTINGS
        itinerary_details = f"""
        CURRENT ITINERARY DETAILS (PRESERVE THESE UNLESS USER EXPLICITLY CHANGES THEM):
        - Destination: {current_itinerary['destination']['name']}, {current_itinerary['destination']['country']}
        - Total Budget: ${current_itinerary['total_budget']:,.2f}
        - Duration: {current_itinerary['duration']} days
        - Travelers: {current_itinerary['travelers']} people
        - Activity Preference: {current_itinerary.get('activity_preference', 'moderate')}
        - Includes Flights: {current_itinerary.get('include_flights', True)} (CRITICAL: User previously selected this!)
        - Includes Hotels: {current_itinerary.get('include_hotels', True)} (CRITICAL: User previously selected this!)
        
        BUDGET BREAKDOWN:
        - Flights: ${current_itinerary['budget_breakdown']['categories']['flights']['amount']:,.2f}
        - Hotels: ${current_itinerary['budget_breakdown']['categories']['hotels']['amount']:,.2f}
        - Food: ${current_itinerary['budget_breakdown']['categories']['food']['amount']:,.2f}
        - Activities: ${current_itinerary['budget_breakdown']['categories']['activities']['amount']:,.2f}
        - Transport: ${current_itinerary['budget_breakdown']['categories']['travel']['amount']:,.2f}
        - Remaining Budget: ${current_itinerary['budget_breakdown']['remaining_budget']:,.2f}
        
        DESTINATION INFORMATION:
        - Description: {current_itinerary['destination']['description']}
        - Timezone: {current_itinerary['destination']['timezone']}
        """
        
        # Format daily activities summary
        daily_activities = current_itinerary.get('daily_activities', [])
        daily_summary = "\n".join([
            f"Day {day['day']}: {day['title']}\n" +
            f"  Morning: {day.get('morning', {}).get('name', 'No activity')}\n" +
            f"  Afternoon: {day.get('afternoon', {}).get('name', 'No activity')}\n" +
            f"  Evening: {day.get('evening', {}).get('name', 'No activity')}"
            for day in daily_activities
        ]) if daily_activities else "No daily activities planned yet"
        
        prompt = f"""
        You are a friendly, helpful travel assistant chatbot. You're chatting with a user about their travel itinerary.

        CRITICAL RULES - READ CAREFULLY:
        1. PRESERVE EXISTING SETTINGS: Unless the user explicitly changes a setting, keep all existing values from the CURRENT ITINERARY
        2. FLIGHTS & HOTELS: User previously selected include_flights={current_itinerary.get('include_flights', True)} and include_hotels={current_itinerary.get('include_hotels', True)} - ONLY change these if user explicitly says to
        3. COMBINE CHANGES: If user makes multiple requests across messages, combine ALL changes in the final proposal
        4. BE PRECISE: When user confirms changes, apply EXACTLY what they requested, nothing more
        5. DESTINATION FORMAT: When proposing destination changes, use ONLY the city name (e.g., "Paris" not "Paris, France")
        6. DON'T REGENERATE: Only propose changes, don't actually regenerate the itinerary until user confirms

        YOUR KNOWLEDGE BASE:

        {itinerary_details}

        DAILY ACTIVITIES SUMMARY:
        {daily_summary}

        CONVERSATION HISTORY:
        {history_text}

        USER'S CURRENT MESSAGE: "{message}"

        YOUR RESPONSE STRATEGY:

        1. FIRST, analyze what the user wants to change:
        - Are they changing DESTINATION? (explicitly mentions city/country) → Use CITY NAME ONLY
        - Are they changing BUDGET? (mentions money, budget, cost)
        - Are they changing DURATION? (mentions days, length, extend)
        - Are they changing TRAVELERS? (mentions people, travelers, group size)
        - Are they changing ACTIVITY PREFERENCE? (mentions relaxed/moderate/high)
        - Are they changing FLIGHTS/HOTELS inclusion? (explicitly says "include flights" or "don't include hotels")
        - Are they just asking questions? (no modification intent)

        2. For QUESTIONS (no modification intent):
        - Answer directly based on current itinerary
        - Be helpful and friendly
        - Don't propose changes
        - Don't ask for confirmation

        3. For MODIFICATION requests:
        - IDENTIFY which specific parameters are being changed
        - PRESERVE all other parameters from current itinerary
        - SUMMARIZE the changes clearly
        - ASK FOR CONFIRMATION before applying
        - Set requires_confirmation = true

        4. For CONFIRMATION messages ("yes", "confirm", "apply changes"):
        - Set confirmed_changes = true
        - Include ALL proposed changes in proposed_changes
        - The system will regenerate the itinerary

        5. CRITICAL: Only change parameters that user EXPLICITLY mentions. Keep everything else the same.

        EXAMPLES OF CORRECT BEHAVIOR:

        User: "What activities are planned for day 2?"
        You: "On Day 2, you have [morning activity], [afternoon activity], and [evening activity] planned. Would you like more details about any of these?"
        Response type: "question", requires_confirmation: false

        User: "I want to change to Paris"
        You: "I'd be happy to change your destination from {current_itinerary['destination']['name']} to Paris! I'll keep your current budget of ${current_itinerary['total_budget']:,.2f}, {current_itinerary['duration']} days, {current_itinerary['travelers']} travelers, and {current_itinerary.get('activity_preference', 'moderate')} activity level. Should I proceed?"
        Proposed changes: {{"destination": "Paris"}}, requires_confirmation: true

        User: "Yes", "Yes, please" or "Okay"
        You: "Great! I'm updating your itinerary to Paris now."
        confirmed_changes: true, proposed_changes: {{"destination": "Paris"}}

        RESPONSE FORMAT:
        You must respond in JSON format with the following structure:
        {{
            "response": "Your friendly, conversational response here.",
            "requires_confirmation": false,
            "confirmed_changes": false,
            "proposed_changes": {{
                "destination": null,
                "budget": null,
                "duration": null,
                "travelers": null,
                "activity_preference": null,
                "include_flights": null,
                "include_hotels": null
            }},
            "response_type": "question|info|modification_proposal|confirmation"
        }}

        IMPORTANT: 
        - Only set non-null values in proposed_changes for parameters the user EXPLICITLY wants to change
        - For destination changes, use ONLY the city name (e.g., "Paris" not "Paris, France")
        - Keep all other parameters as null to preserve current values
        - Don't regenerate until user confirms

        NOW, craft your response based on the user's message and the conversation context.
        Remember: PRESERVE existing settings unless explicitly changed by the user!
        """
        
        messages = [
            SystemMessage(content="You are a precise travel assistant who carefully preserves user preferences and only changes what's explicitly requested."),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            
            # Clean and parse JSON response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Ensure we have proper JSON
            content = content.strip()
            if not content.startswith('{'):
                start_idx = content.find('{')
                if start_idx != -1:
                    content = content[start_idx:]
            if not content.endswith('}'):
                end_idx = content.rfind('}')
                if end_idx != -1:
                    content = content[:end_idx + 1]
            
            result = json.loads(content)
            
            # If changes are confirmed, apply them
            if result.get("confirmed_changes") and any(result["proposed_changes"].values()):
                try:
                    # Get non-null proposed changes
                    changes = {k: v for k, v in result["proposed_changes"].items() if v is not None}
                    
                    # Merge with current itinerary values - PRESERVE existing values for unchanged parameters
                    new_params = {
                        "destination": changes.get("destination", current_itinerary["destination"]["name"]),
                        "budget": changes.get("budget", current_itinerary["total_budget"]),
                        "duration": changes.get("duration", current_itinerary["duration"]),
                        "travelers": changes.get("travelers", current_itinerary["travelers"]),
                        "activity_preference": changes.get("activity_preference", current_itinerary.get("activity_preference", "moderate")),
                        "include_flights": changes.get("include_flights", current_itinerary.get("include_flights", True)),
                        "include_hotels": changes.get("include_hotels", current_itinerary.get("include_hotels", True))
                    }
                    
                    logger.info(f"🔧 APPLYING CHANGES: {changes}")
                    logger.info(f"🔧 FINAL PARAMS: {new_params}")
                    
                    # First validate budget
                    validation = await self.validate_budget(
                        destination=new_params["destination"],
                        budget=new_params["budget"],
                        duration=new_params["duration"],
                        travelers=new_params["travelers"],
                        include_flights=new_params["include_flights"],
                        include_hotels=new_params["include_hotels"]
                    )
                    
                    if not validation["sufficient"]:
                        # Budget is insufficient - return warning message
                        return {
                            "message": validation["message"] + " Would you like to increase your budget or adjust your trip parameters?",
                            "modifications_made": False,
                            "requires_confirmation": False,
                            "proposed_changes": {},
                            "budget_warning": True,
                            "minimum_budget": validation["minimum_budget"]
                        }
                    
                    # Budget is sufficient - generate updated itinerary
                    updated_itinerary = await self.generate_itinerary(**new_params)
                    
                    return {
                        "message": result["response"],
                        "modifications_made": True,
                        "updated_itinerary": updated_itinerary,
                        "requires_confirmation": False,
                        "proposed_changes": {}
                    }
                    
                except Exception as mod_error:
                    logger.error(f"❌ Error applying modifications: {mod_error}")
                    traceback.print_exc()
                    return {
                        "message": f"I understand you want to make changes, but there was an issue: {str(mod_error)}. Could you try rephrasing your request?",
                        "modifications_made": False,
                        "requires_confirmation": False,
                        "proposed_changes": {}
                    }
            
            # No modifications or just conversation
            return {
                "message": result["response"],
                "modifications_made": False,
                "requires_confirmation": result.get("requires_confirmation", False),
                "proposed_changes": result.get("proposed_changes", {})
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing error in process_chat_message: {e}")
            logger.error(f"Content that failed to parse: {content[:500] if 'content' in locals() else 'No content'}")
            
            # Fallback: Friendly conversational response
            return {
                "message": "I'd love to help you modify your itinerary! Please tell me what you'd like to change - the destination, budget, duration, number of travelers, or activity preference.",
                "modifications_made": False,
                "requires_confirmation": False,
                "proposed_changes": {}
            }
            
        except Exception as e:
            logger.error(f"❌ Error in process_chat_message: {e}")
            traceback.print_exc()
            return {
                "message": "I'm here to help you customize your itinerary! You can ask questions about your current plans or suggest changes to the destination, budget, duration, or any other details.",
                "modifications_made": False,
                "requires_confirmation": False,
                "proposed_changes": {}
            }