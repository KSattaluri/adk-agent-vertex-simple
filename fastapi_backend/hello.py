"""
Simple hello world endpoint for FastAPI server
"""

from fastapi import APIRouter, Depends
from .auth import get_current_user, User

router = APIRouter()

@router.get("/hello")
async def hello():
    """Simple public endpoint to check if the server is running."""
    return {"message": "Hello from FastAPI! Server is running."}

@router.get("/hello-auth")
async def hello_auth(user: User = Depends(get_current_user)):
    """Authenticated endpoint to check if auth is working."""
    return {
        "message": f"Hello, {user.name}! Your auth is working correctly.",
        "user": {
            "uid": user.uid,
            "email": user.email,
            "auth_type": user.auth_type
        }
    }