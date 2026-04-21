from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse
from src.core.config import settings

# Create limiter with Redis storage via storage_uri
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,   
    strategy="fixed-window"            
)

def rate_limit_exceeded_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )