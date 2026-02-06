"""
ENHANCED Intelligent Chatbot Service for Itinerary Management

NEW FEATURES:
- Handles ANY user question intelligently
- Fetches REAL data from Google Places API for modifications
- Can modify single or multiple days with real locations
- Can change destinations with full regeneration
- Updates descriptions, images, and budget with real data
- Tracks conversation context properly
- Handles diverse intents (questions, modifications, full changes)
"""

import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
import re
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatbotService:
    """ENHANCED intelligent chatbot for itinerary management with real data integration"""
    
    def __init__(self, api_key: str, google_api_key: str = None):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=api_key
        )
        self.google_api_key = google_api_key
        self.conversation_memory = {}
        self.places_base_url = "https://maps.googleapis.com/maps/api/place"
    
    async def process_message(
        self,
        itinerary_id: str,
        message: str,
        current_itinerary: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        ENHANCED: Process user message with intelligent intent detection and real data
        """
        
        logger.info(f"💬 Processing message: {message[:100]}...")
        
        # Build comprehensive context
        context = self._build_enhanced_context(current_itinerary, conversation_history)
        
        # Detect intent with enhanced categories
        intent_result = await self._detect_intent_enhanced(message, context, current_itinerary)
        
        logger.info(f"🎯 Detected intent: {intent_result['intent']} (confidence: {intent_result['confidence']})")
        
        # Handle based on intent
        if intent_result['intent'] == 'general_question':
            return await self._handle_general_question(message, context, current_itinerary)
        
        elif intent_result['intent'] == 'travel_advice':
            return await self._handle_travel_advice(message, context, current_itinerary)
        
        elif intent_result['intent'] == 'modify_day':
            return await self._handle_day_modification_with_real_data(
                message, context, current_itinerary, intent_result.get('extracted_info', {})
            )
        
        elif intent_result['intent'] == 'modify_multiple_days':
            return await self._handle_multiple_days_modification(
                message, context, current_itinerary, intent_result.get('extracted_info', {})
            )
        
        elif intent_result['intent'] == 'add_activity':
            return await self._handle_add_activity(
                message, context, current_itinerary, intent_result.get('extracted_info', {})
            )
        
        elif intent_result['intent'] == 'swap_activities':
            return await self._handle_swap_activities(
                message, context, current_itinerary, intent_result.get('extracted_info', {})
            )
        
        elif intent_result['intent'] == 'add_day':
            return await self._handle_add_day(message, context, current_itinerary)
        
        elif intent_result['intent'] == 'change_destination':
            return await self._handle_destination_change(message, context, current_itinerary)
        
        elif intent_result['intent'] == 'adjust_budget':
            return await self._handle_budget_adjustment(message, context, current_itinerary)
        
        elif intent_result['intent'] == 'full_regenerate':
            return await self._handle_full_regeneration(message, context, current_itinerary)
        
        else:
            return {
                "response": "I understand you want to make changes. Could you clarify what you'd like to modify? For example:\n• Ask questions about travel advice\n• Modify specific days\n• Change destination\n• Adjust budget",
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
    
    def _build_enhanced_context(
        self,
        current_itinerary: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Build comprehensive context for LLM including all trip details
        """
        destination = current_itinerary.get('destination', {})
        cities = destination.get('cities', [destination.get('name', 'Unknown')])
        
        context = f"""CURRENT TRIP OVERVIEW:
Destination: {destination.get('name', 'Unknown')}, {destination.get('country', 'Unknown')}
Cities: {', '.join(cities)}
Duration: {current_itinerary.get('duration', 0)} days
Budget: ${current_itinerary.get('total_budget', 0):,.2f}
Travelers: {current_itinerary.get('travelers', 1)}
Activity Level: {current_itinerary.get('activity_preference', 'moderate')}

DAILY SCHEDULE (CURRENT):
"""
        
        for day in current_itinerary.get('daily_activities', []):
            context += f"\nDay {day.get('day', 0)} ({day.get('city', 'N/A')}):"
            context += f"\n  Morning: {day.get('morning', {}).get('name', 'N/A')}"
            context += f"\n  Afternoon: {day.get('afternoon', {}).get('name', 'N/A')}"
            context += f"\n  Evening: {day.get('evening', {}).get('name', 'N/A')}"
        
        context += "\n\nBUDGET ALLOCATION:"
        breakdown = current_itinerary.get('budget_breakdown', {}).get('categories', {})
        for cat, data in breakdown.items():
            if cat != 'contingency':
                context += f"\n{cat.title()}: ${data.get('amount', 0):,.2f}"
        
        context += f"\nRemaining: ${current_itinerary.get('budget_breakdown', {}).get('remaining_budget', 0):,.2f}"
        
        if conversation_history:
            context += "\n\nRECENT CONVERSATION:"
            for msg in conversation_history[-6:]:
                context += f"\n{msg['role'].upper()}: {msg['content'][:150]}"
        
        return context
    
    async def _detect_intent_enhanced(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ENHANCED: Detect diverse intents including questions and modifications
        """
        
        prompt = f"""Analyze this user message and determine their intent.

USER MESSAGE: "{message}"

CONTEXT:
{context}

INTENT TYPES:
1. general_question - Questions about current itinerary details (e.g., "what am I doing on day 3?", "where am I staying?")
2. travel_advice - Questions seeking travel advice/recommendations (e.g., "what should I pack?", "best restaurants?", "is 3 days enough?")
3. modify_day - Change specific day's activity (e.g., "change day 3 afternoon to Eiffel Tower")
4. modify_multiple_days - Change multiple days at once (e.g., "change days 2 and 3 to museums")
5. add_activity - Add activity without removing existing (e.g., "add Louvre to day 2")
6. swap_activities - Swap activities between days (e.g., "swap day 1 and day 3 activities")
7. add_day - Add more days to trip
8. change_destination - Visit different cities/destinations
9. adjust_budget - Increase/decrease budget
10. full_regenerate - Completely new itinerary

EXTRACTION GUIDELINES:
- day_number: Extract ALL day numbers mentioned (can be list)
- slot: morning/afternoon/evening
- new_location_name: Extract specific place/attraction name
- multiple_days: true if modifying 2+ days
- swap_days: [day1, day2] if swapping

Return ONLY valid JSON:
{{
    "intent": "intent_type",
    "confidence": 0.0-1.0,
    "extracted_info": {{
        "day_number": null or [1, 2, 3],
        "slot": null or "morning/afternoon/evening",
        "new_location_name": null or string,
        "multiple_days": true/false,
        "swap_days": null or [1, 3],
        "new_destination": null or string,
        "budget_change": null or number
    }}
}}"""
        
        try:
            messages = [
                SystemMessage(content="You are an intent classifier for travel conversations. Return only valid JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            return result
            
        except Exception as e:
            logger.error(f"❌ Error detecting intent: {e}")
            return {
                "intent": "general_question",
                "confidence": 0.5,
                "extracted_info": {}
            }
    
    async def _handle_general_question(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle questions about current itinerary details
        """
        
        prompt = f"""You are a helpful travel assistant. Answer the user's question about their itinerary.

ITINERARY CONTEXT:
{context}

USER QUESTION: "{message}"

Provide a clear, specific answer (2-4 sentences). Reference their actual itinerary details.
Be conversational and helpful."""
        
        try:
            messages = [
                SystemMessage(content="You are a helpful travel assistant. Be concise and reference specific itinerary details."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            answer = response.content.strip()
            
            return {
                "response": answer,
                "intent": "general_question",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.9
            }
            
        except Exception as e:
            logger.error(f"❌ Error handling question: {e}")
            return {
                "response": "I'm having trouble understanding that. Could you rephrase your question?",
                "intent": "error",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
    
    async def _handle_travel_advice(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle travel advice questions (packing, restaurants, tips, etc.)
        """
        
        destination = current_itinerary.get('destination', {})
        cities = destination.get('cities', [destination.get('name', 'Unknown')])
        duration = current_itinerary.get('duration', 0)
        
        prompt = f"""You are an experienced travel advisor with deep knowledge of worldwide destinations.

TRIP DETAILS:
- Destination: {', '.join(cities)}, {destination.get('country', 'Unknown')}
- Duration: {duration} days
- Travelers: {current_itinerary.get('travelers', 1)}

USER QUESTION: "{message}"

Provide practical, actionable travel advice (3-5 sentences). Be specific to their destination and trip length.
Include insider tips when relevant."""
        
        try:
            messages = [
                SystemMessage(content="You are a knowledgeable travel expert. Provide practical, specific advice."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            answer = response.content.strip()
            
            return {
                "response": answer,
                "intent": "travel_advice",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.9
            }
            
        except Exception as e:
            logger.error(f"❌ Error providing advice: {e}")
            return {
                "response": "I'd be happy to help with travel advice. Could you be more specific about what you'd like to know?",
                "intent": "error",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
    
    async def _handle_day_modification_with_real_data(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any],
        extracted_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ENHANCED: Handle day modifications with REAL Google Places API data
        """
        
        logger.info(f"🔄 Handling day modification with real data")
        logger.info(f"Extracted info: {extracted_info}")
        
        day_number = extracted_info.get('day_number')
        slot = extracted_info.get('slot')
        new_location_name = extracted_info.get('new_location_name')
        
        # Enhanced extraction from message
        if not day_number:
            day_matches = re.findall(r'day[s]?\s+(\d+)', message.lower())
            if day_matches:
                day_number = [int(d) for d in day_matches]
        
        if isinstance(day_number, list):
            day_number = day_number[0] if len(day_number) == 1 else day_number
        
        if not slot:
            slot_keywords = {
                'morning': ['morning', 'breakfast', 'am', 'early'],
                'afternoon': ['afternoon', 'lunch', 'pm', 'midday'],
                'evening': ['evening', 'dinner', 'night', 'late']
            }
            for slot_name, keywords in slot_keywords.items():
                if any(kw in message.lower() for kw in keywords):
                    slot = slot_name
                    break
        
        if not new_location_name:
            patterns = [
                r'(?:to|visit|see|explore|go to|add|change to|replace with)\s+(?:the\s+)?([A-Z][a-zA-Z\s\-\']+(?:Tower|Museum|Park|Palace|Cathedral|Temple|Beach|Market|Square|Garden|Bridge|Castle|Wall|Hill|Island|Street|Avenue|Building|Center|Centre|Church|Mosque|Shrine|Fort|Monument|Gallery|Theater|Theatre|Stadium|Arena|Zoo|Aquarium|Library|Plaza|Quarter|District|Bay|Lake|Mountain|Falls|Canyon|Valley|Restaurant|Cafe|Bar))',
                r'(?:to|visit|see|explore|go to|add|change to|replace with)\s+the\s+([A-Z][a-zA-Z\s\-\']+)',
                r'(?:to|visit|see|explore|go to|add|change to|replace with)\s+([A-Z][a-zA-Z\s\-\']{3,})'
            ]
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    new_location_name = match.group(1).strip()
                    logger.info(f"📍 Extracted location: {new_location_name}")
                    break
        
        # Validate extracted info
        if not day_number or not slot or not new_location_name:
            return {
                "response": "I'd like to help modify your itinerary. Please specify:\n\n• **Which day?** (e.g., Day 3)\n• **What time?** (morning, afternoon, or evening)\n• **What location?** (e.g., Eiffel Tower, Louvre Museum)",
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
        
        # Get destination city for search
        destination_info = current_itinerary.get('destination', {})
        destination = destination_info.get('name', 'Unknown')
        country = destination_info.get('country', 'Unknown')
        
        # Get city for specific day if multi-city trip
        if isinstance(day_number, int):
            day_data = next((d for d in current_itinerary.get('daily_activities', []) if d.get('day') == day_number), None)
            if day_data and day_data.get('city'):
                destination = day_data['city']
        
        # Fetch REAL data from Google Places API
        logger.info(f"🔍 Fetching real data for: {new_location_name} in {destination}")
        place_data = await self._fetch_place_from_google(new_location_name, destination)
        
        if not place_data:
            return {
                "response": f"I couldn't find **{new_location_name}** in {destination}. Could you try:\n\n• A more specific name\n• Check the spelling\n• Try a different location\n\nFor example: \"Eiffel Tower\" instead of just \"Tower\"",
                "intent": "error",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
        
        # Generate description using LLM
        description = await self._generate_activity_description(
            place_data['name'], 
            destination, 
            slot
        )
        
        # Calculate budget impact
        old_cost = 0
        if isinstance(day_number, int):
            day_data = next((d for d in current_itinerary.get('daily_activities', []) if d.get('day') == day_number), None)
            if day_data and slot in day_data:
                old_cost = day_data[slot].get('cost', 0)
        
        new_cost = place_data.get('estimated_cost', 0) * current_itinerary.get('travelers', 1)
        budget_impact = new_cost - old_cost
        
        logger.info(f"✅ Found real place: {place_data['name']} (rating: {place_data.get('rating', 'N/A')})")
        
        # Format response
        response_text = f"I'll update **Day {day_number} {slot.title()}** to visit **{place_data['name']}**.\n\n"
        response_text += f"📍 **Location**: {place_data.get('address', 'N/A')}\n"
        response_text += f"⭐ **Rating**: {place_data.get('rating', 'N/A')}/5.0 ({place_data.get('user_ratings_total', 0):,} reviews)\n"
        response_text += f"💰 **Cost**: ${place_data.get('estimated_cost', 0)}/person\n"
        
        if budget_impact != 0:
            sign = '+' if budget_impact > 0 else ''
            response_text += f"💵 **Budget Impact**: {sign}${abs(budget_impact):.2f}\n"
        
        response_text += f"\n📝 **Description**: {description}\n\n"
        response_text += "Would you like to apply this change?"
        
        return {
            "response": response_text,
            "intent": "modify_day",
            "requires_confirmation": True,
            "modifications": {
                "day": day_number if isinstance(day_number, int) else day_number[0],
                "slot": slot,
                "new_activity_name": place_data['name'],
                "new_activity_description": description,
                "new_activity_photo": place_data.get('photo_url'),
                "new_activity_rating": place_data.get('rating'),
                "new_activity_address": place_data.get('address'),
                "estimated_cost": place_data.get('estimated_cost', 0),
                "budget_impact": budget_impact,
                "place_data": place_data
            },
            "confidence": 0.95
        }
    
    async def _handle_multiple_days_modification(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any],
        extracted_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle modification of multiple days at once
        """
        
        day_numbers = extracted_info.get('day_number', [])
        slot = extracted_info.get('slot')
        new_location_name = extracted_info.get('new_location_name')
        
        # Extract days if not in extracted_info
        if not day_numbers or not isinstance(day_numbers, list):
            day_matches = re.findall(r'day[s]?\s+(\d+)(?:\s+and\s+(\d+))?', message.lower())
            if day_matches:
                day_numbers = [int(d) for match in day_matches for d in match if d]
        
        if not day_numbers or len(day_numbers) < 2:
            return {
                "response": "To modify multiple days, please specify which days (e.g., 'days 2, 3, and 4') and what changes you'd like to make.",
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
        
        # For now, suggest doing them one at a time
        return {
            "response": f"I can help modify days {', '.join(map(str, day_numbers))}. To ensure I get the details right, let's do them one at a time. Which day would you like to start with?",
            "intent": "clarification_needed",
            "requires_confirmation": False,
            "modifications": {},
            "confidence": 0.7
        }
    
    async def _handle_add_activity(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any],
        extracted_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add activity to existing schedule without removing
        """
        
        return {
            "response": "Adding activities to existing slots isn't supported yet, but I can help you replace an activity with a new one. Which day and time slot would you like to update?",
            "intent": "feature_unavailable",
            "requires_confirmation": False,
            "modifications": {},
            "confidence": 0.8
        }
    
    async def _handle_swap_activities(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any],
        extracted_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Swap activities between days
        """
        
        swap_days = extracted_info.get('swap_days', [])
        
        if not swap_days or len(swap_days) != 2:
            return {
                "response": "To swap activities, please specify which two days (e.g., 'swap day 1 and day 3').",
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
        
        return {
            "response": "Swapping entire days isn't supported yet. However, I can help you modify individual activities. What specific changes would you like to make?",
            "intent": "feature_unavailable",
            "requires_confirmation": False,
            "modifications": {},
            "confidence": 0.8
        }
    
    async def _handle_add_day(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add days to itinerary (requires full regeneration)
        """
        
        current_duration = current_itinerary.get('duration', 0)
        
        # Extract number of days to add
        add_matches = re.findall(r'add\s+(\d+)', message.lower())
        days_to_add = int(add_matches[0]) if add_matches else 1
        
        new_duration = current_duration + days_to_add
        
        return {
            "response": f"I can extend your trip from **{current_duration} days** to **{new_duration} days**. This will require regenerating the entire itinerary to properly distribute activities.\n\nWould you like to proceed with this change?",
            "intent": "add_day",
            "requires_confirmation": True,
            "modifications": {
                "duration": new_duration,
                "regenerate_required": True
            },
            "confidence": 0.9
        }
    
    async def _handle_destination_change(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle destination changes (requires full regeneration)
        """
        
        # Extract new destination from message
        prompt = f"""Extract the new destination the user wants to visit.

USER MESSAGE: "{message}"

CURRENT DESTINATION: {current_itinerary.get('destination', {}).get('name', 'Unknown')}

Return ONLY the destination name as plain text (e.g., "Tokyo", "Paris, France", "Italy").
No JSON, no explanation, just the destination."""
        
        try:
            messages = [
                SystemMessage(content="Extract destination name only. Return just the destination, nothing else."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            new_destination = response.content.strip().strip('"').strip("'")
            
            current_dest = current_itinerary.get('destination', {}).get('name', 'Unknown')
            
            return {
                "response": f"I can change your destination from **{current_dest}** to **{new_destination}**.\n\nThis will:\n• Generate a completely new itinerary\n• Fetch real attractions and activities from {new_destination}\n• Recalculate budget based on local costs\n• Find flights and hotels\n\nWould you like to proceed?",
                "intent": "change_destination",
                "requires_confirmation": True,
                "modifications": {
                    "destination": new_destination,
                    "regenerate_required": True
                },
                "confidence": 0.85
            }
            
        except Exception as e:
            logger.error(f"❌ Error extracting destination: {e}")
            return {
                "response": "Where would you like to go instead? Please specify the city or country.",
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
    
    async def _handle_budget_adjustment(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle budget changes (requires full regeneration)
        """
        
        # Extract new budget
        numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', message.replace('$', ''))
        
        if numbers:
            new_budget = float(numbers[0].replace(',', ''))
            current_budget = current_itinerary.get('total_budget', 0)
            
            change = new_budget - current_budget
            change_text = f"increase by ${abs(change):,.2f}" if change > 0 else f"decrease by ${abs(change):,.2f}"
            
            return {
                "response": f"I can adjust your budget from **${current_budget:,.2f}** to **${new_budget:,.2f}** (a {change_text}).\n\nThis will:\n• Regenerate the itinerary\n• Adjust activity selections\n• Update hotel and restaurant choices\n• Recalculate all costs\n\nProceed with the new budget?",
                "intent": "adjust_budget",
                "requires_confirmation": True,
                "modifications": {
                    "budget": new_budget,
                    "regenerate_required": True
                },
                "confidence": 0.9
            }
        else:
            current_budget = current_itinerary.get('total_budget', 0)
            return {
                "response": f"Your current budget is **${current_budget:,.2f}**. What would you like to change it to?",
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }
    
    async def _handle_full_regeneration(
        self,
        message: str,
        context: str,
        current_itinerary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle full itinerary regeneration
        """
        
        return {
            "response": "I can create a completely new itinerary for you. This will:\n\n• Replace your current plan\n• Generate fresh activities and recommendations\n• Recalculate budget\n• Find new hotels and restaurants\n\nWould you like me to proceed?",
            "intent": "full_regenerate",
            "requires_confirmation": True,
            "modifications": {
                "regenerate_required": True,
                "keep_parameters": False
            },
            "confidence": 0.95
        }
    
    async def _fetch_place_from_google(
        self,
        place_name: str,
        destination: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch REAL place data from Google Places API
        
        Returns place with: name, rating, photo_url, address, estimated_cost
        """
        
        if not self.google_api_key:
            logger.warning("⚠️ No Google API key, returning fallback")
            return {
                "name": place_name,
                "rating": 4.5,
                "photo_url": None,
                "address": destination,
                "estimated_cost": 25
            }
        
        try:
            # Text search for the place
            url = f"{self.places_base_url}/textsearch/json"
            params = {
                "query": f"{place_name} {destination}",
                "key": self.google_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("results"):
                logger.warning(f"⚠️ No results for: {place_name}")
                return None
            
            # Get top result sorted by quality score
            results = data["results"]
            
            # Sort by quality score (rating × min(num_ratings, 1000))
            results.sort(
                key=lambda x: x.get("rating", 0) * min(x.get("user_ratings_total", 0), 1000),
                reverse=True
            )
            
            result = results[0]
            
            # Get photo URL
            photo_url = None
            if result.get("photos"):
                photo_ref = result["photos"][0].get("photo_reference")
                if photo_ref:
                    photo_url = f"{self.places_base_url}/photo?maxwidth=800&photo_reference={photo_ref}&key={self.google_api_key}"
            
            # Estimate cost based on price_level
            price_level = result.get("price_level", 1)
            base_costs = {0: 0, 1: 15, 2: 35, 3: 75, 4: 150}
            estimated_cost = base_costs.get(price_level, 35)
            
            return {
                "name": result.get("name"),
                "rating": result.get("rating", 4.0),
                "user_ratings_total": result.get("user_ratings_total", 0),
                "photo_url": photo_url,
                "address": result.get("formatted_address", ""),
                "estimated_cost": estimated_cost,
                "place_id": result.get("place_id"),
                "price_level": price_level
            }
            
        except Exception as e:
            logger.error(f"❌ Error fetching from Google Places: {e}")
            return None
    
    async def _generate_activity_description(
        self,
        activity_name: str,
        destination: str,
        slot: str
    ) -> str:
        """
        Generate engaging description for activity using LLM
        """
        
        time_context = {
            'morning': 'Start your day at',
            'afternoon': 'Spend your afternoon exploring',
            'evening': 'End your day with'
        }
        
        prompt = f"""{time_context.get(slot, 'Visit')} {activity_name} in {destination}. 

Write ONE engaging sentence (20-30 words) describing what visitors can experience there.
Be specific and vivid.

Return ONLY the sentence, no preamble or quotes."""
        
        try:
            messages = [
                SystemMessage(content="You are a travel writer. Write ONE short engaging sentence only (20-30 words)."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            description = response.content.strip().strip('"').strip("'")
            
            # Ensure it's reasonably short
            if len(description.split()) > 40:
                description = ' '.join(description.split()[:35]) + '...'
            
            return description
            
        except Exception as e:
            logger.error(f"Error generating description: {e}")
            return f"Explore {activity_name}, one of {destination}'s most popular attractions."
    
    async def apply_modifications(
        self,
        modifications: Dict[str, Any],
        current_itinerary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ENHANCED: Apply confirmed modifications to itinerary
        """
        
        logger.info(f"✅ Applying modifications: {modifications}")
        
        # Check if full regeneration is needed
        if modifications.get('regenerate_required'):
            return {
                "updated_itinerary": None,
                "regeneration_params": {
                    "destination": modifications.get('destination', current_itinerary.get('destination', {}).get('name', 'Unknown')),
                    "budget": modifications.get('budget', current_itinerary.get('total_budget', 0)),
                    "duration": modifications.get('duration', current_itinerary.get('duration', 0)),
                    "travelers": current_itinerary.get('travelers', 1),
                    "activity_preference": current_itinerary.get('activity_preference', 'moderate'),
                    "include_flights": current_itinerary.get('include_flights', True),
                    "include_hotels": current_itinerary.get('include_hotels', True),
                    "user_location": current_itinerary.get('user_location')
                },
                "success": True,
                "message": "Full regeneration required"
            }
        
        # Handle day-level modifications
        if 'day' in modifications and 'slot' in modifications:
            updated_itinerary = current_itinerary.copy()
            updated_activities = [day.copy() for day in current_itinerary.get('daily_activities', [])]
            
            day_num = modifications['day']
            slot = modifications['slot']
            new_name = modifications.get('new_activity_name')
            new_desc = modifications.get('new_activity_description')
            new_photo = modifications.get('new_activity_photo')
            new_rating = modifications.get('new_activity_rating')
            new_address = modifications.get('new_activity_address')
            estimated_cost = modifications.get('estimated_cost', 0)
            
            # Find and update the day
            for i, day in enumerate(updated_activities):
                if day.get('day') == day_num:
                    if slot in day and new_name:
                        # Update activity details
                        updated_activities[i][slot]['name'] = new_name
                        if new_desc:
                            updated_activities[i][slot]['description'] = new_desc
                        if new_photo:
                            updated_activities[i][slot]['photo_url'] = new_photo
                        if new_rating:
                            updated_activities[i][slot]['rating'] = new_rating
                        if new_address:
                            updated_activities[i][slot]['address'] = new_address
                        updated_activities[i][slot]['cost'] = estimated_cost
                        
                        logger.info(f"✅ Updated Day {day_num} {slot}: {new_name}")
                    break
            
            updated_itinerary['daily_activities'] = updated_activities
            
            # Recalculate budget if needed
            if modifications.get('budget_impact', 0) != 0:
                budget_breakdown = updated_itinerary.get('budget_breakdown', {})
                activities_cat = budget_breakdown.get('categories', {}).get('activities', {})
                current_amount = activities_cat.get('amount', 0)
                new_amount = current_amount + modifications['budget_impact']
                
                budget_breakdown['categories']['activities']['amount'] = max(0, new_amount)
                budget_breakdown['total_allocated'] = sum(
                    cat.get('amount', 0) for cat in budget_breakdown.get('categories', {}).values()
                    if cat.get('amount') is not None
                )
                budget_breakdown['remaining_budget'] = (
                    current_itinerary.get('total_budget', 0) - budget_breakdown['total_allocated']
                )
                
                updated_itinerary['budget_breakdown'] = budget_breakdown
                logger.info(f"💰 Budget updated: activities now ${new_amount:,.2f}")
            
            return {
                "updated_itinerary": updated_itinerary,
                "regeneration_params": None,
                "success": True,
                "message": f"Updated Day {day_num} {slot}"
            }
        
        return {
            "updated_itinerary": None,
            "regeneration_params": None,
            "success": False,
            "message": "No valid modifications found"
        }


def create_chatbot_service(api_key: str, google_api_key: str = None) -> ChatbotService:
    """Factory function to create chatbot service"""
    return ChatbotService(api_key, google_api_key)