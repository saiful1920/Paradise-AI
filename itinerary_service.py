import json
import os
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage
import re
import logging

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
        """Validate if the budget is sufficient for the trip using actual destination data"""
        
        # Extract city name from "City, Country" format if needed
        destination_city = destination.split(',')[0].strip()
        
        # Get comprehensive destination data
        location_data = self.demo_data.fetch_location_based_data(destination_city, None, include_flights)
        
        # Calculate minimum realistic costs based on actual data
        min_costs = self._calculate_minimum_costs(location_data, duration, travelers, include_flights, include_hotels)
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
    
    def _calculate_minimum_costs(self, location_data: Dict[str, Any], duration: int, travelers: int, include_flights: bool, include_hotels: bool) -> Dict[str, float]:
        """Calculate REALISTIC minimum costs based on actual destination data"""
        costs = {}
        
        # Flights (if included)
        if include_flights and location_data.get("flights"):
            cheapest_flight = min(location_data["flights"], key=lambda x: x["price"])
            costs["flights"] = cheapest_flight["price"] * travelers
        else:
            costs["flights"] = 0
        
        # Hotels (if included) - FIXED: Ensure proper calculation
        if include_hotels:
            # Use realistic hotel costs based on destination
            destination_hotel_costs = {
                "bali": 60,
                "paris": 120,
                "tokyo": 100,
                "new york": 150,
                "london": 130,
                "rome": 90,
                "barcelona": 85,
                "dubai": 140,
                "bangkok": 50,
                "singapore": 110
            }
            
            # Get destination name
            dest_name = location_data.get("destination_info", {}).get("name", "").lower()
            
            # Find matching hotel cost or use default
            avg_hotel_cost = 100  # default
            for key, price in destination_hotel_costs.items():
                if key in dest_name:
                    avg_hotel_cost = price
                    break
            
            rooms_needed = (travelers + 1) // 2  # 2 people per room
            costs["hotels"] = avg_hotel_cost * duration * rooms_needed
        else:
            costs["hotels"] = 0
        
        # Food - realistic daily costs per person
        costs["food"] = 40 * duration * travelers  # $40/person/day average
        
        # Transport - local transport
        costs["transport"] = 15 * duration * travelers  # $15/person/day average
        
        # Activities - mix of free and paid
        costs["activities"] = 30 * duration * travelers  # $30/person/day average
        
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
        """Generate a complete itinerary using LLM with comprehensive destination data"""
        
        # Extract city name from "City, Country" format if needed
        destination_city = destination.split(',')[0].strip()
        
        # Fetch comprehensive location data - ALWAYS pass include_flights flag
        location_data = self.demo_data.fetch_location_based_data(
            destination_city, 
            user_location or "New York",
            include_flights
        )
        
        # Generate REALISTIC budget breakdown
        budget_breakdown = await self._generate_realistic_budget_breakdown(
            destination=destination_city,
            budget=budget,
            duration=duration,
            travelers=travelers,
            include_flights=include_flights,
            include_hotels=include_hotels,
            location_data=location_data
        )
        
        # Generate daily activities using actual destination data
        daily_activities = await self._generate_daily_activities_with_data(
            destination=destination_city,
            duration=duration,
            activity_preference=activity_preference,
            budget_breakdown=budget_breakdown,
            location_data=location_data,
            travelers=travelers
        )
        
        # Generate attractions summary
        attractions_summary = await self._generate_attractions_summary_with_data(
            destination=destination_city,
            location_data=location_data,
            activity_preference=activity_preference
        )
        
        return {
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
            "hotels": location_data.get("hotels", []),  # Hotel recommendations with photos
            "restaurants": location_data.get("restaurants", []),  # Restaurant recommendations
            "created_at": datetime.now().isoformat()
        }
    
    async def _generate_realistic_budget_breakdown(
        self,
        destination: str,
        budget: float,
        duration: int,
        travelers: int,
        include_flights: bool,
        include_hotels: bool,
        location_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate REALISTIC budget breakdown using actual hotel and restaurant data"""
        
        allocations = {}
        total_allocated = 0
        
        # Step 1: Flights allocation (if included)
        if include_flights:
            if location_data.get("flights") and len(location_data["flights"]) > 0:
                cheapest_flight = min(location_data["flights"], key=lambda x: x["price"])
                allocations["flights"] = cheapest_flight["price"] * travelers
            else:
                allocations["flights"] = 500 * travelers  # Default reasonable flight cost
            total_allocated += allocations["flights"]
        else:
            allocations["flights"] = 0
        
        # Step 2: Hotels allocation using ACTUAL Google Places data
        if include_hotels:
            hotels = location_data.get("hotels", [])
            if hotels:
                # Get budget hotels (category = "budget")
                budget_hotels = [h for h in hotels if h.get("category") == "budget"]
                
                if budget_hotels:
                    # Use average of budget hotels
                    avg_budget_price = sum(h["price_per_night"] for h in budget_hotels) / len(budget_hotels)
                elif hotels:
                    # Use cheapest available
                    avg_budget_price = min(h["price_per_night"] for h in hotels)
                else:
                    # Fallback
                    avg_budget_price = 100
                
                # Calculate rooms needed (2 people per room)
                rooms_needed = (travelers + 1) // 2
                
                # Total hotel cost
                hotel_total = avg_budget_price * duration * rooms_needed
                
                # Ensure doesn't exceed 40% of remaining budget
                remaining = budget - total_allocated
                max_hotel_budget = remaining * 0.40
                
                allocations["hotels"] = min(hotel_total, max_hotel_budget)
                total_allocated += allocations["hotels"]
                
                print(f"🏨 HOTEL CALCULATION (Google Places Data):")
                print(f"   - Hotels found: {len(hotels)}")
                print(f"   - Budget hotels: {len(budget_hotels)}")
                print(f"   - Avg price/night: ${avg_budget_price:.2f}")
                print(f"   - Duration: {duration} nights")
                print(f"   - Rooms needed: {rooms_needed}")
                print(f"   - Raw total: ${hotel_total:.2f}")
                print(f"   - Final allocated: ${allocations['hotels']:.2f}")
            else:
                # Fallback if no hotel data
                avg_hotel_cost = 100
                rooms_needed = (travelers + 1) // 2
                allocations["hotels"] = avg_hotel_cost * duration * rooms_needed
                total_allocated += allocations["hotels"]
                print(f"🏨 HOTEL CALCULATION (Fallback):")
                print(f"   - Using default: ${avg_hotel_cost}/night")
        else:
            allocations["hotels"] = 0
        
        # Step 3: Food allocation using ACTUAL restaurant data
        restaurants = location_data.get("restaurants", [])
        if restaurants:
            # Get average meal prices from actual restaurants
            budget_restaurants = [r for r in restaurants if r.get("price_level", 2) <= 2]
            
            if budget_restaurants:
                avg_meal_cost = sum(r["avg_price"] for r in budget_restaurants) / len(budget_restaurants)
            else:
                avg_meal_cost = sum(r["avg_price"] for r in restaurants) / len(restaurants)
            
            # 3 meals per day
            food_cost = avg_meal_cost * 3 * duration * travelers
            
            print(f"🍽️ FOOD CALCULATION (Google Places Data):")
            print(f"   - Restaurants found: {len(restaurants)}")
            print(f"   - Avg meal cost: ${avg_meal_cost:.2f}")
            print(f"   - Total food cost: ${food_cost:.2f}")
        else:
            # Fallback
            avg_meal_cost = 25
            food_cost = avg_meal_cost * 3 * duration * travelers
            print(f"🍽️ FOOD CALCULATION (Fallback): ${avg_meal_cost}/meal")
        
        # Allocate remaining budget
        remaining_budget = budget - total_allocated
        
        # Food gets calculated amount or 35% of remaining (whichever is lower)
        food_allocated = min(food_cost, remaining_budget * 0.35)
        allocations["food"] = food_allocated
        
        # Calculate how much budget is left AFTER food
        budget_after_food = remaining_budget - food_allocated
        
        # Distribute the REST OF THE BUDGET proportionally
        # Original ratios: travel=20%, activities=35%, buffer=10% out of (20+35+10)=65%
        # New ratios out of what's left:
        total_ratio = 0.20 + 0.35 + 0.10  # 65%
        
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
        
        print(f"\n💰 FINAL BUDGET BREAKDOWN:")
        print(f"   - Flights: ${allocations.get('flights', 0):.2f} ({percentages.get('flights', 0):.1f}%)")
        print(f"   - Hotels: ${allocations.get('hotels', 0):.2f} ({percentages.get('hotels', 0):.1f}%)")
        print(f"   - Food: ${allocations.get('food', 0):.2f} ({percentages.get('food', 0):.1f}%)")
        print(f"   - Travel: ${allocations.get('travel', 0):.2f} ({percentages.get('travel', 0):.1f}%)")
        print(f"   - Activities: ${allocations.get('activities', 0):.2f} ({percentages.get('activities', 0):.1f}%)")
        print(f"   - Remaining: ${remaining_buffer:.2f} ({remaining_percentage:.1f}%)")
        print(f"   - Grand Total: ${grand_total:.2f}")
        print(f"   - Original Budget: ${budget:.2f}")
        print(f"   - Difference: ${abs(grand_total - budget):.2f}")
        
        # Verify calculation
        if abs(grand_total - budget) > 0.01:
            logger.warning(f"⚠️ Budget mismatch! Grand Total: ${grand_total:.2f}, Budget: ${budget:.2f}, Diff: ${abs(grand_total - budget):.2f}")
        
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
    
    async def _generate_daily_activities_with_data(
        self,
        destination: str,
        duration: int,
        activity_preference: str,
        budget_breakdown: Dict[str, Any],
        location_data: Dict[str, Any],
        travelers: int
    ) -> List[Dict[str, Any]]:
        """Generate daily activities including hotels and restaurants with photos"""
        
        activities_budget = budget_breakdown["categories"]["activities"]["amount"]
        
        # Prepare comprehensive data for LLM
        attractions_data = location_data.get("attractions", [])
        activities_data = location_data.get("activities", [])
        hotels_data = location_data.get("hotels", [])
        restaurants_data = location_data.get("restaurants", [])
        
        # Create lookup maps for photos
        photo_lookup = {}
        for attraction in attractions_data:
            if attraction.get("photo_url"):
                photo_lookup[attraction["name"]] = attraction["photo_url"]
        for activity in activities_data:
            if activity.get("photo_url"):
                photo_lookup[activity["name"]] = activity["photo_url"]
        
        # Get recommended hotel and restaurants
        recommended_hotel = hotels_data[0] if hotels_data else None
        recommended_restaurants = restaurants_data[:5] if restaurants_data else []
        
        print(f"📸 Created photo lookup with {len(photo_lookup)} images")
        print(f"🏨 Hotel recommendations: {len(hotels_data)}")
        print(f"🍽️ Restaurant recommendations: {len(restaurants_data)}")
        
        prompt = f"""
        Create a detailed {duration}-day itinerary for {destination} for {travelers} traveler(s) with {activity_preference} activity level.
        
        BUDGET FOR ACTIVITIES: ${activities_budget:.2f} total (${activities_budget/duration:.2f} per day)
        
        RECOMMENDED HOTEL:
        {json.dumps(recommended_hotel, indent=2) if recommended_hotel else "Standard accommodation"}
        
        TOP RESTAURANTS:
        {json.dumps(recommended_restaurants, indent=2)}
        
        AVAILABLE TOP-RATED ATTRACTIONS:
        {json.dumps(attractions_data[:8], indent=2)}
        
        AVAILABLE TOP-RATED ACTIVITIES:
        {json.dumps(activities_data[:5], indent=2)}
        
        ACTIVITY PREFERENCE: {activity_preference}
        - "relaxed": 1-2 activities per day, plenty of rest time
        - "moderate": 2-3 activities per day, balanced pace  
        - "high": 3-4 activities per day, packed schedule
        
        INSTRUCTIONS:
        1. Create exactly {duration} days of activities
        2. Use ACTUAL names from the provided data (attractions, activities, restaurants)
        3. Include specific restaurant recommendations for lunch and dinner
        4. Mention the hotel for check-in on Day 1
        5. Match the {activity_preference} activity level
        6. Consider realistic travel times between locations
        7. Balance paid and free activities to stay within budget
        8. Make each day unique and engaging
        
        FORMAT: Return ONLY valid JSON array with this structure:
        [
            {{
                "day": 1,
                "title": "Day 1 - Arrival and First Impressions",
                "hotel": "{recommended_hotel['name'] if recommended_hotel else 'Your Hotel'}",
                "morning": {{
                    "time": "09:00 - 12:00",
                    "name": "Specific activity name from data",
                    "description": "Detailed description of what we'll do"
                }},
                "lunch": {{
                    "restaurant": "Specific restaurant name from data",
                    "description": "What to try here"
                }},
                "afternoon": {{
                    "time": "13:00 - 17:00", 
                    "name": "Specific activity name",
                    "description": "Detailed description"
                }},
                "dinner": {{
                    "restaurant": "Specific restaurant name from data",
                    "description": "Evening dining experience"
                }},
                "evening": {{
                    "time": "18:00 - 21:00",
                    "name": "Evening activity or leisure",
                    "description": "Evening experience description"
                }}
            }}
        ]
        
        Use REAL names from the provided data. Be specific and realistic.
        """
        
        messages = [
            SystemMessage(content="You are an expert travel planner who creates realistic itineraries using actual destination data."),
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
            
            # Add photo URLs to activities
            for day in result:
                # Add hotel info to each day
                if not day.get("hotel") and recommended_hotel:
                    day["hotel"] = recommended_hotel["name"]
                
                # Match photos for activities
                for period in ["morning", "afternoon", "evening"]:
                    if day.get(period) and day[period].get("name"):
                        activity_name = day[period]["name"]
                        # Try to find photo URL by matching activity name
                        for key in photo_lookup:
                            if key.lower() in activity_name.lower() or activity_name.lower() in key.lower():
                                day[period]["photo_url"] = photo_lookup[key]
                                print(f"📸 Matched photo for: {activity_name} -> {key}")
                                break
                        
                        # If no photo found, use None
                        if "photo_url" not in day[period]:
                            day[period]["photo_url"] = None
            
            return result
            
        except Exception as e:
            print(f"Error generating activities: {e}")
            return self._create_fallback_itinerary(duration, destination, activity_preference)
    
    def _create_fallback_itinerary(self, duration: int, destination: str, activity_preference: str) -> List[Dict[str, Any]]:
        """Create a simple fallback itinerary"""
        itinerary = []
        for day in range(1, duration + 1):
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
            
            itinerary.append({
                "day": day,
                "title": title,
                "morning": morning,
                "afternoon": afternoon,
                "evening": evening
            })
        
        return itinerary
    
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
        
        print(f"📸 Found {len(attraction_photos)} attraction photos and {len(activity_photos)} activity photos")
        
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
            print(f"Error generating summary: {e}")
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

        User: "Yes, please"
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
                    
                    print(f"🔧 APPLYING CHANGES: {changes}")
                    print(f"🔧 FINAL PARAMS: {new_params}")
                    
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
                    print(f"❌ Error applying modifications: {mod_error}")
                    import traceback
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
            print(f"❌ JSON parsing error in process_chat_message: {e}")
            print(f"Content that failed to parse: {content[:500] if 'content' in locals() else 'No content'}")
            
            # Fallback: Friendly conversational response
            return {
                "message": "I'd love to help you modify your itinerary! Please tell me what you'd like to change - the destination, budget, duration, number of travelers, or activity preference.",
                "modifications_made": False,
                "requires_confirmation": False,
                "proposed_changes": {}
            }
            
        except Exception as e:
            print(f"❌ Error in process_chat_message: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "message": "I'm here to help you customize your itinerary! You can ask questions about your current plans or suggest changes to the destination, budget, duration, or any other details.",
                "modifications_made": False,
                "requires_confirmation": False,
                "proposed_changes": {}
            }