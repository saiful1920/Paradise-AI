"""
Run script for the Travel Itinerary Generator API.
"""

import sys
import os
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting Travel Itinerary Generator API...")
    print("📡 Server available at: http://0.0.0.0:8001")
    uvicorn.run(
        "src.api.main:app",   
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )