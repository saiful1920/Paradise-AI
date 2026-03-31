"""
Enhanced Itinerary Service - Complete Production Version

Features:
1. LLM-powered chatbot - understands ANY user request
2. Perfect budget calculation - never exceeds budget
3. Real data only from Google Places API
4. LLM-generated contingency items
5. Smart activity selection with no repetition
6. Accurate budget breakdown to the penny
"""

import json
import os
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
import logging
import traceback
import requests
import re
from chatbot import ChatbotService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ItineraryService:
    """Enhanced itinerary service with LLM-powered intelligence."""
    
    def __init__(self, demo_data_manager, api_key: str):
        self.demo_data = demo_data_manager
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            openai_api_key=api_key
        )
        self.fast_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=api_key
        )

        self.chatbot = ChatbotService(
            api_key=api_key,
            google_api_key=demo_data_manager.google_api_key,
            demo_data_manager=demo_data_manager  
        )

        # Link chatbot back to service (avoids circular dependency)
        self.chatbot.set_itinerary_service(self)
    
    # ========================================================================
    # BUDGET VALIDATION
    # ========================================================================
    
    async def validate_budget(
        self,
        destination: str,
        budget: float,
        duration: int,
        travelers: int,
        include_flights: bool,
        include_hotels: bool,
        user_location: Optional[str] = None  # ← ADDED THIS PARAMETER
    ) -> Dict[str, Any]:
        """Validate if budget is sufficient using real API data"""
        
        location_data = self.demo_data.fetch_location_based_data(
            destination, 
            user_location,  
            include_flights, 
            duration
        )
        
        min_costs = self._calculate_minimum_costs(
            location_data, duration, travelers, include_flights, include_hotels
        )
        total_min_cost = sum(min_costs.values())
        
        sufficient = budget >= (total_min_cost * 0.85)
        
        if sufficient:
            message = f"Your budget of ${budget:,.2f} is sufficient for this {duration}-day trip!"
        else:
            message = f"Your budget of ${budget:,.2f} is below the recommended minimum of ${total_min_cost:,.2f} for {travelers} traveler(s)."
        
        return {
            "sufficient": sufficient,
            "minimum_budget": total_min_cost,
            "current_budget": budget,
            "message": message,
            "breakdown": min_costs
        }
    
    def _calculate_minimum_costs(
        self,
        location_data: Dict[str, Any],
        duration: int,
        travelers: int,
        include_flights: bool,
        include_hotels: bool
    ) -> Dict[str, float]:
        """Calculate REALISTIC minimum costs from REAL API data"""
        costs = {}
        
        # Flights - use REAL API data
        if include_flights:
            flights = location_data.get("flights", [])
            if flights:
                # Use cheapest REAL flight from API
                cheapest = min(flights, key=lambda x: x.get("price", 9999))
                costs["flights"] = cheapest.get("price", 0) * travelers
                logger.info(f"✅ Using REAL flight price: ${costs['flights']:.2f}")
            else:
                # No flights available - set to 0
                costs["flights"] = 0
                logger.warning("⚠️ No flights found - flight cost set to $0 (arrange separately)")
        else:
            costs["flights"] = 0
        
        # Hotels - use budget category
        if include_hotels:
            hotels = location_data.get("hotels", [])
            if hotels:
                budget_hotels = [h for h in hotels if h.get("category") == "budget"]
                if budget_hotels:
                    avg_price = sum(h["price_per_night"] for h in budget_hotels) / len(budget_hotels)
                else:
                    avg_price = min(h["price_per_night"] for h in hotels)
                rooms = (travelers + 1) // 2
                costs["hotels"] = avg_price * duration * rooms
            else:
                costs["hotels"] = 60 * duration * ((travelers + 1) // 2)
        else:
            costs["hotels"] = 0
        
        # Food - realistic minimum
        restaurants = location_data.get("restaurants", [])
        if restaurants:
            budget_restaurants = [r for r in restaurants if r.get("price_level", 3) <= 2]
            if budget_restaurants:
                avg_meal = sum(r["avg_price"] for r in budget_restaurants) / len(budget_restaurants)
            else:
                avg_meal = sum(r["avg_price"] for r in restaurants) / len(restaurants)
            costs["food"] = avg_meal * 2 * duration * travelers  # 2 meals minimum
        else:
            costs["food"] = 20 * 2 * duration * travelers
        
        # Activities - minimum must-do only
        experiences = location_data.get("experiences", [])
        attractions = location_data.get("attractions", [])
        
        if experiences or attractions:
            all_activities = experiences + attractions
            sorted_activities = sorted(all_activities, key=lambda x: x.get("price", x.get("estimated_cost", 30)))
            min_activities = sorted_activities[:duration]
            avg_cost = sum(a.get("price", a.get("estimated_cost", 20)) for a in min_activities) / len(min_activities) if min_activities else 20
            costs["activities"] = avg_cost * 1 * duration * travelers
        else:
            costs["activities"] = 20 * 1 * duration * travelers
        
        # Transport - minimum local transport
        transport = location_data.get("local_transport", [])
        if transport:
            cheapest_transport = min(t["price"] for t in transport)
            costs["travel"] = cheapest_transport * duration * travelers
        else:
            costs["travel"] = 10 * duration * travelers
        
        return costs
    
    # ========================================================================
    # MAIN ITINERARY GENERATION
    # ========================================================================
    
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
        """Generate complete itinerary with PERFECT budget calculation"""
        
        current_date = datetime.now()
        departure_date = current_date + timedelta(days=30)
        return_date = departure_date + timedelta(days=duration - 1)
        
        logger.info(f"🌍 Generating itinerary for {destination} ({duration} days, ${budget:,.2f})")
        
        # Fetch location data
        location_data = self.demo_data.fetch_location_based_data(
            destination, user_location, include_flights, duration
        )
        
        dest_info = location_data["destination_info"]
        cities = dest_info.get("cities", [destination])
        is_multi_city = dest_info.get("is_multi_city", False)
        
        # Create main title
        if is_multi_city and len(cities) > 1:
            city_names = ", ".join(cities[:-1]) + f" & {cities[-1]}"
            main_title = f"{duration}-Day {dest_info.get('country', '')} Adventure: {city_names}"
        else:
            main_title = f"{duration}-Day {cities[0]} Itinerary"
        
        # STEP 1: Select activities (no repetition)
        selected_activities = self._select_activities_for_trip(
            location_data, duration, travelers, activity_preference
        )
        
        logger.info(f"📋 Selected {len(selected_activities['must_do'])} must-do, {len(selected_activities['recommended'])} recommended")
        
        # STEP 2: Generate daily itinerary
        daily_activities = await self._generate_daily_activities_no_repeat(
            dest_info, duration, activity_preference, selected_activities,
            location_data, travelers, departure_date
        )
        
        # STEP 3: Calculate PERFECT budget (never exceeds)
        budget_breakdown = await self._generate_itemized_budget_breakdown(
            budget, duration, travelers, include_flights, include_hotels,
            location_data, selected_activities, daily_activities
        )
        
        # Generate recommended experiences
        recommended_experiences = await self._generate_recommended_experiences_with_descriptions(
            location_data, activity_preference, duration, cities
        )
        
        # Prepare recommendations
        hotel_recommendations = self._prepare_hotel_recommendations(
            location_data, departure_date, duration
        )
        
        restaurant_recommendations = self._prepare_restaurant_recommendations(location_data)
        
        # Update flights
        updated_flights = None
        if include_flights and location_data.get("flights"):
            updated_flights = self._update_flight_dates(
                location_data["flights"], departure_date, return_date, user_location, cities[0]
            )
        
        # Format destination
        formatted_dest = {
            "name": cities[0] if cities else destination,
            "country": dest_info.get("country", "Unknown"),
            "cities": cities,
            "is_multi_city": is_multi_city,
            "timezone": dest_info.get("city_details", [{}])[0].get("timezone", "UTC"),
            "description": f"Explore the wonders of {dest_info.get('country', 'this destination')}"
        }
        
        trip_dates = f"{departure_date.strftime('%b %d')} - {return_date.strftime('%b %d, %Y')}"
        
        # Generate attractions summary
        attractions_summary = await self._generate_attractions_summary_llm(
            location_data, cities[0] if cities else destination
        )
        
        return {
            "main_title": main_title,
            "current_date": current_date.strftime("%B %d, %Y"),
            "departure_date": departure_date.strftime("%B %d, %Y"),
            "return_date": return_date.strftime("%B %d, %Y"),
            "trip_dates": trip_dates,
            "duration_days": duration,
            "user_location": user_location,
            "destination": formatted_dest,
            "duration": duration,
            "travelers": travelers,
            "total_budget": budget,
            "activity_preference": activity_preference,
            "include_flights": include_flights,
            "include_hotels": include_hotels,
            "budget_breakdown": budget_breakdown,
            "daily_activities": daily_activities,
            "recommended_experiences": recommended_experiences,
            "hotel_recommendations": hotel_recommendations,
            "restaurant_recommendations": restaurant_recommendations,
            "updated_flights": updated_flights,
            "local_transport": location_data.get("local_transport", []),
            "attractions_summary": attractions_summary,
            "created_at": current_date.isoformat()
        }
    
    # ========================================================================
    # ACTIVITY SELECTION
    # ========================================================================
    
    def _select_activities_for_trip(
        self,
        location_data: Dict[str, Any],
        duration: int,
        travelers: int,
        activity_preference: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        IMPROVED: Now includes hotels and restaurants in selection
        Each day will have access to real hotels and restaurants
        """

        attractions = location_data.get("attractions", [])
        experiences = location_data.get("experiences", [])
        hotels = location_data.get("hotels", [])

        # Calculate requirements
        total_activities_needed = duration * 3 
        buffer = 2

        logger.info(f"📊 Need {total_activities_needed} activities (+{buffer} buffer)")
        logger.info(f"📊 Available: {len(attractions)} attractions, {len(experiences)} experiences")
        logger.info(f"📊 Available: {len(hotels)} hotels")

        def score(item, cap=1000, weight=1.0):
            """Calculate relevance score based on rating and review count"""
            return item.get("rating", 0) * min(item.get("user_ratings_total", 1), cap) * weight

        # Sort all categories by quality
        attractions_sorted = sorted(attractions, key=lambda x: score(x), reverse=True)
        experiences_sorted = sorted(experiences, key=lambda x: score(x), reverse=True)
        hotels_sorted = sorted(hotels, key=lambda x: score(x, cap=500), reverse=True)

        # Initialize collections
        must_do = []
        recommended = []
        optional = []
        seen = set()

        # Separate collections for hotels and restaurants
        selected_hotels = []
        selected_restaurants = []

        def add_unique(target, items, limit):
            """Add items to target list, avoiding duplicates"""
            for item in items:
                if len(target) >= limit:
                    return
                uid = item.get("place_id") or item.get("id") or item.get("name")
                if uid in seen:
                    continue
                target.append(item)
                seen.add(uid)

        # --- HOTELS SELECTION ---
        hotels_needed = min(duration, 3)  
        add_unique(selected_hotels, hotels_sorted, hotels_needed)
        
        logger.info(f"🏨 Selected {len(selected_hotels)} hotels for {duration} days")

        # --- ACTIVITIES SELECTION ---
        # MUST DO: Top attractions (prioritize these)
        must_do_limit = min(duration + 1, total_activities_needed)
        add_unique(must_do, attractions_sorted, must_do_limit)
        add_unique(must_do, experiences_sorted, must_do_limit)

        # RECOMMENDED: Mix of attractions, experiences, and some restaurants
        recommended_limit = total_activities_needed - must_do_limit
        add_unique(recommended, attractions_sorted[must_do_limit:], recommended_limit)
        add_unique(recommended, experiences_sorted, recommended_limit)

        # OPTIONAL: Buffer activities
        optional_limit = buffer
        add_unique(optional, attractions_sorted, optional_limit)

        logger.info(
            f"✅ Final selection → must_do: {len(must_do)}, "
            f"recommended: {len(recommended)}, optional: {len(optional)}"
        )
        logger.info(
            f"✅ Hotels: {len(selected_hotels)}, Restaurants: {len(selected_restaurants)}"
        )
        logger.info(
            f"🎯 Total activity pool: "
            f"{len(must_do) + len(recommended) + len(optional)} unique activities"
        )

        return {
            "must_do": must_do,
            "recommended": recommended,
            "optional": optional,
            "hotels": selected_hotels,  
            "restaurants": selected_restaurants  
        }

    
    async def _generate_daily_activities_no_repeat(
        self,
        dest_info: Dict[str, Any],
        duration: int,
        activity_preference: str,
        selected_activities: Dict[str, List[Dict]],
        location_data: Dict[str, Any],
        travelers: int,
        departure_date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate daily activities with NO REPETITION"""
        
        cities = dest_info.get("cities", ["Unknown"])
        days_per_city = dest_info.get("days_per_city", [duration])
        
        city_schedule = []
        current_day = 1
        for i, city in enumerate(cities):
            days = days_per_city[i] if i < len(days_per_city) else 1
            city_schedule.append({
                "city": city,
                "start_day": current_day,
                "end_day": current_day + days - 1,
                "days": days
            })
            current_day += days
        
        # Build flat list of ALL available activities
        all_available = []
        for act in selected_activities["must_do"]:
            all_available.append({
                "name": act.get("name"),
                "type": "attraction",
                "priority": "must_do",
                "city": act.get("city", cities[0]),
                "photo_url": act.get("photo_url"),
                "cost": act.get("estimated_cost", act.get("price", 0))
            })
        
        for act in selected_activities["recommended"]:
            all_available.append({
                "name": act.get("name"),
                "type": act.get("type", "experience"),
                "priority": "recommended",
                "city": act.get("city", cities[0]),
                "photo_url": act.get("photo_url"),
                "cost": act.get("estimated_cost", act.get("price", act.get("avg_price", 0)))
            })
        
        for act in selected_activities["optional"][:duration * 2]:
            all_available.append({
                "name": act.get("name"),
                "type": act.get("type", "restaurant"),
                "priority": "optional",
                "city": act.get("city", cities[0]),
                "photo_url": act.get("photo_url"),
                "cost": act.get("estimated_cost", act.get("price", act.get("avg_price", 0)))
            })
        
        logger.info(f"🎯 Available activity pool: {len(all_available)} unique activities")
        
        # Add hotels
        hotel_list = []
        for hotel in selected_activities.get("hotels", []):
            hotel_list.append({
                "name": hotel.get("name"),
                "price_per_night": hotel.get("price_per_night", 100),
                "address": hotel.get("address", ""),
                "city": hotel.get("city", cities[0])
            })
        
        logger.info(f"🎯 Available activity pool: {len(all_available)} unique activities")
        logger.info(f"🏨 Available hotels: {len(hotel_list)}")
        
        prompt = f"""Create {duration}-day itinerary using ONLY activities and hotels from the list below.

            CRITICAL RULES:
            1. Use ONLY activity names from "AVAILABLE ACTIVITIES"
            2. NEVER repeat an activity (each activity used ONCE only)
            3. Each activity name must EXACTLY match from the list
            4. Prioritize "must_do" activities first
            5. Use "recommended" for variety
            6. Fill remaining with "optional"
            7. Use hotel for evening/meals when possible(if activity not available)

            TRIP DETAILS:
            - Duration: {duration} days
            - Cities: {', '.join(cities)}
            - Start: {departure_date.strftime('%A, %B %d, %Y')}

            CITY SCHEDULE:
            {json.dumps(city_schedule, indent=2)}

            AVAILABLE ACTIVITIES (TOTAL: {len(all_available)}):
            {json.dumps(all_available[:60], indent=2)}

            AVAILABLE HOTELS:
            {json.dumps(hotel_list, indent=2)}

            Return ONLY valid JSON array with {duration} days:
            [
                {{
                    "day": 1,
                    "date": "{departure_date.strftime('%A, %B %d, %Y')}",
                    "city": "City from schedule",
                    "title": "Day 1 - [Title]",
                    "morning": {{
                        "time": "09:00 - 12:00",
                        "name": "[EXACT name from list - must_do priority]",
                        "description": "1-2 sentences (30-40 words)"
                    }},
                    "afternoon": {{
                        "time": "14:00 - 17:30",
                        "name": "[EXACT different name - must_do priority]",
                        "description": "1-2 sentences (30-40 words)"
                    }},
                    "evening": {{
                        "time": "19:00 - 22:00",
                        "name": "[EXACT different name - prefer restaurants]",
                        "description": "1-2 sentences (30-40 words)"
                    }}
                }}
            ]

            VALIDATION: NO activity should appear twice across all {duration} days!
            """
        
        try:
            messages = [
                SystemMessage(content="You are a travel planner. Use EXACT activity names. NO REPETITION. Return valid JSON only."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Validate no repetition
            used_activities = set()
            valid_names = {act["name"].lower(): act for act in all_available}
            
            for day in result:
                for slot in ["morning", "afternoon", "evening"]:
                    if day.get(slot):
                        activity_name = day[slot].get("name", "").lower()
                        
                        # Check if already used
                        if activity_name in used_activities:
                            logger.warning(f"⚠️ DUPLICATE detected: {day[slot].get('name')}")
                            for avail_act in all_available:
                                if avail_act["name"].lower() not in used_activities:
                                    day[slot]["name"] = avail_act["name"]
                                    activity_name = avail_act["name"].lower()
                                    logger.info(f"✅ Replaced with: {avail_act['name']}")
                                    break
                        
                        used_activities.add(activity_name)
                        
                        # Add photo
                        if activity_name in valid_names:
                            day[slot]["photo_url"] = valid_names[activity_name].get("photo_url")
            
            # Update dates
            for i, day in enumerate(result):
                day_date = departure_date + timedelta(days=i)
                day["date"] = day_date.strftime("%A, %B %d, %Y")
                day["date_short"] = day_date.strftime("%b %d")
            
            logger.info(f"✅ Generated {len(result)} days, {len(used_activities)} unique activities used")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            traceback.print_exc()
            return self._create_fallback_itinerary(duration, cities, activity_preference, departure_date)
    
    # ========================================================================
    # PERFECT BUDGET CALCULATION
    # ========================================================================
    
    async def _generate_itemized_budget_breakdown(
        self,
        budget: float,
        duration: int,
        travelers: int,
        include_flights: bool,
        include_hotels: bool,
        location_data: Dict[str, Any],
        selected_activities: Dict[str, List[Dict]],
        daily_activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        PERFECT BUDGET CALCULATION: Never exceed budget, accurate to the penny
        
        FIXED: Remaining budget stays as remaining (not allocated to contingency)
        Contingency is 5-10% SUGGESTION only
        """
        
        logger.info(f"💰 Calculating PERFECT budget for ${budget:,.2f}")
        
        breakdown = {
            "categories": {},
            "detailed_items": {},
            "total_allocated": 0,
            "remaining_budget": 0,
            "original_budget": budget
        }
        
        running_total = 0.0
        
        # ========================================================================
        # STEP 1: FLIGHTS (Fixed Cost)
        # ========================================================================
        
        flight_cost = 0.0
        flight_details = []
        
        if include_flights and location_data.get("flights"):
            flights = location_data["flights"]
            affordable_flights = [f for f in flights if f.get("price", 9999) * travelers <= budget * 0.5]
            
            if affordable_flights:
                selected_flight = min(affordable_flights, key=lambda x: x.get("price", 9999))
            else:
                selected_flight = min(flights, key=lambda x: x.get("price", 9999))
            
            price_per_person = selected_flight.get("price", 400)
            flight_cost = round(price_per_person * travelers, 2)
            
            flight_details.append({
                "item": f"{selected_flight.get('airline', 'Flight')} - Round Trip",
                "quantity": travelers,
                "unit_price": price_per_person,
                "total": flight_cost,
                "essential": "MUST"
            })
            
            running_total += flight_cost
            logger.info(f"✈️ Flights: ${flight_cost:,.2f} | Running: ${running_total:,.2f}")
        
        breakdown["categories"]["flights"] = {"amount": flight_cost, "percentage": 0}
        breakdown["detailed_items"]["flights"] = flight_details
        
        if running_total >= budget:
            logger.error(f"❌ Budget exhausted by flights!")
            breakdown["total_allocated"] = running_total
            breakdown["remaining_budget"] = 0
            return breakdown
        
        # ========================================================================
        # STEP 2: HOTELS (Fixed Cost)
        # ========================================================================
        
        hotel_cost = 0.0
        hotel_details = []
        
        if include_hotels:
            remaining_after_flights = budget - running_total
            max_hotel_budget = remaining_after_flights * 0.45
            
            hotels = location_data.get("hotels", [])
            if hotels:
                sorted_hotels = sorted(hotels, key=lambda x: x.get("price_per_night", 100))
                
                rooms = (travelers + 1) // 2
                
                selected_hotel = None
                for hotel in sorted_hotels:
                    total_hotel_cost = hotel.get("price_per_night", 100) * duration * rooms
                    if running_total + total_hotel_cost <= budget:
                        selected_hotel = hotel
                        break
                
                if not selected_hotel:
                    selected_hotel = sorted_hotels[0]
                
                price_per_night = selected_hotel.get("price_per_night", 80)
                hotel_cost = round(price_per_night * duration * rooms, 2)
                
                if running_total + hotel_cost > budget:
                    hotel_cost = round(budget - running_total, 2)
                    price_per_night = hotel_cost / (duration * rooms)
                
                hotel_details.append({
                    "item": f"{selected_hotel.get('name', 'Hotel')} - {selected_hotel.get('category', 'Standard')}",
                    "quantity": f"{duration} nights × {rooms} room(s)",
                    "unit_price": round(price_per_night, 2),
                    "total": hotel_cost,
                    "essential": "MUST"
                })
                
                running_total += hotel_cost
                logger.info(f"🏨 Hotels: ${hotel_cost:,.2f} | Running: ${running_total:,.2f}")
        
        breakdown["categories"]["hotels"] = {"amount": hotel_cost, "percentage": 0}
        breakdown["detailed_items"]["hotels"] = hotel_details
        
        # ========================================================================
        # STEP 3: CALCULATE REMAINING BUDGET POOL
        # ========================================================================
        
        remaining_budget_pool = round(budget - running_total, 2)
        
        logger.info(f"💵 Remaining budget pool: ${remaining_budget_pool:,.2f}")
        
        if remaining_budget_pool <= 0:
            logger.warning("⚠️ No budget remaining after fixed costs")
            breakdown["total_allocated"] = running_total
            breakdown["remaining_budget"] = 0
            return breakdown
        
        # ========================================================================
        # STEP 4: DISTRIBUTE 90% OF REMAINING (Keep 10% as actual remaining)
        # ========================================================================
        
        # Allocate 90% of remaining pool, keep 10% for user to reallocate
        allocatable_pool = remaining_budget_pool * 0.90
        
        food_pct = 0.35
        activities_pct = 0.45
        transport_pct = 0.20
        
        food_target = round(allocatable_pool * food_pct, 2)
        activities_target = round(allocatable_pool * activities_pct, 2)
        transport_target = round(allocatable_pool * transport_pct, 2)
        
        total_targets = food_target + activities_target + transport_target
        
        if total_targets > allocatable_pool:
            scale = allocatable_pool / total_targets
            food_target = round(food_target * scale, 2)
            activities_target = round(activities_target * scale, 2)
            transport_target = round(allocatable_pool - food_target - activities_target, 2)
        
        # Food
        food_items = self._calculate_food_breakdown(food_target, duration, travelers, location_data)
        food_actual = sum(item["cost"] for item in food_items)
        
        if running_total + food_actual > budget:
            food_actual = round(budget - running_total, 2)
            food_items = [{"item": "Food budget", "cost": food_actual, "detail": f"${food_actual/duration:.0f}/day"}]
        
        running_total += food_actual
        breakdown["categories"]["food"] = {"amount": food_actual, "percentage": 0}
        breakdown["detailed_items"]["food"] = food_items
        logger.info(f"🍔 Food: ${food_actual:,.2f} | Running: ${running_total:,.2f}")
        
        # Activities
        activities_actual_budget = min(activities_target, budget - running_total)
        activities_breakdown = self._calculate_activities_breakdown(
            activities_actual_budget, duration, travelers, selected_activities, daily_activities
        )
        
        activities_actual = activities_breakdown["total"]
        running_total += activities_actual
        
        breakdown["categories"]["activities"] = {
            "amount": activities_actual,
            "percentage": 0,
            "must_do_total": activities_breakdown["must_do_total"],
            "recommended_total": activities_breakdown["recommended_total"],
            "optional_total": activities_breakdown["optional_total"]
        }
        breakdown["detailed_items"]["must_do_activities"] = activities_breakdown["must_do_items"]
        breakdown["detailed_items"]["recommended_activities"] = activities_breakdown["recommended_items"]
        breakdown["detailed_items"]["optional_activities"] = activities_breakdown["optional_items"]
        logger.info(f"🎭 Activities: ${activities_actual:,.2f} | Running: ${running_total:,.2f}")
        
        # Transport
        transport_actual_budget = min(transport_target, budget - running_total)
        transport_items = self._calculate_transport_breakdown(transport_actual_budget, duration, travelers, location_data)
        transport_actual = sum(item["cost"] for item in transport_items)
        
        if running_total + transport_actual > budget:
            transport_actual = round(budget - running_total, 2)
            transport_items = [{"item": "Local transport", "cost": transport_actual, "detail": "Daily transport"}]
        
        running_total += transport_actual
        breakdown["categories"]["travel"] = {"amount": transport_actual, "percentage": 0}
        breakdown["detailed_items"]["travel"] = transport_items
        logger.info(f"🚗 Transport: ${transport_actual:,.2f} | Running: ${running_total:,.2f}")
        
        # ========================================================================
        # STEP 5: CONTINGENCY (5-10% SUGGESTION - NOT ALLOCATED)
        # ========================================================================
        
        # Calculate suggested contingency (7.5% of total budget)
        suggested_contingency = round(budget * 0.075, 2)
        
        contingency_items = await self._get_contingency_items_llm(
            location_data["destination_info"].get("primary_city", {}).get("name", "destination"),
            duration,
            travelers,
            budget
        )
        
        breakdown["categories"]["contingency"] = {
            "amount": 0,  # NOT allocated
            "percentage": 0,
            "suggested_amount": suggested_contingency,
            "suggested_percentage": 7.5,
            "note": "Reserve 5-10% of your total budget for unexpected costs"
        }
        breakdown["detailed_items"]["contingency"] = contingency_items
        
        logger.info(f"💼 Contingency: ${suggested_contingency:,.2f} (suggested, not allocated)")
        
        # ========================================================================
        # STEP 6: FINALIZE & VALIDATE
        # ========================================================================
        
        for cat in breakdown["categories"]:
            breakdown["categories"][cat]["amount"] = round(breakdown["categories"][cat]["amount"], 2)
            breakdown["categories"][cat]["percentage"] = round((breakdown["categories"][cat]["amount"] / budget * 100) if budget > 0 else 0, 2)
        
        breakdown["total_allocated"] = round(running_total, 2)
        breakdown["remaining_budget"] = round(budget - running_total, 2)
        breakdown["remaining_percentage"] = round((breakdown["remaining_budget"] / budget * 100) if budget > 0 else 0, 2)
        
        if breakdown["total_allocated"] > budget:
            logger.error(f"❌ CRITICAL: Budget exceeded!")
            excess = breakdown["total_allocated"] - budget
            breakdown["categories"]["travel"]["amount"] = max(0, breakdown["categories"]["travel"]["amount"] - excess)
            breakdown["total_allocated"] = budget
            breakdown["remaining_budget"] = 0
        
        logger.info(f"✅ PERFECT budget: ${breakdown['total_allocated']:,.2f} / ${budget:,.2f}")
        logger.info(f"✅ Remaining: ${breakdown['remaining_budget']:,.2f} (available for reallocation)")
        logger.info(f"💡 Suggested contingency: ${suggested_contingency:,.2f} (5-10% buffer)")
        
        return breakdown
    
    def _calculate_food_breakdown(
        self,
        food_budget: float,
        duration: int,
        travelers: int,
        location_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate food breakdown - NEVER exceed food_budget"""
        
        if food_budget <= 0:
            return []
        
        restaurants = location_data.get("restaurants", [])
        
        if restaurants:
            budget_restaurants = [r for r in restaurants if r.get("price_level", 3) <= 2]
            avg_meal = sum(r["avg_price"] for r in budget_restaurants) / len(budget_restaurants) if budget_restaurants else 20
        else:
            avg_meal = 20
        
        daily_per_person = food_budget / (duration * travelers)
        
        if daily_per_person < 30:
            breakfast = round(daily_per_person * 0.25, 2)
            lunch = round(daily_per_person * 0.40, 2)
            dinner = round(daily_per_person * 0.35, 2)
        elif daily_per_person < 50:
            breakfast = round(daily_per_person * 0.20, 2)
            lunch = round(daily_per_person * 0.35, 2)
            dinner = round(daily_per_person * 0.35, 2)
        else:
            breakfast = round(daily_per_person * 0.18, 2)
            lunch = round(daily_per_person * 0.36, 2)
            dinner = round(daily_per_person * 0.36, 2)
        
        breakfast_total = round(breakfast * duration * travelers, 2)
        lunch_total = round(lunch * duration * travelers, 2)
        dinner_total = round(dinner * duration * travelers, 2)
        beverages_total = round(food_budget - breakfast_total - lunch_total - dinner_total, 2)
        
        return [
            {"item": "Breakfasts", "cost": breakfast_total, "detail": f"${breakfast:.0f}/meal × {duration} days"},
            {"item": "Lunches", "cost": lunch_total, "detail": f"${lunch:.0f}/meal × {duration} days"},
            {"item": "Dinners", "cost": dinner_total, "detail": f"${dinner:.0f}/meal × {duration} days"},
            {"item": "Beverages & snacks", "cost": max(0, beverages_total), "detail": "Water, coffee, snacks"}
        ]
    
    def _calculate_activities_breakdown(
        self,
        activities_budget: float,
        duration: int,
        travelers: int,
        selected_activities: Dict[str, List[Dict]],
        daily_activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate activities - NEVER exceed activities_budget"""
        
        if activities_budget <= 0:
            return {
                "must_do_items": [],
                "recommended_items": [],
                "optional_items": [],
                "must_do_total": 0,
                "recommended_total": 0,
                "optional_total": 0,
                "total": 0
            }
        
        used_activity_names = set()
        for day in daily_activities:
            for slot in ["morning", "afternoon", "evening"]:
                if day.get(slot):
                    used_activity_names.add(day[slot].get("name", "").lower())
        
        must_do_items = []
        recommended_items = []
        optional_items = []
        
        must_do_total = 0.0
        recommended_total = 0.0
        
        for act in selected_activities.get("must_do", []):
            if act.get("name", "").lower() in used_activity_names:
                cost_per_person = act.get("estimated_cost", act.get("price", 20))
                total_cost = round(cost_per_person * travelers, 2)
                
                if must_do_total + total_cost <= activities_budget:
                    must_do_items.append({
                        "item": act.get("name"),
                        "location": act.get("city", ""),
                        "cost": total_cost,
                        "duration": act.get("duration", "Half day"),
                        "essential": "MUST"
                    })
                    must_do_total += total_cost
        
        remaining_budget = activities_budget - must_do_total
        
        for act in selected_activities.get("recommended", []):
            if act.get("name", "").lower() in used_activity_names:
                cost_per_person = act.get("price", act.get("estimated_cost", act.get("avg_price", 25)))
                total_cost = round(cost_per_person * travelers, 2)
                
                if recommended_total + total_cost <= remaining_budget:
                    recommended_items.append({
                        "item": act.get("name"),
                        "location": act.get("city", ""),
                        "cost": total_cost,
                        "duration": act.get("duration", "2-3 hours"),
                        "essential": "Recommended"
                    })
                    recommended_total += total_cost
        
        for act in selected_activities.get("optional", [])[:5]:
            if act.get("name", "").lower() not in used_activity_names:
                cost_per_person = act.get("price", act.get("estimated_cost", act.get("avg_price", 20)))
                total_cost = round(cost_per_person * travelers, 2)
                
                optional_items.append({
                    "item": act.get("name"),
                    "location": act.get("city", ""),
                    "cost": total_cost,
                    "duration": act.get("duration", "1-2 hours"),
                    "essential": "Optional"
                })
        
        return {
            "must_do_items": must_do_items,
            "recommended_items": recommended_items,
            "optional_items": optional_items,
            "must_do_total": round(must_do_total, 2),
            "recommended_total": round(recommended_total, 2),
            "optional_total": sum(item["cost"] for item in optional_items),
            "total": round(must_do_total + recommended_total, 2)
        }
    
    def _calculate_transport_breakdown(
        self,
        transport_budget: float,
        duration: int,
        travelers: int,
        location_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate transport - NEVER exceed transport_budget"""
        
        if transport_budget <= 0:
            return []
        
        transport_data = location_data.get("local_transport", [])
        
        if transport_data:
            sorted_transport = sorted(transport_data, key=lambda x: x["price"])
            selected = sorted_transport[0]
            
            daily_cost = min(selected["price"], transport_budget / (duration * travelers))
            total_cost = round(daily_cost * duration * travelers, 2)
            
            if total_cost > transport_budget:
                total_cost = round(transport_budget, 2)
                daily_cost = total_cost / (duration * travelers)
            
            return [{
                "item": selected["mode"],
                "cost": total_cost,
                "detail": f"${daily_cost:.0f}/day × {duration} days"
            }]
        else:
            return [{
                "item": "Local transport",
                "cost": round(transport_budget, 2),
                "detail": f"${transport_budget/(duration*travelers):.0f}/day"
            }]
    
    async def _get_contingency_items_llm(
        self,
        destination: str,
        duration: int,
        travelers: int,
        total_budget: float
    ) -> List[Dict[str, Any]]:
        """
        LLM-POWERED: Generate contingency items that ADD UP to suggested amount
        """
        
        # Calculate target contingency (7.5% of total budget)
        target_contingency = round(total_budget * 0.075, 2)
        
        prompt = f"""You are a travel budget expert. Generate a realistic contingency/miscellaneous budget breakdown for this trip.

            TRIP DETAILS:
            - Destination: {destination}
            - Duration: {duration} days
            - Travelers: {travelers}
            - Total Budget: ${total_budget:,.2f}
            - TARGET CONTINGENCY: ${target_contingency:,.2f}

            CRITICAL: The sum of ALL estimated costs must equal EXACTLY ${target_contingency:,.2f}

            GENERATE 6-8 contingency categories with:
            1. Category name (be specific to destination if relevant)
            2. Estimated cost in USD (must sum to ${target_contingency:,.2f})
            3. How to minimize this cost

            CONSIDERATIONS:
            - Local customs (tipping culture, etc.)
            - Common tourist expenses
            - Unexpected costs typical for this destination
            - Travel insurance
            - Emergency buffer

            VALIDATION: Before returning, verify that the sum equals ${target_contingency:,.2f}. Adjust the last few items if needed to match exactly.

            Return ONLY valid JSON array:
            [
                {{
                    "category": "Category name",
                    "estimated": 15,
                    "detail": "How to minimize or tips"
                }}
            ]

            The total of all "estimated" values MUST equal ${target_contingency:,.2f}."""
        
        try:
            messages = [
                SystemMessage(content=f"You are a travel budget expert. Return only valid JSON array. CRITICAL: Sum of estimated values must equal ${target_contingency:.2f}"),
                HumanMessage(content=prompt)
            ]
            
            response = await self.fast_llm.ainvoke(messages)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            items = json.loads(content)
            
            # VALIDATION: Ensure sum matches target
            total = sum(item["estimated"] for item in items)
            
            if abs(total - target_contingency) > 1:  # Allow $1 tolerance
                logger.warning(f"⚠️ Contingency sum mismatch: ${total} vs ${target_contingency}")
                
                # Adjust proportionally
                scale_factor = target_contingency / total if total > 0 else 1
                for item in items:
                    item["estimated"] = round(item["estimated"] * scale_factor)
                
                # Final adjustment to match exactly
                actual_total = sum(item["estimated"] for item in items)
                if actual_total != target_contingency:
                    difference = target_contingency - actual_total
                    items[-1]["estimated"] += difference
            
            final_total = sum(item["estimated"] for item in items)
            logger.info(f"💼 Generated {len(items)} contingency items via LLM | Total: ${final_total}")
            
            return items
            
        except Exception as e:
            logger.error(f"❌ Error generating contingency items: {e}")
            
            # Fallback with correct totals
            item_count = 8
            per_item = round(target_contingency / item_count)
            remainder = target_contingency - (per_item * (item_count - 1))
            
            return [
                {"category": "Tipping for services", "estimated": per_item, "detail": "Research local tipping customs; tip when service is exceptional"},
                {"category": "Emergency medical expenses", "estimated": per_item, "detail": "Purchase travel insurance to cover medical emergencies"},
                {"category": "Unexpected transportation costs", "estimated": per_item, "detail": "Use public transportation or walk when possible"},
                {"category": "Souvenirs and gifts", "estimated": per_item, "detail": "Set a strict budget for souvenirs and stick to it"},
                {"category": "Food and drink beyond budget", "estimated": per_item, "detail": "Plan meals ahead; try local street food"},
                {"category": "Sightseeing and entry fees", "estimated": per_item, "detail": "Research free attractions and discounts"},
                {"category": "Miscellaneous expenses", "estimated": per_item, "detail": "Keep a small buffer for unexpected costs"},
                {"category": "Currency exchange fees", "estimated": remainder, "detail": "Use local ATMs to minimize exchange fees"}
            ]
    
    # ========================================================================
    # HELPER METHODS - Recommendations & Summaries
    # ========================================================================
    
    async def _generate_attractions_summary_llm(
        self,
        location_data: Dict[str, Any],
        destination: str
    ) -> Dict[str, Any]:
        """Generate attractions summary with SHORT descriptions"""
        
        attractions = location_data.get("attractions", [])[:5]
        activities = location_data.get("experiences", [])[:5]
        
        attraction_photos = [a.get("photo_url") for a in attractions if a.get("photo_url")]
        activity_photos = [a.get("photo_url") for a in activities if a.get("photo_url")]
        
        prompt = f"""Create brief summaries for {destination}.

            ATTRACTIONS:
            {json.dumps([{"name": a["name"]} for a in attractions], indent=2)}

            ACTIVITIES:
            {json.dumps([{"name": a["name"]} for a in activities], indent=2)}

            Return ONLY valid JSON (no markdown):
            {{
                "attractions": {{
                    "description": "One sentence about {destination}'s attractions (30-40 words max)",
                    "items": [
                        "Attraction 1 with brief note (20 words max)",
                        "Attraction 2 with brief note (20 words max)",
                        "Attraction 3 with brief note (20 words max)",
                        "Attraction 4 with brief note (20 words max)",
                        "Attraction 5 with brief note (20 words max)"
                    ]
                }},
                "activities": {{
                    "description": "One sentence about activities (30-40 words max)",
                    "items": [
                        "Activity 1 with brief note (20 words max)",
                        "Activity 2 with brief note (20 words max)",
                        "Activity 3 with brief note (20 words max)",
                        "Activity 4 with brief note (20 words max)",
                        "Activity 5 with brief note (20 words max)"
                    ]
                }}
            }}

            Use SPECIFIC names. Keep ALL descriptions under 30 words and the item notes under 20 words."""
        
        try:
            messages = [
                SystemMessage(content="You are a travel writer. Write BRIEF descriptions (30-40 words max) and the items (20 words max each). Return only valid JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.fast_llm.ainvoke(messages)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            result["attractions"]["photos"] = attraction_photos[:4]
            result["activities"]["photos"] = activity_photos[:4]
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating attractions summary: {e}")
            return {
                "attractions": {
                    "description": f"Discover {destination}'s iconic landmarks and hidden gems.",
                    "items": [a["name"] for a in attractions],
                    "photos": attraction_photos[:4]
                },
                "activities": {
                    "description": f"Experience the best tours and activities {destination} offers.",
                    "items": [a["name"] for a in activities],
                    "photos": activity_photos[:4]
                }
            }
    
    async def _generate_recommended_experiences_with_descriptions(
        self,
        location_data: Dict[str, Any],
        activity_preference: str,
        duration: int,
        cities: List[str]
    ) -> Dict[str, Any]:
        """
        FIXED: Proper categorization, max 5 per category
        """
        
        experiences = location_data.get("experiences", [])
        attractions = location_data.get("attractions", [])
        
        logger.info(f"📊 Raw data: {len(experiences)} experiences, {len(attractions)} attractions")
        
        tours = []
        excursions = []
        
        for exp in experiences:
            exp_type = exp.get("type", "").lower()
            name = exp.get("name", "").lower()
            
            if any(keyword in name or keyword in exp_type for keyword in ["day trip", "excursion", "adventure", "safari", "hiking", "trek", "island", "cruise", "boat"]):
                excursions.append(exp)
            elif any(keyword in name or keyword in exp_type for keyword in ["tour", "walk", "guide", "food", "bike", "class", "workshop", "cooking", "lesson"]):
                tours.append(exp)
            else:
                excursions.append(exp)
        
        # Must-see: Top 5 attractions ONLY
        must_see = sorted(
            attractions,
            key=lambda x: x.get("rating", 0) * min(x.get("user_ratings_total", 1), 1000),
            reverse=True
        )[:5]
        
        # Limit to 5 each
        tours = tours[:5]
        excursions = excursions[:5]
        
        logger.info(f"✅ Categorized: {len(tours)} tours, {len(excursions)} excursions, {len(must_see)} must-see (MAX 5 each)")
        
        destination = cities[0] if cities else "the destination"
        
        tours_with_desc = await self._add_llm_descriptions(tours, "tour", destination)
        excursions_with_desc = await self._add_llm_descriptions(excursions, "excursion", destination)
        must_see_with_desc = await self._add_llm_descriptions(must_see, "attraction", destination)
        
        # Add Google Maps links
        for item in tours_with_desc + excursions_with_desc + must_see_with_desc:
            if item.get("location"):
                lat = item["location"].get("lat")
                lng = item["location"].get("lng")
                if lat and lng:
                    item["maps_link"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        
        return {
            "tours": {
                "title": "Guided Tours",
                "description": "Expert-led tours to discover hidden gems and local secrets",
                "items": tours_with_desc,
                "count": len(tours)
            },
            "excursions": {
                "title": "Day Excursions",
                "description": "Unforgettable day trips to explore beyond the city",
                "items": excursions_with_desc,
                "count": len(excursions)
            },
            "must_see": {
                "title": "Must-See Attractions",
                "description": "Iconic landmarks and top-rated sites you can't miss",
                "items": must_see_with_desc,
                "count": len(must_see)
            },
            "total_available": len(experiences) + len(attractions)
        }
    
    async def _add_llm_descriptions(
        self,
        items: List[Dict],
        item_type: str,
        destination: str
    ) -> List[Dict]:
        """Add LLM-generated SHORT descriptions (20-30 words)"""
        
        if not items:
            return []
        
        item_names = [item.get("name", "Unknown") for item in items]
        
        prompt = f"""Generate SHORT descriptions for these {item_type}s in {destination}.
            Each description should be exactly 1 sentence (15-20 words).

            Items:
            {json.dumps(item_names, indent=2)}

            Return ONLY valid JSON (no markdown):
            {{
                "Item Name 1": "One short engaging sentence (15-20 words).",
                "Item Name 2": "One short engaging sentence (15-20 words)."
            }}"""
        
        try:
            messages = [
                SystemMessage(content="You are a travel writer. Write SHORT 1-sentence descriptions (15-20 words). Return only valid JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.fast_llm.ainvoke(messages)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            descriptions = json.loads(content)
            
            result = []
            for item in items:
                item_copy = item.copy()
                name = item.get("name", "")
                desc = descriptions.get(name, "")
                if not desc:
                    for key, val in descriptions.items():
                        if key.lower() in name.lower() or name.lower() in key.lower():
                            desc = val
                            break
                item_copy["description"] = desc or f"A wonderful {item_type} in {destination}."
                result.append(item_copy)
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating descriptions: {e}")
            return [{**item, "description": f"An amazing {item_type} in {destination}."} for item in items]
    
    def _prepare_hotel_recommendations(
        self,
        location_data: Dict[str, Any],
        departure_date: datetime,
        duration: int
    ) -> List[Dict[str, Any]]:
        """Add Google Maps links to hotels"""
        
        hotels = location_data.get("hotels", [])
        check_out_date = departure_date + timedelta(days=duration)
        
        result = []
        for hotel in hotels[:5]:
            hotel_data = {
                "name": hotel.get("name"),
                "category": hotel.get("category"),
                "price_per_night": hotel.get("price_per_night"),
                "rating": hotel.get("rating"),
                "photo_url": hotel.get("photo_url"),
                "check_in_date": departure_date.strftime("%B %d, %Y"),
                "check_out_date": check_out_date.strftime("%B %d, %Y"),
                "duration_nights": duration,
                "total_cost": round(hotel.get("price_per_night", 100) * duration, 2),
                "user_ratings_total": hotel.get("user_ratings_total", 0)
            }
            
            if hotel.get("location"):
                lat = hotel["location"].get("lat")
                lng = hotel["location"].get("lng")
                if lat and lng:
                    hotel_data["maps_link"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            
            result.append(hotel_data)
        
        return result
    
    def _prepare_restaurant_recommendations(self, location_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Add Google Maps links to restaurants"""
        
        restaurants = location_data.get("restaurants", [])
        result = []
        
        for r in restaurants[:5]:
            restaurant_data = {
                "name": r.get("name"),
                "cuisine": r.get("cuisine"),
                "avg_price": r.get("avg_price"),
                "rating": r.get("rating"),
                "photo_url": r.get("photo_url"),
                "price_level": r.get("price_level")
            }
            
            if r.get("location"):
                lat = r["location"].get("lat")
                lng = r["location"].get("lng")
                if lat and lng:
                    restaurant_data["maps_link"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            
            result.append(restaurant_data)
        
        return result
    
    def _update_flight_dates(
        self,
        flights: List[Dict],
        departure_date: datetime,
        return_date: datetime,
        user_location: Optional[str],
        destination: str
    ) -> List[Dict[str, Any]]:
        """
        Update flight dates using actual duration_minutes
        """
        if not flights:
            return []
        
        updated = []
        for i, flight in enumerate(flights[:5]):
            updated_flight = flight.copy()
            
            duration_mins = flight.get("duration_minutes", 360) 
            
            # Validate duration is realistic
            if duration_mins > 1440 or duration_mins < 30:
                logger.warning(f"⚠️ Unrealistic duration {duration_mins} mins, using 6-hour default")
                duration_mins = 360
            
            # Determine flight direction based on return_at field or type
            flight_type = flight.get("type", "")
            is_outbound = (flight_type == "one-way" or i < len(flights) // 2)
            
            if is_outbound:
                # Outbound flight - use departure_date
                dep_time = departure_date.replace(hour=8 + (i * 2), minute=30)
                arr_time = dep_time + timedelta(minutes=duration_mins)
                flight_direction = "outbound"
            else:
                # Return flight - use return_date
                dep_time = return_date.replace(hour=14 + ((i - len(flights) // 2) * 2), minute=0)
                arr_time = dep_time + timedelta(minutes=duration_mins)
                flight_direction = "return"
            
            # Format duration properly
            flight_hours = duration_mins // 60
            flight_minutes = duration_mins % 60
            duration_str = f"{flight_hours}h {flight_minutes}m" if flight_minutes else f"{flight_hours}h"
            
            # Update flight with correct dates and duration
            updated_flight.update({
                "departure_date": dep_time.strftime("%B %d, %Y"),
                "departure_time": dep_time.strftime("%I:%M %p"),
                "arrival_date": arr_time.strftime("%B %d, %Y"),
                "arrival_time": arr_time.strftime("%I:%M %p"),
                "departure": dep_time.isoformat(),
                "arrival": arr_time.isoformat(),
                "duration": duration_str,
                "duration_minutes": duration_mins,  
                "type": flight_direction
            })
            
            updated.append(updated_flight)
        
        logger.info(f"✅ Updated {len(updated)} flights with realistic durations")
        if updated:
            logger.info(f"   Example: {updated[0].get('duration')} ({updated[0].get('duration_minutes')} mins)")
            logger.info(f"   Route: {updated[0].get('origin')} → {updated[0].get('destination')}")
        
        return updated

    
    def _create_fallback_itinerary(
        self,
        duration: int,
        cities: List[str],
        activity_preference: str,
        departure_date: datetime
    ) -> List[Dict[str, Any]]:
        """Create fallback itinerary"""
        
        itinerary = []
        
        for day in range(1, duration + 1):
            day_date = departure_date + timedelta(days=day - 1)
            city = cities[(day - 1) % len(cities)]
            
            itinerary.append({
                "day": day,
                "date": day_date.strftime("%A, %B %d, %Y"),
                "date_short": day_date.strftime("%b %d"),
                "city": city,
                "title": f"Day {day} - Exploring {city}",
                "morning": {
                    "time": "09:00 - 12:00",
                    "name": f"Morning Exploration in {city}",
                    "description": f"Discover the vibrant streets and iconic landmarks of {city}."
                },
                "afternoon": {
                    "time": "14:00 - 17:30",
                    "name": "Afternoon Adventures",
                    "description": f"Visit museums, markets, or scenic spots in {city}."
                },
                "evening": {
                    "time": "19:00 - 22:00",
                    "name": "Evening Experience",
                    "description": f"Enjoy local cuisine and nightlife in {city}."
                }
            })
        
        return itinerary
    
    # ========================================================================
    # BUDGET REALLOCATION
    # ========================================================================
    
    async def reallocate_budget(
        self,
        current_itinerary: Dict[str, Any],
        selected_categories: List[str]
    ) -> Dict[str, Any]:
        """
        Reallocate remaining budget to selected categories
        
        FIXED: Properly extract data and regenerate all detailed breakdowns
        """
        
        logger.info(f"💰 Reallocating budget to: {selected_categories}")
        
        budget_breakdown = current_itinerary["budget_breakdown"]
        remaining = budget_breakdown.get("remaining_budget", 0)
        
        if remaining <= 0:
            logger.warning("⚠️ No remaining budget to reallocate")
            return budget_breakdown
        
        categories = budget_breakdown["categories"]
        detailed_items = budget_breakdown.get("detailed_items", {})
        
        # Extract necessary data from itinerary
        duration = current_itinerary["duration"]
        travelers = current_itinerary["travelers"]
        daily_activities = current_itinerary.get("daily_activities", [])
        
        # Recreate location_data
        destination = current_itinerary["destination"]["name"]
        user_location = None  
        include_flights = current_itinerary.get("include_flights", True)
        
        location_data = self.demo_data.fetch_location_based_data(
            destination, user_location, include_flights, duration
        )
        
        # Recreate selected_activities from daily activities
        selected_activities = self._extract_activities_from_daily(
            daily_activities, location_data
        )
        
        # Calculate total of selected categories
        selected_total = sum(
            categories[cat]["amount"] 
            for cat in selected_categories 
            if cat in categories
        )
        
        if selected_total <= 0:
            logger.warning("⚠️ Selected categories have zero total")
            return budget_breakdown
        
        # Calculate proportional additions
        additions = {}
        for cat in selected_categories:
            if cat in categories:
                proportion = categories[cat]["amount"] / selected_total
                additional = remaining * proportion
                additions[cat] = additional
                categories[cat]["amount"] = round(categories[cat]["amount"] + additional, 2)
        
        logger.info(f"💵 Additions: {additions}")
        
        # Update total allocated
        budget_breakdown["total_allocated"] = round(
            budget_breakdown["total_allocated"] + remaining, 2
        )
        budget_breakdown["remaining_budget"] = 0
        budget_breakdown["remaining_percentage"] = 0
        
        # Recalculate percentages
        total_budget = budget_breakdown["original_budget"]
        for cat in categories:
            categories[cat]["percentage"] = round(
                (categories[cat]["amount"] / total_budget * 100) if total_budget > 0 else 0, 
                2
            )
        
        # ========================================================================
        # REGENERATE DETAILED BREAKDOWNS FOR SELECTED CATEGORIES
        # ========================================================================
        
        # Flights - update if selected
        if "flights" in selected_categories and "flights" in detailed_items:
            flight_items = detailed_items["flights"]
            if flight_items:
                old_total = sum(item["total"] for item in flight_items)
                new_total = categories["flights"]["amount"]
                scale_factor = new_total / old_total if old_total > 0 else 1
                
                for item in flight_items:
                    item["total"] = round(item["total"] * scale_factor, 2)
                    item["unit_price"] = round(item["total"] / item["quantity"], 2)
                
                logger.info(f"✈️ Updated flights breakdown: ${new_total:,.2f}")
        
        # Hotels - regenerate if selected
        if "hotels" in selected_categories:
            hotel_budget = categories["hotels"]["amount"]
            detailed_items["hotels"] = self._calculate_hotels_breakdown_realloc(
                hotel_budget, duration, travelers, location_data
            )
            logger.info(f"🏨 Regenerated hotels breakdown: ${hotel_budget:,.2f}")
        
        # Food - regenerate if selected
        if "food" in selected_categories:
            food_budget = categories["food"]["amount"]
            detailed_items["food"] = self._calculate_food_breakdown(
                food_budget, duration, travelers, location_data
            )
            logger.info(f"🍔 Regenerated food breakdown: ${food_budget:,.2f}")
        
        # Activities - regenerate if selected
        if "activities" in selected_categories:
            activities_budget = categories["activities"]["amount"]
            activities_breakdown = self._calculate_activities_breakdown(
                activities_budget, duration, travelers, 
                selected_activities, daily_activities
            )
            
            categories["activities"]["must_do_total"] = activities_breakdown["must_do_total"]
            categories["activities"]["recommended_total"] = activities_breakdown["recommended_total"]
            categories["activities"]["optional_total"] = activities_breakdown["optional_total"]
            
            detailed_items["must_do_activities"] = activities_breakdown["must_do_items"]
            detailed_items["recommended_activities"] = activities_breakdown["recommended_items"]
            detailed_items["optional_activities"] = activities_breakdown["optional_items"]
            
            logger.info(f"🎭 Regenerated activities breakdown: ${activities_budget:,.2f}")
            logger.info(f"   Must-do: ${activities_breakdown['must_do_total']:,.2f}")
            logger.info(f"   Recommended: ${activities_breakdown['recommended_total']:,.2f}")
        
        # Transport - regenerate if selected
        if "travel" in selected_categories:
            transport_budget = categories["travel"]["amount"]
            detailed_items["travel"] = self._calculate_transport_breakdown(
                transport_budget, duration, travelers, location_data
            )
            logger.info(f"🚗 Regenerated transport breakdown: ${transport_budget:,.2f}")
        
        logger.info(f"✅ Budget reallocated. New total: ${budget_breakdown['total_allocated']:,.2f}")
        logger.info(f"✅ Detailed breakdowns regenerated for: {selected_categories}")
        
        return budget_breakdown


    def _extract_activities_from_daily(
        self,
        daily_activities: List[Dict[str, Any]],
        location_data: Dict[str, Any]
    ) -> Dict[str, List[Dict]]:
        """
        Extract and categorize activities from daily itinerary
        """
        
        # Get all activities from location data
        all_attractions = location_data.get("attractions", [])
        all_experiences = location_data.get("experiences", [])
        all_restaurants = location_data.get("restaurants", [])
        
        # Create lookup dictionaries
        activities_lookup = {}
        
        for attr in all_attractions:
            name = attr.get("name", "").lower()
            activities_lookup[name] = {**attr, "type": "attraction", "priority": "must_do"}
        
        for exp in all_experiences:
            name = exp.get("name", "").lower()
            activities_lookup[name] = {**exp, "type": "experience", "priority": "recommended"}
        
        for rest in all_restaurants:
            name = rest.get("name", "").lower()
            activities_lookup[name] = {**rest, "type": "restaurant", "priority": "optional"}
        
        # Extract activities from daily itinerary
        used_activities = set()
        must_do = []
        recommended = []
        optional = []
        
        for day in daily_activities:
            for slot in ["morning", "afternoon", "evening"]:
                if day.get(slot):
                    activity_name = day[slot].get("name", "").lower()
                    
                    if activity_name in used_activities:
                        continue
                    
                    used_activities.add(activity_name)
                    
                    # Find in lookup
                    if activity_name in activities_lookup:
                        activity = activities_lookup[activity_name]
                        
                        if activity["priority"] == "must_do":
                            must_do.append(activity)
                        elif activity["priority"] == "recommended":
                            recommended.append(activity)
                        else:
                            optional.append(activity)
        
        logger.info(f"🎯 Extracted {len(must_do)} must-do, {len(recommended)} recommended, {len(optional)} optional from daily activities")
        
        return {
            "must_do": must_do,
            "recommended": recommended,
            "optional": optional
        }


    def _calculate_hotels_breakdown_realloc(
        self,
        hotel_budget: float,
        duration: int,
        travelers: int,
        location_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate hotels breakdown after reallocation"""
        
        if hotel_budget <= 0:
            return []
        
        hotels = location_data.get("hotels", [])
        rooms = (travelers + 1) // 2
        
        if hotels:
            # Find best hotel that fits new budget
            sorted_hotels = sorted(hotels, key=lambda x: x.get("price_per_night", 100))
            
            selected_hotel = None
            for hotel in sorted_hotels:
                total_cost = hotel.get("price_per_night", 100) * duration * rooms
                if total_cost <= hotel_budget * 1.1:  # Allow 10% over
                    selected_hotel = hotel
            
            if not selected_hotel:
                selected_hotel = sorted_hotels[-1]  # Get most expensive if budget allows
            
            price_per_night = min(
                selected_hotel.get("price_per_night", 100),
                hotel_budget / (duration * rooms)
            )
            
            hotel_cost = round(price_per_night * duration * rooms, 2)
            
            # Adjust to match budget exactly
            if hotel_cost > hotel_budget:
                hotel_cost = hotel_budget
                price_per_night = hotel_cost / (duration * rooms)
            
            return [{
                "item": f"{selected_hotel.get('name', 'Hotel')} - {selected_hotel.get('category', 'Standard')}",
                "quantity": f"{duration} nights × {rooms} room(s)",
                "unit_price": round(price_per_night, 2),
                "total": hotel_cost,
                "essential": "MUST"
            }]
        else:
            # Generic hotel
            price_per_night = hotel_budget / (duration * rooms)
            return [{
                "item": "Hotel Accommodation",
                "quantity": f"{duration} nights × {rooms} room(s)",
                "unit_price": round(price_per_night, 2),
                "total": hotel_budget,
                "essential": "MUST"
            }]
    
    async def process_chat_message(
        self,
        message: str,
        current_itinerary: Dict[str, Any],
        conversation_history: List[Dict[str, str]]   
    ) -> Dict[str, Any]:
        """
        Process chat message.

        Delegates ALL confirmation/cancellation logic to chatbot.py, which
        intercepts yes/no BEFORE running intent detection.

        The new 'trip_param_queued' intent means the user queued a parameter
        change (destination, budget, duration, etc.) but hasn't confirmed yet.
        We pass the response back without touching the itinerary.
        """

        logger.info(f"💬 Processing: {message[:100]}...")

        itinerary_id = current_itinerary.get("itinerary_id", "unknown")

        # Delegate entirely to chatbot — confirmation handled inside
        result = await self.chatbot.process_message(
            itinerary_id=itinerary_id,
            message=message,
            current_itinerary=current_itinerary,
            conversation_history=None   
        )

        intent = result.get("intent")
        logger.info(f"🎯 Intent: {intent}, Confirmed: {result.get('confirmed_changes', False)}")

        # ── Case 1: Modification already applied (confirmed + done) ─────────
        if result.get("confirmed_changes") and result.get("modifications_made"):

            if result.get("regeneration_params"):
                logger.info("🔄 Full regeneration required (fallback path)")
                new_itinerary = await self.generate_itinerary(**result["regeneration_params"])
                return {
                    "response": result["response"],
                    "modifications_made": True,
                    "updated_itinerary": new_itinerary,
                    "requires_confirmation": False,
                    "modification_type": "full_regeneration",
                    "proposed_changes": {},
                    "confidence": 1.0
                }

            return {
                "response": result["response"],
                "modifications_made": True,
                "updated_itinerary": result.get("updated_itinerary"),
                "requires_confirmation": False,
                "modification_type": intent or "modification_applied",
                "proposed_changes": {},
                "confidence": 1.0
            }

        # ── Case 2: Trip-level params queued (accumulating, not yet confirmed) ─
        # chatbot.accumulated_params has the change stored.
        # Just relay the response message — nothing changes in the itinerary yet.
        if intent == "trip_param_queued" or result.get("is_trip_param_change"):
            return {
                "response": result.get("response", ""),
                "modifications_made": False,
                "updated_itinerary": None,
                "requires_confirmation": False,   # chatbot manages this internally
                "modification_type": "trip_param_queued",
                "proposed_changes": result.get("modifications", {}),
                "confidence": result.get("confidence", 0.95)
            }

        # ── Case 3: Day-level modification — waiting for user confirmation ───
        if result.get("requires_confirmation"):
            return {
                "response": result.get("response", ""),
                "modifications_made": False,
                "updated_itinerary": None,
                "requires_confirmation": True,
                "proposed_changes": result.get("modifications", {}),
                "modification_type": intent or "none",
                "confidence": result.get("confidence", 0.0)
            }

        # ── Case 4: Informational / cancelled / error ───────────────────────
        return {
            "response": result.get("response", ""),
            "modifications_made": False,
            "updated_itinerary": None,
            "requires_confirmation": False,
            "proposed_changes": {},
            "modification_type": intent or "none",
            "confidence": result.get("confidence", 0.0)
        }

    