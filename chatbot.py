import json
import logging
from typing import List, Dict, Optional, Any
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
import re
import requests
from datetime import datetime
from sqlalchemy import select, delete
from database import AsyncSessionLocal
from models import ChatMessage, PendingModification, AccumulatedParams

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRIP_PARAM_KEYS = {"destination", "budget", "duration", "travelers", "activity_preference",
                   "include_flights", "include_hotels"}

PARAM_LABELS = {
    "destination": "Destination",
    "budget": "Budget",
    "duration": "Duration (days)",
    "travelers": "Travelers",
    "activity_preference": "Activity level",
    "include_flights": "Include flights",
    "include_hotels": "Include hotels",
}


class ChatbotService:
    """
    Intelligent chatbot with database persistence.
    """

    def __init__(self, api_key: str, google_api_key: str = None, demo_data_manager=None):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, openai_api_key=api_key)
        self.fast_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, openai_api_key=api_key)
        self.google_api_key = google_api_key
        self.demo_data_manager = demo_data_manager
        self.itinerary_service = None

        self.places_base_url = "https://maps.googleapis.com/maps/api/place"

        # In‑memory context (still needed for quick access during a session)
        self.itinerary_context: Dict[str, Dict] = {}

    def set_itinerary_service(self, itinerary_service):
        self.itinerary_service = itinerary_service
        logger.info("✅ Chatbot linked to itinerary_service")

    # -------------------------------------------------------------------------
    # Conversation History (Database)
    # -------------------------------------------------------------------------
    async def get_conversation_history(self, itinerary_id: str) -> List[Dict]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.itinerary_id == itinerary_id)
                .order_by(ChatMessage.timestamp)
                .limit(20)
            )
            messages = result.scalars().all()
            return [{"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()} for m in messages]

    async def add_to_history(self, itinerary_id: str, role: str, content: str):
        async with AsyncSessionLocal() as db:
            msg = ChatMessage(
                itinerary_id=itinerary_id,
                role=role,
                content=content
            )
            db.add(msg)
            await db.commit()

    # -------------------------------------------------------------------------
    # Itinerary Context (in‑memory for speed)
    # -------------------------------------------------------------------------
    def update_context(self, itinerary_id: str, current_itinerary: Dict):
        dest = current_itinerary.get("destination", {})
        self.itinerary_context[itinerary_id] = {
            "destination": dest.get("name", "Unknown"),
            "budget": current_itinerary.get("total_budget", 0),
            "duration": current_itinerary.get("duration", 0),
            "travelers": current_itinerary.get("travelers", 1),
            "activity_preference": current_itinerary.get("activity_preference", "moderate"),
            "cities": dest.get("cities", []),
            "include_flights": current_itinerary.get("include_flights", False),
            "include_hotels": current_itinerary.get("include_hotels", False),
            "user_location": current_itinerary.get("user_location"),
            "last_updated": datetime.now().isoformat()
        }

    # -------------------------------------------------------------------------
    # Pending Day‑Level Modifications (Database)
    # -------------------------------------------------------------------------
    async def store_pending_modification(self, itinerary_id: str, modifications: Dict, summary: str):
        async with AsyncSessionLocal() as db:
            # Check if exists
            stmt = select(PendingModification).where(PendingModification.itinerary_id == itinerary_id)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.modifications = modifications
                existing.summary = summary
            else:
                pending = PendingModification(
                    itinerary_id=itinerary_id,
                    modifications=modifications,
                    summary=summary
                )
                db.add(pending)
            await db.commit()

    async def get_pending_modification(self, itinerary_id: str) -> Optional[Dict]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PendingModification).where(PendingModification.itinerary_id == itinerary_id)
            )
            pending = result.scalar_one_or_none()
            if pending:
                return {
                    "modifications": pending.modifications,
                    "summary": pending.summary,
                    "timestamp": pending.created_at.isoformat() if pending.created_at else None
                }
            return None

    async def clear_pending_modification(self, itinerary_id: str):
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(PendingModification).where(PendingModification.itinerary_id == itinerary_id)
            )
            await db.commit()

    # -------------------------------------------------------------------------
    # Accumulated Trip‑Level Parameters (Database)
    # -------------------------------------------------------------------------
    async def accumulate_param(self, itinerary_id: str, key: str, value):
        async with AsyncSessionLocal() as db:
            stmt = select(AccumulatedParams).where(AccumulatedParams.itinerary_id == itinerary_id)
            result = await db.execute(stmt)
            acc = result.scalar_one_or_none()
            if acc:
                # Create a copy of the existing params to ensure SQLAlchemy detects the change
                params = acc.params.copy() if acc.params else {}
                params[key] = value
                acc.params = params
            else:
                acc = AccumulatedParams(
                    itinerary_id=itinerary_id,
                    params={key: value}
                )
                db.add(acc)
            await db.commit()

    async def get_accumulated_params(self, itinerary_id: str) -> Dict:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AccumulatedParams).where(AccumulatedParams.itinerary_id == itinerary_id)
            )
            acc = result.scalar_one_or_none()
            return acc.params.copy() if acc and acc.params else {}

    async def clear_accumulated_params(self, itinerary_id: str):
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(AccumulatedParams).where(AccumulatedParams.itinerary_id == itinerary_id)
            )
            await db.commit()

    # -------------------------------------------------------------------------
    # Helper: format accumulated summary (uses context)
    # -------------------------------------------------------------------------
    def _format_accumulated_summary(self, itinerary_id: str, current_itinerary: Dict) -> str:
        # This method is called from async context, but it's synchronous because it only reads from memory.
        params = self.accumulated_params.get(itinerary_id, {})  # Wait, we changed to DB, so we need to get from DB.
        # Actually we need to get params from DB. But _format_accumulated_summary is called from _handle_trip_param_change,
        # which already has the accumulated params (it calls get_accumulated_params and passes them). So we can change signature.
        # However, to keep changes minimal, we'll keep this method synchronous and pass params as argument.
        # We'll modify the calling code to pass params. See below.
        pass

    # We'll rewrite _handle_trip_param_change to use the database version.

    # -------------------------------------------------------------------------
    # Confirmation / Cancellation Detection (unchanged)
    # -------------------------------------------------------------------------
    def _is_confirmation(self, message: str) -> bool:
        confirmations = {
            "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm",
            "apply", "go ahead", "do it", "proceed", "please", "yes please",
            "sounds good", "great", "perfect", "absolutely", "definitely",
            "correct", "right", "agreed", "approved"
        }
        # Normalize: lowercase, strip leading/trailing spaces, remove trailing punctuation
        msg = message.lower().strip().rstrip(".!?,")
        return msg in confirmations

    def _is_cancellation(self, message: str) -> bool:
        cancellations = {
            "no", "nope", "cancel", "nevermind", "never mind", "stop",
            "don't", "do not", "skip", "ignore", "abort", "forget it",
            "forget that", "discard"
        }
        msg = message.lower().strip().rstrip(".!?,")
        return msg in cancellations

    # -------------------------------------------------------------------------
    # Main Entry Point (updated to use async DB methods)
    # -------------------------------------------------------------------------
    async def process_message(
        self,
        itinerary_id: str,
        message: str,
        current_itinerary: Dict,
        conversation_history=None   # kept for compatibility, ignored
    ) -> Dict:
        logger.info(f"💬 [{itinerary_id}] Processing: {message[:100]}...")
        self.update_context(itinerary_id, current_itinerary)
        await self.add_to_history(itinerary_id, "user", message)

        # STEP 1: Check pending day-level modification
        pending_day = await self.get_pending_modification(itinerary_id)
        if pending_day:
            if self._is_confirmation(message):
                logger.info("✅ Confirmed pending day-modification")
                result = await self._apply_pending_modification(
                    itinerary_id, pending_day, current_itinerary
                )
                await self.add_to_history(itinerary_id, "assistant", result.get("response", ""))
                return result

            if self._is_cancellation(message):
                logger.info("❌ Cancelled pending day-modification")
                await self.clear_pending_modification(itinerary_id)
                response = ("No problem! That change has been cancelled. "
                            "Is there anything else I can help you with?")
                await self.add_to_history(itinerary_id, "assistant", response)
                return {
                    "response": response, "intent": "cancelled",
                    "requires_confirmation": False, "modifications": {}, "confidence": 1.0
                }

        # STEP 2: Check pending accumulated trip-level parameters
        accumulated = await self.get_accumulated_params(itinerary_id)
        if accumulated:
            if self._is_confirmation(message):
                logger.info(f"✅ Confirmed accumulated params: {accumulated}")
                result = await self._apply_accumulated_params(
                    itinerary_id, accumulated, current_itinerary
                )
                await self.add_to_history(itinerary_id, "assistant", result.get("response", ""))
                return result

            if self._is_cancellation(message):
                logger.info("❌ Cancelled accumulated params")
                await self.clear_accumulated_params(itinerary_id)
                response = ("Got it — all pending changes have been discarded. "
                            "Your itinerary stays as-is. What else can I help you with?")
                await self.add_to_history(itinerary_id, "assistant", response)
                return {
                    "response": response, "intent": "cancelled",
                    "requires_confirmation": False, "modifications": {}, "confidence": 1.0
                }

            # User continues to add changes while queue not empty
            history = await self.get_conversation_history(itinerary_id)
            context = self._build_enhanced_context(current_itinerary, history)
            intent_result = await self._detect_intent_enhanced(message, context, current_itinerary)

            trip_param_intents = {
                "change_destination", "adjust_budget", "add_day",
                "change_travelers", "change_activity_pref", "change_flights", "change_hotels"
            }
            if intent_result["intent"] in trip_param_intents:
                response_data = await self._handle_trip_param_change(
                    message, context, current_itinerary,
                    intent_result.get("extracted_info", {}), itinerary_id
                )
                await self.add_to_history(itinerary_id, "assistant", response_data.get("response", ""))
                return response_data

            response_data = await self._route_intent(
                intent_result, message, context, current_itinerary, itinerary_id
            )
            if (response_data.get("requires_confirmation") and
                    response_data.get("modifications") and
                    not response_data.get("is_trip_param_change")):
                await self.store_pending_modification(
                    itinerary_id, response_data["modifications"], response_data.get("response", "")
                )
            await self.add_to_history(itinerary_id, "assistant", response_data.get("response", ""))
            return response_data

        # STEP 3: Normal intent detection (no pending anything)
        history = await self.get_conversation_history(itinerary_id)
        context = self._build_enhanced_context(current_itinerary, history)
        intent_result = await self._detect_intent_enhanced(message, context, current_itinerary)

        logger.info(f"🎯 Intent: {intent_result['intent']} "
                    f"(confidence: {intent_result['confidence']})")

        response_data = await self._route_intent(
            intent_result, message, context, current_itinerary, itinerary_id
        )

        # Store day-level modifications for confirmation
        if (response_data.get("requires_confirmation") and
                response_data.get("modifications") and
                not response_data.get("is_trip_param_change")):
            await self.store_pending_modification(
                itinerary_id,
                response_data["modifications"],
                response_data.get("response", "")
            )

        await self.add_to_history(itinerary_id, "assistant", response_data.get("response", ""))
        return response_data

    # -------------------------------------------------------------------------
    # Apply Helpers (unchanged logic, but now use DB)
    # -------------------------------------------------------------------------
    async def _apply_pending_modification(
        self, itinerary_id: str, pending: Dict, current_itinerary: Dict
    ) -> Dict:
        modifications = pending["modifications"]
        await self.clear_pending_modification(itinerary_id)

        result = await self.apply_modifications(modifications, current_itinerary)
        if result.get("success"):
            if "day" in modifications and "slot" in modifications:
                name = modifications.get("new_activity_name", "the new activity")
                day = modifications["day"]
                slot = modifications["slot"].title()
                response = (f"✅ Done! **Day {day} {slot}** has been updated to "
                            f"**{name}**. Your itinerary has been refreshed above.")
            else:
                response = "✅ Done! Your itinerary has been updated."

            return {
                "response": response,
                "intent": "modification_applied",
                "requires_confirmation": False,
                "modifications": modifications,
                "confirmed_changes": True,
                "modifications_made": bool(result.get("updated_itinerary")),
                "updated_itinerary": result.get("updated_itinerary"),
                "regeneration_params": result.get("regeneration_params"),
                "confidence": 1.0
            }
        else:
            return {
                "response": "❌ Sorry, I couldn't apply that change. Please try again.",
                "intent": "modification_failed",
                "requires_confirmation": False,
                "modifications": {},
                "confidence": 0.0
            }

    async def _apply_accumulated_params(
        self, itinerary_id: str, accumulated: Dict, current_itinerary: Dict
    ) -> Dict:
        # Strip internal sentinel keys
        real_changes = {k: v for k, v in accumulated.items() if not k.startswith("_")}

        ctx = self.itinerary_context.get(itinerary_id, {})
        regen_params = {
            "destination": real_changes.get("destination",
                        ctx.get("destination",
                        current_itinerary.get("destination", {}).get("name", "Unknown"))),
            "budget": real_changes.get("budget",
                    ctx.get("budget", current_itinerary.get("total_budget", 0))),
            "duration": real_changes.get("duration",
                        ctx.get("duration", current_itinerary.get("duration", 0))),
            "travelers": real_changes.get("travelers",
                        ctx.get("travelers", current_itinerary.get("travelers", 1))),
            "activity_preference": real_changes.get("activity_preference",
                                ctx.get("activity_preference",
                                current_itinerary.get("activity_preference", "moderate"))),
            "include_flights": real_changes.get("include_flights",
                            ctx.get("include_flights",
                            current_itinerary.get("include_flights", True))),
            "include_hotels": real_changes.get("include_hotels",
                            ctx.get("include_hotels",
                            current_itinerary.get("include_hotels", True))),
            "user_location": ctx.get("user_location", current_itinerary.get("user_location", "New York"))
        }

        logger.info(f"🔄 Regenerating with accumulated changes: {real_changes}")
        logger.info(f"🔄 user_location from ctx: {ctx.get('user_location')}")
        logger.info(f"🔄 user_location from current_itinerary: {current_itinerary.get('user_location')}")
        logger.info(f"🔄 Final user_location for regeneration: {regen_params['user_location']}")

        # --- Budget validation ---
        if self.itinerary_service:
            validation = await self.itinerary_service.validate_budget(
                user_location=regen_params["user_location"],
                destination=regen_params["destination"],
                budget=regen_params["budget"],
                duration=regen_params["duration"],
                travelers=regen_params["travelers"],
                include_flights=regen_params["include_flights"],
                include_hotels=regen_params["include_hotels"]
            )

            if not validation["sufficient"]:
                response = (
                    f"⚠️ The budget **${regen_params['budget']:,.0f}** is below the recommended minimum "
                    f"**${validation['minimum_budget']:,.0f}** for {regen_params['duration']} days in {regen_params['destination']}.\n\n"
                    f"Please increase your budget or adjust other parameters.\n\n"
                    f"Your current pending changes are still saved – you can modify them further."
                )
                return {
                    "response": response,
                    "intent": "budget_insufficient",
                    "requires_confirmation": False,
                    "modifications": {}, 
                    "confidence": 1.0
                }
        # --- End validation ---

        # Clear accumulated params only after validation passes
        await self.clear_accumulated_params(itinerary_id)

        if self.itinerary_service:
            try:
                new_itinerary = await self.itinerary_service.generate_itinerary(**regen_params)

                # --- NEW: Update in‑memory context with the new itinerary ---
                self.update_context(itinerary_id, new_itinerary)

                changes = []
                for key, val in real_changes.items():
                    label = PARAM_LABELS.get(key, key.title())
                    if key == "budget":
                        changes.append(f"**{label}** → ${val:,.0f}")
                    elif key == "duration":
                        changes.append(f"**{label}** → {val} days")
                    else:
                        changes.append(f"**{label}** → {val}")

                unchanged = [PARAM_LABELS.get(k, k) for k in TRIP_PARAM_KEYS if k not in real_changes]
                response = (
                    f"✅ Done! Your itinerary has been regenerated with: "
                    f"{', '.join(changes)}.\n\n"
                    f"Everything else ({', '.join(unchanged)}) remains unchanged."
                )

                return {
                    "response": response,
                    "intent": "modification_applied",
                    "requires_confirmation": False,
                    "modifications": real_changes,
                    "confirmed_changes": True,
                    "modifications_made": True,
                    "updated_itinerary": new_itinerary,
                    "regeneration_params": None,
                    "confidence": 1.0
                }
            except Exception as e:
                logger.error(f"❌ Regeneration failed: {e}")

        # Fallback (should rarely happen)
        return {
            "response": "✅ Applying your changes now...",
            "intent": "modification_applied",
            "requires_confirmation": False,
            "modifications": real_changes,
            "confirmed_changes": True,
            "modifications_made": False,
            "updated_itinerary": None,
            "regeneration_params": regen_params,
            "confidence": 1.0
        }

    # -------------------------------------------------------------------------
    # Context Builder (unchanged)
    # -------------------------------------------------------------------------
    def _build_enhanced_context(self, current_itinerary: Dict, history: List[Dict]) -> str:
        dest = current_itinerary.get("destination", {})
        cities = dest.get("cities", [dest.get("name", "Unknown")])

        ctx = f"""CURRENT TRIP:
        Destination: {dest.get('name', 'Unknown')}, {dest.get('country', 'Unknown')}
        Cities: {', '.join(cities)}
        Duration: {current_itinerary.get('duration', 0)} days
        Budget: ${current_itinerary.get('total_budget', 0):,.2f}
        Travelers: {current_itinerary.get('travelers', 1)}
        Activity level: {current_itinerary.get('activity_preference', 'moderate')}
        Flights included: {current_itinerary.get('include_flights', False)}
        Hotels included: {current_itinerary.get('include_hotels', False)}

        DAILY SCHEDULE:"""

        for day in current_itinerary.get("daily_activities", []):
            ctx += (f"\n  Day {day.get('day', '?')} ({day.get('city', '?')}): "
                    f"Morning={day.get('morning', {}).get('name', '?')} | "
                    f"Afternoon={day.get('afternoon', {}).get('name', '?')} | "
                    f"Evening={day.get('evening', {}).get('name', '?')}")

        ctx += "\n\nBUDGET:"
        breakdown = current_itinerary.get("budget_breakdown", {}).get("categories", {})
        for cat, data in breakdown.items():
            if cat != "contingency":
                ctx += f"\n  {cat.title()}: ${data.get('amount', 0):,.2f}"
        ctx += (f"\n  Remaining: "
                f"${current_itinerary.get('budget_breakdown', {}).get('remaining_budget', 0):,.2f}")

        if history:
            ctx += "\n\nRECENT MESSAGES:"
            for msg in history[-6:]:
                ctx += f"\n  {msg['role'].upper()}: {msg['content'][:150]}"

        return ctx

    # -------------------------------------------------------------------------
    # Intent Detection (unchanged)
    # -------------------------------------------------------------------------
    async def _detect_intent_enhanced(self, message: str, context: str, current_itinerary: Dict) -> Dict:
        prompt = f"""Analyze this travel chatbot message and classify the user's intent.

        USER MESSAGE: "{message}"

        CONTEXT:
        {context}

        INTENT TYPES:
        1. general_question      — asking about current itinerary details
        2. travel_advice         — seeking travel tips/recommendations
        3. modify_day            — changing a specific day's activity slot
        4. modify_multiple_days  — changing several days at once
        5. add_activity          — adding an activity without removing one
        6. swap_activities       — swapping activities between days
        7. add_day               — extending the trip length
        8. change_destination    — visiting a different destination
        9. adjust_budget         — changing the total budget
        10. change_travelers     — changing number of travelers
        11. change_activity_pref — changing activity preference/level
        12. change_flights       — toggling flight inclusion
        13. change_hotels        — toggling hotel inclusion
        14. full_regenerate      — start completely fresh

        EXTRACTION RULES:
        - day_number: int or list[int] or null
        - slot: "morning" | "afternoon" | "evening" | null
        - new_location_name: extracted place name or null
        - new_destination: extracted city/country or null
        - budget_value: new absolute budget amount (float) or null
        - budget_delta: relative change (+/-) in budget (float) or null
        - duration_value: new absolute number of days (int) or null
        - duration_delta: days to add/subtract (int) or null
        - travelers_value: new absolute traveler count (int) or null
        - activity_preference: "light"|"moderate"|"active"|"extreme" or null
        - include_flights: true|false|null
        - include_hotels: true|false|null

        Return ONLY valid JSON:
        {{
            "intent": "<intent_type>",
            "confidence": <0.0-1.0>,
            "extracted_info": {{
                "day_number": null,
                "slot": null,
                "new_location_name": null,
                "new_destination": null,
                "budget_value": null,
                "budget_delta": null,
                "duration_value": null,
                "duration_delta": null,
                "travelers_value": null,
                "activity_preference": null,
                "include_flights": null,
                "include_hotels": null
            }}
        }}"""

        try:
            messages = [
                SystemMessage(content="You classify travel chatbot intents. Return ONLY valid JSON."),
                HumanMessage(content=prompt)
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"❌ Intent detection error: {e}")
            return {"intent": "general_question", "confidence": 0.5, "extracted_info": {}}

    # -------------------------------------------------------------------------
    # Intent Router (unchanged)
    # -------------------------------------------------------------------------
    async def _route_intent(
        self, intent_result: Dict, message: str, context: str,
        current_itinerary: Dict, itinerary_id: str
    ) -> Dict:
        intent = intent_result["intent"]
        extracted = intent_result.get("extracted_info", {})

        handlers = {
            "general_question":      self._handle_general_question,
            "travel_advice":         self._handle_travel_advice,
            "modify_day":            self._handle_day_modification,
            "modify_multiple_days":  self._handle_multiple_days,
            "add_activity":          self._handle_add_activity,
            "swap_activities":       self._handle_swap_activities,
            "add_day":               self._handle_trip_param_change,
            "change_destination":    self._handle_trip_param_change,
            "adjust_budget":         self._handle_trip_param_change,
            "change_travelers":      self._handle_trip_param_change,
            "change_activity_pref":  self._handle_trip_param_change,
            "change_flights":        self._handle_trip_param_change,
            "change_hotels":         self._handle_trip_param_change,
            "full_regenerate":       self._handle_full_regeneration,
        }

        handler = handlers.get(intent, self._handle_clarification_needed)
        return await handler(message, context, current_itinerary, extracted, itinerary_id)

    # -------------------------------------------------------------------------
    # Handlers (mostly unchanged, but _handle_trip_param_change updated to use DB)
    # -------------------------------------------------------------------------
    async def _handle_general_question(
        self, message, context, current_itinerary, extracted, itinerary_id
    ) -> Dict:
        prompt = f"""You are a helpful travel assistant. Answer the user's question about their itinerary.

        ITINERARY CONTEXT:
        {context}

        USER QUESTION: "{message}"

        Answer clearly in 2-4 sentences. Reference actual names, numbers, and dates from the context. But no need to mention any remaining budget
        Be conversational and friendly."""

        try:
            resp = await self.llm.ainvoke([
                SystemMessage(content="Helpful travel assistant. Be concise and specific."),
                HumanMessage(content=prompt)
            ])
            return {
                "response": resp.content.strip(),
                "intent": "general_question",
                "requires_confirmation": False,
                "modifications": {}, "confidence": 0.9
            }
        except Exception as e:
            logger.error(f"Error in general_question: {e}")
            return self._error_response("I had trouble understanding that. Could you rephrase?")

    async def _handle_travel_advice(
        self, message, context, current_itinerary, extracted, itinerary_id
    ) -> Dict:
        dest = current_itinerary.get("destination", {})
        cities = dest.get("cities", [dest.get("name", "Unknown")])

        prompt = f"""You are an experienced travel advisor. Answer the user's travel question.

        TRIP: {', '.join(cities)}, {dest.get('country', '')}
        Duration: {current_itinerary.get('duration', 0)} days
        Budget: ${current_itinerary.get('total_budget', 0):,.2f}
        Travelers: {current_itinerary.get('travelers', 1)}

        USER QUESTION: "{message}"

        Provide practical, specific advice in 3-5 sentences. Include insider tips where relevant."""

        try:
            resp = await self.llm.ainvoke([
                SystemMessage(content="Experienced travel advisor. Practical, specific, friendly."),
                HumanMessage(content=prompt)
            ])
            return {
                "response": resp.content.strip(),
                "intent": "travel_advice",
                "requires_confirmation": False,
                "modifications": {}, "confidence": 0.9
            }
        except Exception as e:
            logger.error(f"Error in travel_advice: {e}")
            return self._error_response("I'd love to help — could you be more specific?")

    async def _handle_trip_param_change(
        self, message, context, current_itinerary, extracted, itinerary_id
    ) -> Dict:
        current_budget = current_itinerary.get("total_budget", 0)
        current_duration = current_itinerary.get("duration", 0)
        current_destination = current_itinerary.get("destination", {}).get("name", "")

        changed_this_turn = {}

        new_destination = extracted.get("new_destination")
        if not new_destination and any(
            kw in message.lower() for kw in
            ["destination", "go to", "visit", "instead of", "change to", "fly to", "travel to"]
        ):
            new_destination = await self._llm_extract_destination(
                message, current_destination
            )

        new_budget = None
        budget_value = extracted.get("budget_value")
        budget_delta = extracted.get("budget_delta")

        if budget_value is not None:
            new_budget = float(budget_value)
        elif budget_delta is not None:
            new_budget = current_budget + float(budget_delta)
        elif any(kw in message.lower() for kw in ["budget", "$", "dollar", "money", "spend"]):
            raw = await self._llm_extract_number(message, "budget in USD", current_budget)
            if raw is not None:
                if any(kw in message.lower() for kw in ["increase", "add", "more", "raise"]):
                    new_budget = current_budget + raw
                elif any(kw in message.lower() for kw in ["decrease", "reduce", "less", "cut"]):
                    new_budget = current_budget - raw
                else:
                    new_budget = raw

        new_duration = None
        duration_value = extracted.get("duration_value")
        duration_delta = extracted.get("duration_delta")

        if duration_value is not None:
            new_duration = int(duration_value)
        elif duration_delta is not None:
            new_duration = current_duration + int(duration_delta)
        elif any(kw in message.lower() for kw in ["days", "extend", "add day", "longer", "week"]):
            raw = await self._llm_extract_number(message, "number of days", current_duration)
            if raw is not None:
                if any(kw in message.lower() for kw in ["add", "more", "extend", "extra"]):
                    new_duration = current_duration + int(raw)
                else:
                    new_duration = int(raw)

        new_travelers = extracted.get("travelers_value")
        new_activity_pref = extracted.get("activity_preference")
        new_include_flights = extracted.get("include_flights")
        new_include_hotels = extracted.get("include_hotels")

        if new_destination:
            await self.accumulate_param(itinerary_id, "destination", new_destination)
            changed_this_turn["destination"] = new_destination

        if new_budget is not None and new_budget > 0:
            await self.accumulate_param(itinerary_id, "budget", round(new_budget, 2))
            changed_this_turn["budget"] = round(new_budget, 2)

        if new_duration is not None and new_duration > 0:
            await self.accumulate_param(itinerary_id, "duration", new_duration)
            changed_this_turn["duration"] = new_duration

        if new_travelers is not None:
            await self.accumulate_param(itinerary_id, "travelers", new_travelers)
            changed_this_turn["travelers"] = new_travelers

        if new_activity_pref:
            await self.accumulate_param(itinerary_id, "activity_preference", new_activity_pref)
            changed_this_turn["activity_preference"] = new_activity_pref

        if new_include_flights is not None:
            await self.accumulate_param(itinerary_id, "include_flights", new_include_flights)
            changed_this_turn["include_flights"] = new_include_flights

        if new_include_hotels is not None:
            await self.accumulate_param(itinerary_id, "include_hotels", new_include_hotels)
            changed_this_turn["include_hotels"] = new_include_hotels

        if not changed_this_turn:
            return await self._handle_clarification_needed(
                message, context, current_itinerary, extracted, itinerary_id
            )

        all_pending = await self.get_accumulated_params(itinerary_id)
        changes_summary = await self._format_accumulated_summary_db(itinerary_id, current_itinerary, all_pending)

        real_pending = {k: v for k, v in all_pending.items() if not k.startswith("_")}
        pending_count = len(real_pending)

        if pending_count == 1:
            prompt_line = "Would you like to **add more changes** or **confirm** to regenerate?"
        else:
            prompt_line = (f"You have **{pending_count} changes** queued. "
                        f"Would you like to **add more** or **confirm** to apply them all?")

        response = (
            f"Got it! Here are your queued changes:\n\n"
            f"{changes_summary}\n\n"
            f"{prompt_line}\n\n"
            f"_Type any new change (e.g. 'also extend to 7 days'), "
            f"say **confirm** to apply all, or **cancel** to discard."
        )

        return {
            "response": response,
            "intent": "trip_param_queued",
            "requires_confirmation": False,
            "is_trip_param_change": True,
            "modifications": real_pending,
            "confidence": 0.95
        }

    async def _format_accumulated_summary_db(self, itinerary_id: str, current_itinerary: Dict, params: Dict) -> str:
        if not params:
            return ""
        lines = []
        for key, new_val in params.items():
            if key.startswith("_"):
                continue
            label = PARAM_LABELS.get(key, key.title())
            # Get old value from current_itinerary
            if key == "destination":
                old_val = current_itinerary.get("destination", {}).get("name", "Unknown")
            elif key == "budget":
                old_val = current_itinerary.get("total_budget", 0)
            elif key == "duration":
                old_val = current_itinerary.get("duration", 0)
            elif key == "travelers":
                old_val = current_itinerary.get("travelers", 1)
            elif key == "activity_preference":
                old_val = current_itinerary.get("activity_preference", "moderate")
            elif key == "include_flights":
                old_val = current_itinerary.get("include_flights", False)
            elif key == "include_hotels":
                old_val = current_itinerary.get("include_hotels", False)
            else:
                old_val = current_itinerary.get(key, "—")

            if key == "budget":
                lines.append(f"  • **{label}**: ${old_val:,.0f} → **${new_val:,.0f}**")
            elif key == "duration":
                lines.append(f"  • **{label}**: {old_val} days → **{new_val} days**")
            elif key in ("include_flights", "include_hotels"):
                lines.append(f"  • **{label}**: {old_val} → **{new_val}**")
            else:
                lines.append(f"  • **{label}**: {old_val} → **{new_val}**")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Day modification handler (unchanged)
    # -------------------------------------------------------------------------
    async def _handle_day_modification(
        self, message, context, current_itinerary, extracted, itinerary_id
    ) -> Dict:
        logger.info(f"🔄 Day modification | extracted: {extracted}")

        day_number = extracted.get("day_number")
        slot = extracted.get("slot")
        new_location_name = extracted.get("new_location_name")

        if not day_number:
            m = re.search(r'day[s]?\s+(\d+)', message, re.IGNORECASE)
            if m:
                day_number = int(m.group(1))

        if not slot:
            for s, kws in {
                "morning":   ["morning", "breakfast", "early", " am "],
                "afternoon": ["afternoon", "lunch", "midday", "pm"],
                "evening":   ["evening", "dinner", "night", "late"]
            }.items():
                if any(kw in message.lower() for kw in kws):
                    slot = s
                    break

        if not new_location_name:
            new_location_name = await self._llm_extract_place_name(message)

        if not all([day_number, slot, new_location_name]):
            missing = []
            if not day_number:          missing.append("which **day** (e.g., Day 3)")
            if not slot:                missing.append("which **time slot** (morning, afternoon, or evening)")
            if not new_location_name:   missing.append("the **new activity or place**")
            return {
                "response": f"I'd love to help! Please also specify: {', '.join(missing)}.",
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {}, "confidence": 0.0
            }

        city_ctx = self._get_day_city_context(day_number, current_itinerary)
        city = city_ctx["city"]
        search_location = city_ctx["search_location"]
        lat = city_ctx["lat"]
        lng = city_ctx["lng"]
        day_data = city_ctx["day_data"]

        place_data = await self._fetch_place_from_google(
            new_location_name, search_location, lat=lat, lng=lng
        )

        if not place_data:
            return {
                "response": (
                    f"I couldn't find **{new_location_name}** in **{city}**. "
                    f"Please try:\n"
                    f"• A more specific name (e.g. 'Colosseum Rome' instead of just 'Colosseum')\n"
                    f"• Check the spelling\n"
                    f"• A nearby alternative"
                ),
                "intent": "error",
                "requires_confirmation": False,
                "modifications": {}, "confidence": 0.0
            }

        result_address = place_data.get("address", "").lower()
        city_lower = city.lower()
        country_lower = city_ctx["country"].lower()
        city_confirmed = (
            city_lower in result_address or
            country_lower in result_address or
            any(c.lower() in result_address for c in
                current_itinerary.get("destination", {}).get("cities", []))
        )
        if not city_confirmed:
            logger.warning(f"⚠️ Place address '{place_data['address']}' doesn't mention '{city}'")
            stricter_name = f"{new_location_name} {city}"
            place_data_retry = await self._fetch_place_from_google(
                stricter_name, search_location, lat=lat, lng=lng
            )
            if place_data_retry:
                place_data = place_data_retry

        description = await self._generate_activity_description(
            place_data["name"], city, slot
        )

        old_cost = (day_data or {}).get(slot, {}).get("cost", 0)
        new_cost = place_data.get("estimated_cost", 0) * current_itinerary.get("travelers", 1)
        budget_impact = new_cost - old_cost

        response = (
            f"I'll update **Day {day_number} {slot.title()}** to visit "
            f"**{place_data['name']}** in **{city}**.\n\n"
            f"📍 **Address**: {place_data.get('address', 'N/A')}\n"
            f"⭐ **Rating**: {place_data.get('rating', 'N/A')}/5.0 "
            f"({place_data.get('user_ratings_total', 0):,} reviews)\n"
            f"💰 **Cost**: ${place_data.get('estimated_cost', 0)}/person\n"
        )
        if budget_impact:
            sign = "+" if budget_impact > 0 else ""
            response += f"💵 **Budget impact**: {sign}${abs(budget_impact):.2f}\n"
        response += f"\n📝 {description}\n\nWould you like to apply this change?"

        return {
            "response": response,
            "intent": "modify_day",
            "requires_confirmation": True,
            "modifications": {
                "day": day_number, "slot": slot,
                "new_activity_name": place_data["name"],
                "new_activity_description": description,
                "new_activity_photo": place_data.get("photo_url"),
                "new_activity_rating": place_data.get("rating"),
                "new_activity_address": place_data.get("address"),
                "estimated_cost": place_data.get("estimated_cost", 0),
                "budget_impact": budget_impact,
                "place_data": place_data,
                "city": city,
            },
            "confidence": 0.95
        }

    async def _handle_multiple_days(self, message, context, current_itinerary, extracted, itinerary_id) -> Dict:
        return {
            "response": ("To keep changes accurate, let's update days one at a time. "
                         "Which day would you like to start with?"),
            "intent": "clarification_needed",
            "requires_confirmation": False,
            "modifications": {}, "confidence": 0.7
        }

    async def _handle_add_activity(self, message, context, current_itinerary, extracted, itinerary_id) -> Dict:
        return {
            "response": ("Adding to an existing slot isn't supported yet. "
                         "I can replace an activity instead — which day and time slot?"),
            "intent": "feature_unavailable",
            "requires_confirmation": False,
            "modifications": {}, "confidence": 0.8
        }

    async def _handle_swap_activities(self, message, context, current_itinerary, extracted, itinerary_id) -> Dict:
        return {
            "response": ("Swapping whole days isn't supported yet. "
                         "I can modify individual slots — what would you like to change?"),
            "intent": "feature_unavailable",
            "requires_confirmation": False,
            "modifications": {}, "confidence": 0.8
        }

    async def _handle_full_regeneration(self, message, context, current_itinerary, extracted, itinerary_id) -> Dict:
        await self.clear_accumulated_params(itinerary_id)
        await self.accumulate_param(itinerary_id, "_full_regen", True)
        return {
            "response": ("I'll create a brand-new itinerary with your current settings "
                         "(same destination, budget, duration, and travelers).\n\n"
                         "Say **confirm** to regenerate, or **cancel** to keep your current plan."),
            "intent": "full_regenerate",
            "requires_confirmation": False,
            "is_trip_param_change": True,
            "modifications": {}, "confidence": 0.95
        }

    async def _handle_clarification_needed(self, message, context, current_itinerary, extracted, itinerary_id) -> Dict:
        prompt = f"""You are a travel assistant. The user sent a message that needs clarification.

        USER MESSAGE: "{message}"
        CONTEXT (brief): {context[:400]}

        Write a friendly 1-2 sentence clarifying question. Suggest these options naturally:
        - Modify a specific day (e.g., 'change day 3 afternoon to Colosseum')
        - Change destination, budget, duration, or travelers
        - Get travel tips or advice"""

        try:
            resp = await self.llm.ainvoke([
                SystemMessage(content="Friendly travel assistant. Ask a brief clarifying question."),
                HumanMessage(content=prompt)
            ])
            return {
                "response": resp.content.strip(),
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {}, "confidence": 0.0
            }
        except Exception:
            return {
                "response": ("I'm not sure what you'd like to change. You can:\n"
                             "• Modify a day (e.g., 'change day 2 morning to Colosseum')\n"
                             "• Change destination, budget, or duration\n"
                             "• Ask for travel tips"),
                "intent": "clarification_needed",
                "requires_confirmation": False,
                "modifications": {}, "confidence": 0.0
            }

    # -------------------------------------------------------------------------
    # LLM Extraction Helpers (unchanged)
    # -------------------------------------------------------------------------
    async def _llm_extract_destination(self, message: str, current_dest: str) -> Optional[str]:
        prompt = (f"Extract the new travel destination the user wants to visit.\n"
                  f"Current destination: {current_dest}\n"
                  f"Message: \"{message}\"\n"
                  f"Return ONLY the destination name (e.g., 'New York', 'Tokyo', 'Italy'). "
                  f"Nothing else. If none found, return null.")
        try:
            resp = await self.fast_llm.ainvoke([
                SystemMessage(content="Extract destination name only. Return just the name or null."),
                HumanMessage(content=prompt)
            ])
            result = resp.content.strip().strip('"').strip("'")
            return result if result.lower() not in ("null", "none", "", current_dest.lower()) else None
        except Exception:
            return None

    async def _llm_extract_number(self, message: str, what: str, current_val) -> Optional[float]:
        prompt = (f"Extract the {what} from this message.\n"
                  f"Current value: {current_val}\n"
                  f"Message: \"{message}\"\n"
                  f"Return ONLY the numeric value (no $, no text). "
                  f"If the user says 'add $500', return 500 (the delta only, not the total). "
                  f"If you cannot find a number, return null.")
        try:
            resp = await self.fast_llm.ainvoke([
                SystemMessage(content="Extract a single number. Return only the number or null."),
                HumanMessage(content=prompt)
            ])
            text = resp.content.strip().replace(",", "").replace("$", "")
            return float(text) if text.lower() not in ("null", "none", "") else None
        except Exception:
            return None

    async def _llm_extract_place_name(self, message: str) -> Optional[str]:
        prompt = (f"Extract the name of the place or attraction the user wants to visit.\n"
                  f"Message: \"{message}\"\n"
                  f"Return ONLY the place name (e.g., 'Eiffel Tower', 'Louvre Museum'). "
                  f"Nothing else. If no specific place is mentioned, return null.")
        try:
            resp = await self.fast_llm.ainvoke([
                SystemMessage(content="Extract a place/attraction name only. Return the name or null."),
                HumanMessage(content=prompt)
            ])
            result = resp.content.strip().strip('"').strip("'")
            return result if result.lower() not in ("null", "none", "") else None
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Google Places API (unchanged)
    # -------------------------------------------------------------------------
    async def _fetch_place_from_google(
        self, place_name: str, destination: str,
        lat: Optional[float] = None, lng: Optional[float] = None,
    ) -> Optional[Dict]:
        if self.demo_data_manager and hasattr(self.demo_data_manager, "fetch_place_details"):
            try:
                data = self.demo_data_manager.fetch_place_details(place_name, destination)
                if data:
                    return data
            except Exception as e:
                logger.warning(f"⚠️ demo_data_manager fetch failed: {e}")

        if not self.google_api_key:
            return {
                "name": place_name, "rating": 4.5, "photo_url": None,
                "address": destination, "estimated_cost": 25,
                "location": {"lat": lat, "lng": lng} if lat and lng else {}
            }

        query = f"{place_name} {destination}"
        params: Dict[str, Any] = {"query": query, "key": self.google_api_key}
        if lat is not None and lng is not None:
            params["locationbias"] = f"circle:50000@{lat},{lng}"
            logger.info(f"🗺️ Location bias applied: circle:50000@{lat},{lng}")

        try:
            resp = requests.get(f"{self.places_base_url}/textsearch/json", params=params, timeout=10)
            data = resp.json()
            if data.get("status") != "OK" or not data.get("results"):
                logger.warning(f"⚠️ No Places results for query='{query}'")
                return None

            results = data["results"]
            city_name = destination.split(",")[0].strip().lower()

            def score(r: Dict) -> float:
                base = r.get("rating", 0) * min(r.get("user_ratings_total", 0), 1000)
                addr = r.get("formatted_address", "").lower()
                city_bonus = 1.2 if city_name in addr else 1.0
                return base * city_bonus

            results.sort(key=score, reverse=True)
            r = results[0]

            photo_url = None
            if r.get("photos"):
                ref = r["photos"][0].get("photo_reference")
                if ref:
                    photo_url = f"{self.places_base_url}/photo?maxwidth=800&photo_reference={ref}&key={self.google_api_key}"

            base_costs = {0: 0, 1: 15, 2: 35, 3: 75, 4: 150}
            result_loc = r.get("geometry", {}).get("location", {})

            return {
                "name": r.get("name"),
                "rating": r.get("rating", 4.0),
                "user_ratings_total": r.get("user_ratings_total", 0),
                "photo_url": photo_url,
                "address": r.get("formatted_address", ""),
                "estimated_cost": base_costs.get(r.get("price_level", 1), 35),
                "place_id": r.get("place_id"),
                "price_level": r.get("price_level", 1),
                "location": result_loc,
            }
        except Exception as e:
            logger.error(f"❌ Google Places error: {e}")
            return None

    async def _generate_activity_description(self, name: str, destination: str, slot: str) -> str:
        opening = {
            "morning": "Start your day at",
            "afternoon": "Spend your afternoon at",
            "evening": "End your day with a visit to"
        }.get(slot, "Visit")
        prompt = (f"{opening} {name} in {destination}. "
                  f"Write ONE engaging sentence (20-30 words) about what visitors experience there. "
                  f"Return ONLY the sentence — no quotes, no preamble.")
        try:
            resp = await self.fast_llm.ainvoke([
                SystemMessage(content="Travel writer. One sentence only (20-30 words)."),
                HumanMessage(content=prompt)
            ])
            desc = resp.content.strip().strip('"').strip("'")
            return " ".join(desc.split()[:35]) + ("..." if len(desc.split()) > 35 else "")
        except Exception:
            return f"Explore {name}, one of {destination}'s top attractions."

    # -------------------------------------------------------------------------
    # Day city context (unchanged)
    # -------------------------------------------------------------------------
    def _get_day_city_context(self, day_number: int, current_itinerary: Dict) -> Dict[str, Any]:
        dest_info = current_itinerary.get("destination", {})
        country = dest_info.get("country", "")
        all_cities = dest_info.get("cities", [])
        daily_activities = current_itinerary.get("daily_activities", [])
        day_data = next((d for d in daily_activities if d.get("day") == day_number), None)

        city = None
        if day_data and day_data.get("city"):
            city = day_data["city"].strip()
        if not city and day_data and day_data.get("title"):
            title = day_data["title"]
            title_clean = re.sub(r'^day\s+\d+\s*[-:]\s*', '', title, flags=re.IGNORECASE).strip()
            city_candidate = re.split(
                r'\s+(?:highlights|adventure|exploration|tour|visit|morning|exploring)',
                title_clean, maxsplit=1, flags=re.IGNORECASE
            )[0].strip()
            if city_candidate and len(city_candidate) > 2:
                city = city_candidate
        if not city and all_cities and day_data:
            for slot in ["morning", "afternoon", "evening"]:
                activity_name = (day_data.get(slot) or {}).get("name", "").lower()
                for known_city in all_cities:
                    if known_city.lower() in activity_name:
                        city = known_city
                        break
                if city:
                    break
        if not city and all_cities:
            city = all_cities[0]
        if not city:
            city = dest_info.get("name", "Unknown")

        search_location = f"{city}, {country}".strip(", ") if country else city

        lat, lng = None, None
        if day_data:
            for slot in ["morning", "afternoon", "evening"]:
                slot_data = day_data.get(slot) or {}
                loc = slot_data.get("location") or slot_data.get("place_data", {}).get("location", {})
                if isinstance(loc, dict) and loc.get("lat") and loc.get("lng"):
                    lat = loc["lat"]
                    lng = loc["lng"]
                    break

        return {
            "city": city,
            "country": country,
            "search_location": search_location,
            "lat": lat,
            "lng": lng,
            "day_data": day_data,
        }

    # -------------------------------------------------------------------------
    # Apply Modifications (unchanged)
    # -------------------------------------------------------------------------
    async def apply_modifications(self, modifications: Dict, current_itinerary: Dict) -> Dict:
        logger.info(f"✅ Applying: {list(modifications.keys())}")

        if modifications.get("regenerate_required"):
            if self.itinerary_service:
                params = {
                    "destination": modifications.get("destination",
                                   current_itinerary.get("destination", {}).get("name", "Unknown")),
                    "budget": modifications.get("budget", current_itinerary.get("total_budget", 0)),
                    "duration": modifications.get("duration", current_itinerary.get("duration", 0)),
                    "travelers": current_itinerary.get("travelers", 1),
                    "activity_preference": current_itinerary.get("activity_preference", "moderate"),
                    "include_flights": current_itinerary.get("include_flights", True),
                    "include_hotels": current_itinerary.get("include_hotels", True),
                    "user_location": current_itinerary.get("user_location")
                }
                try:
                    new_itinerary = await self.itinerary_service.generate_itinerary(**params)
                    return {"updated_itinerary": new_itinerary, "regeneration_params": None, "success": True}
                except Exception as e:
                    logger.error(f"❌ Regeneration error: {e}")
            return {
                "updated_itinerary": None,
                "regeneration_params": {
                    "destination": modifications.get("destination",
                                   current_itinerary.get("destination", {}).get("name", "Unknown")),
                    "budget": modifications.get("budget", current_itinerary.get("total_budget", 0)),
                    "duration": modifications.get("duration", current_itinerary.get("duration", 0)),
                    "travelers": current_itinerary.get("travelers", 1),
                    "activity_preference": current_itinerary.get("activity_preference", "moderate"),
                    "include_flights": current_itinerary.get("include_flights", True),
                    "include_hotels": current_itinerary.get("include_hotels", True),
                    "user_location": current_itinerary.get("user_location")
                },
                "success": True
            }

        if "day" in modifications and "slot" in modifications:
            updated = current_itinerary.copy()
            updated_activities = [d.copy() for d in current_itinerary.get("daily_activities", [])]
            day_num = modifications["day"]
            slot = modifications["slot"]

            for i, day in enumerate(updated_activities):
                if day.get("day") == day_num:
                    slot_data = dict(updated_activities[i].get(slot, {}))
                    slot_data["name"] = modifications.get("new_activity_name", slot_data.get("name"))
                    if modifications.get("new_activity_description"):
                        slot_data["description"] = modifications["new_activity_description"]
                    if modifications.get("new_activity_photo"):
                        slot_data["photo_url"] = modifications["new_activity_photo"]
                    if modifications.get("new_activity_rating"):
                        slot_data["rating"] = modifications["new_activity_rating"]
                    if modifications.get("new_activity_address"):
                        slot_data["address"] = modifications["new_activity_address"]
                    slot_data["cost"] = modifications.get("estimated_cost", 0)
                    updated_activities[i][slot] = slot_data
                    break

            updated["daily_activities"] = updated_activities

            impact = modifications.get("budget_impact", 0)
            if impact:
                breakdown = dict(updated.get("budget_breakdown", {}))
                cats = dict(breakdown.get("categories", {}))
                act = dict(cats.get("activities", {}))
                act["amount"] = max(0, act.get("amount", 0) + impact)
                cats["activities"] = act
                total = sum(c.get("amount", 0) for c in cats.values())
                breakdown["categories"] = cats
                breakdown["total_allocated"] = round(total, 2)
                breakdown["remaining_budget"] = round(
                    current_itinerary.get("total_budget", 0) - total, 2
                )
                updated["budget_breakdown"] = breakdown

            return {"updated_itinerary": updated, "regeneration_params": None, "success": True}

        return {
            "updated_itinerary": None, "regeneration_params": None,
            "success": False, "message": "No valid modifications found"
        }

    def _error_response(self, message: str) -> Dict:
        return {
            "response": message, "intent": "error",
            "requires_confirmation": False, "modifications": {}, "confidence": 0.0
        }


def create_chatbot_service(
    api_key: str, google_api_key: str = None, demo_data_manager=None
) -> ChatbotService:
    return ChatbotService(api_key, google_api_key, demo_data_manager)