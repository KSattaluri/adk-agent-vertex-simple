"""
Authentication utilities for FastAPI implementation
"""

import os
import logging
from typing import Optional, Dict, Any

import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
firebase_initialized = False

# User model for dependency injection
class User(BaseModel):
    uid: str
    email: Optional[str] = None
    name: Optional[str] = None
    auth_type: str = "firebase"

def init_firebase():
    """Initialize Firebase Admin SDK with credentials from environment or file system."""
    global firebase_initialized

    if firebase_initialized or firebase_admin._apps:
        firebase_initialized = True
        return

    try:
        # Try credential sources in priority order
        # 1. FIREBASE_CREDENTIALS_PATH environment variable
        firebase_creds_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
        if firebase_creds_path and os.path.exists(firebase_creds_path):
            cred = credentials.Certificate(firebase_creds_path)
            firebase_admin.initialize_app(cred)
            firebase_initialized = True
            return

        # 2. Service account file in .firebase directory
        firebase_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.firebase')
        if os.path.exists(firebase_dir):
            service_account_files = [f for f in os.listdir(firebase_dir) if f.endswith('.json')]
            if service_account_files:
                service_account_path = os.path.join(firebase_dir, service_account_files[0])
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                firebase_initialized = True
                return

        # 3. Application default credentials (fallback)
        firebase_admin.initialize_app()
        firebase_initialized = True

    except Exception as e:
        logger.error(f"Firebase initialization error: {e}")
        raise

async def get_current_user(request: Request) -> User:
    """FastAPI dependency to check authentication and return current user."""
    # Add debug info
    logger.info(f"[AUTH] get_current_user called for {request.url.path}")
    logger.info(f"[AUTH] DISABLE_AUTH={os.environ.get('DISABLE_AUTH', 'Not set')}")

    # Check if authentication is disabled for development
    if os.environ.get('DISABLE_AUTH') == 'true' or os.environ.get('FLASK_ENV') == 'development':
        # Get session cookie - if there is one
        session_cookie = request.cookies.get("session")
        if session_cookie:
            # If this is a dev session from dev_auth.py, use it
            try:
                # Import only when needed to avoid circular imports
                from fastapi_backend.dev_auth import dev_sessions
                if session_cookie in dev_sessions:
                    session_data = dev_sessions[session_cookie]
                    logger.info(f"[AUTH] Using development session: {session_cookie}")
                    return User(
                        uid=session_data['user_id'],
                        email=session_data['user_email'],
                        name=session_data['user_name'],
                        auth_type='development'
                    )
            except ImportError:
                pass

        # Set a default user for development
        logger.info(f"[AUTH] Using default development user")
        return User(
            uid='dev_user_123',
            email='dev@example.com',
            name='Development User',
            auth_type='development'
        )

    # Initialize Firebase if needed
    if not firebase_initialized:
        try:
            init_firebase()
        except Exception as e:
            logger.error(f"[AUTH] Firebase initialization failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable"
            )

    # Check for session authentication (browser)
    session = request.cookies.get("session")
    if session:
        try:
            # Verify session cookie
            decoded_claims = auth.verify_session_cookie(session)
            return User(
                uid=decoded_claims['uid'],
                email=decoded_claims.get('email'),
                name=decoded_claims.get('name', decoded_claims.get('email', '').split('@')[0]),
                auth_type='firebase'
            )
        except Exception as e:
            logger.error(f"[AUTH] Session cookie verification error: {e}")
            # Fall through to token check before failing

    # Check for API authentication (token)
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        try:
            # Verify token
            decoded_token = auth.verify_id_token(auth_header.split('Bearer ')[1])
            return User(
                uid=decoded_token['uid'],
                email=decoded_token.get('email'),
                name=decoded_token.get('name', decoded_token.get('email', '').split('@')[0]),
                auth_type='firebase'
            )
        except Exception as e:
            logger.error(f"[AUTH] Token verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

    # No valid authentication found
    logger.warning(f"[AUTH] No valid authentication found")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required"
    )

async def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """Verify Firebase ID token and return decoded token. Returns None if invalid."""
    if not firebase_initialized:
        init_firebase()

    try:
        # Add clock_skew_seconds parameter to handle time synchronization issues
        return auth.verify_id_token(id_token, clock_skew_seconds=60)
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None