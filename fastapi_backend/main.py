"""
STAR Answer Generator FastAPI Application with Authentication
Direct replacement for Flask backend with async support
"""

import os
import json  # Make sure json is imported at the module level
import uuid
import sys
import datetime
import logging
import traceback  # Import traceback at the module level
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

import vertexai
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import auth, firestore

# Import local modules
from fastapi_backend.cloud_run_agent import CloudRunAgent

from fastapi_backend.response_utils import prepare_ui_response_from_model, create_error_response
from fastapi_backend.user_service import get_user_profile, update_last_login, store_user_response
from schemas import FinalResponse
from fastapi_backend.auth import User, get_current_user, verify_firebase_token, init_firebase

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
    ]
)
logger = logging.getLogger(__name__)

# Environment configuration loaded from .env file
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
AGENT_LOCATION = os.getenv("AGENT_LOCATION", "local").strip()
AGENT_CLOUD_RUN_URL = os.getenv("AGENT_CLOUD_RUN_URL")
SKIP_FIRESTORE = os.getenv("SKIP_FIRESTORE", "false").lower() == "true"  # Set SKIP_FIRESTORE=true to bypass Firestore

# Debug logging for environment variables
logger.info(f"Environment variables loaded:")
logger.info(f"  AGENT_LOCATION: {AGENT_LOCATION}")
logger.info(f"  AGENT_CLOUD_RUN_URL: {AGENT_CLOUD_RUN_URL}")
logger.info(f"  PROJECT_ID: {PROJECT_ID}")
logger.info(f"  LOCATION: {LOCATION}")

# Firebase configuration
FIREBASE_API_KEY = os.getenv("FIREBASE_CLIENT_API_KEY")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN", f"{PROJECT_ID}.firebaseapp.com")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", PROJECT_ID)

# Construct Firebase configuration object for client-side
FIREBASE_CONFIG = {
    "apiKey": FIREBASE_API_KEY,
    "authDomain": FIREBASE_AUTH_DOMAIN,
    "projectId": FIREBASE_PROJECT_ID,
}

if PROJECT_ID and LOCATION:
    vertexai.init(project=PROJECT_ID, location=LOCATION)

# Initialize Firebase if credentials are available
try:
    init_firebase()
except Exception as e:
    logger.warning(f"Firebase initialization failed: {e}")
    logger.warning("Authentication will not work without Firebase credentials")

# Simple request validation
class STARRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=100)
    industry: str = Field(..., min_length=2, max_length=100)
    question: str = Field(..., min_length=10)
    resume: str = Field("", description="Optional resume text", max_length=10000)
    jobDescription: str = Field("", description="Optional job description", max_length=15000)

class SessionRequest(BaseModel):
    token: Optional[str] = None
    idToken: Optional[str] = None  # Also support 'idToken' field which is used by frontend

# Define agent URL based on configuration
agent_url = None
if AGENT_LOCATION == "cloud_run":
    # Cloud Run mode - use the Cloud Run URL
    if not AGENT_CLOUD_RUN_URL:
        logger.error("AGENT_CLOUD_RUN_URL is required for cloud_run mode")
        sys.exit(1)
    agent_url = AGENT_CLOUD_RUN_URL
    logger.info(f"Using Cloud Run Agent: {agent_url}")
else:
    # Local mode - use local FastAPI server URL
    agent_url = os.environ.get("LOCAL_AGENT_URL", "http://localhost:8080")
    logger.info(f"Using Local FastAPI Agent: {agent_url}")

# Initialize the CloudRunAgent client
cloud_run_agent = CloudRunAgent(agent_url)

# Test connectivity to agent
if not cloud_run_agent.health_check():
    logger.warning(f"Agent health check failed at {agent_url} - service may not be ready")

# Create FastAPI app
app = FastAPI(title="STAR Answer Generator API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static files - use local static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

logger.info(f"Static files: {static_dir}, Templates: {templates_dir}")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup templates - use local templates
templates = Jinja2Templates(directory=templates_dir)

# Authentication Routes
@app.get('/login', response_class=HTMLResponse)
async def login(request: Request):
    """Serve the login page."""
    # Pass Firebase config to the template
    if not FIREBASE_API_KEY:
        logger.warning("FIREBASE_CLIENT_API_KEY is not set in environment variables")
        # Show a more helpful error
        return "Error: FIREBASE_CLIENT_API_KEY is not set in environment variables. Check your .env file."

    logger.debug(f"Serving login page with Firebase config: {FIREBASE_CONFIG}")

    # Use the backend templates
    return templates.TemplateResponse("login_direct.html", {
        "request": request,
        "firebase_config": FIREBASE_CONFIG
    })


@app.get('/logout', response_class=HTMLResponse)
async def logout(request: Request):
    """Log out user by clearing session and redirecting to the logout page."""
    response = templates.TemplateResponse("logout.html", {
        "request": request,
        "firebase_config": FIREBASE_CONFIG
    })
    response.delete_cookie(key="session")
    return response

@app.post('/auth/session', response_model=None)
async def create_session(request_data: SessionRequest):
    """Create a session cookie from a Firebase ID token."""
    # Support both 'token' and 'idToken' fields
    id_token = request_data.token or request_data.idToken

    if not id_token:
        logger.error("No token provided in request")
        return JSONResponse(content={'error': 'No token provided'}, status_code=400)
    try:
        # Set session expiration to 5 days
        expires_in = datetime.timedelta(days=5)
        session_cookie = auth.create_session_cookie(id_token, expires_in=expires_in)
        
        # Verify token to get user info
        decoded_token = await verify_firebase_token(id_token)
        if not decoded_token:
            return JSONResponse(content={'error': 'Invalid ID token'}, status_code=401)
            
        user_id = decoded_token['uid']
        
        # Try to update user profile and last login
        try:
            # Get or create user profile
            user_profile = get_user_profile(user_id)
            # Update last login time
            update_last_login(user_id)
            logger.debug(f"Updated profile for user: {user_id}")
        except Exception as e:
            logger.debug(f"Failed to update user profile: {e}")
            # Continue anyway - authentication succeeded
            
        response = JSONResponse(content={"status": "success", "user": {
            'uid': user_id,
            'email': decoded_token.get('email', ''),
            'displayName': decoded_token.get('name', decoded_token.get('email', '').split('@')[0])
        }})
        
        response.set_cookie(
            key="session",
            value=session_cookie,
            httponly=True,
            secure=False if os.environ.get('FLASK_ENV') == 'development' else True,
            samesite='lax'
        )
        logger.debug("Successfully created session cookie")
        return response
    except Exception as e:
        logger.error(f"Failed to create session cookie: {e}")
        return JSONResponse(content={'error': 'Failed to create session'}, status_code=401)

# Main Application Routes
@app.get('/', response_class=FileResponse)
async def serve_ui(user: User = Depends(get_current_user)):
    """Serve the HTML UI. Requires authentication."""
    logger.debug(f"serve_ui route called by user: {user.uid}")
    index_path = os.path.join(static_dir, "index.html")
    logger.info(f"Serving index file from: {index_path}")
    return FileResponse(index_path)

@app.post('/api/chat/stream')
async def chat_stream(validated_data: STARRequest, user: User = Depends(get_current_user)):
    """Process chat requests with real-time streaming updates. Requires authentication."""
    logger.debug(f"chat_stream route called for user: {user.uid} with data: {validated_data.dict()}")

    async def event_generator():
        session_id = str(uuid.uuid4())
        request_data = validated_data.model_dump()

        try:
            # Use the refactored stream_query to pass initial_state directly
            async for event in cloud_run_agent.stream_query(
                user_id=user.uid,
                session_id=session_id,
                initial_state=request_data
            ):
                if event.get('type') == 'status':
                    # Forward status updates directly to the client
                    yield f"data: {json.dumps(event)}\n\n"
                
                # The final response is no longer a special type, but the full agent output
                elif event.get('type') not in ['status', 'error'] and 'metadata' in event and 'iterations' in event:
                    try:
                        # Debug: Log what we received
                        logger.info(f"[DEBUG] Final event keys: {list(event.keys())}")
                        logger.info(f"[DEBUG] Number of iterations: {len(event.get('iterations', []))}")
                        logger.info(f"[DEBUG] Performance metrics: {event.get('performanceMetrics', {})}")
                        
                        # 1. Validate the agent's response against the FinalResponse Pydantic model
                        validated_response = FinalResponse.model_validate(event)
                        logger.info(f"Successfully validated agent response for user {user.uid}")
                        logger.info(f"[DEBUG] Validated response has {len(validated_response.iterations)} iterations")
                        logger.info(f"[DEBUG] Validated performance metrics: {validated_response.performanceMetrics.model_dump()}")

                        # 2. Convert to UI-compatible format
                        ui_response = prepare_ui_response_from_model(validated_response)
                        logger.info(f"Converted response to UI format for user {user.uid}")

                        # 3. Store the validated response in Firestore
                        if not SKIP_FIRESTORE:
                            try:
                                response_id = store_user_response(
                                    user_id=user.uid,
                                    response_data=validated_response.model_dump()
                                )
                                ui_response['id'] = response_id
                                logger.info(f"Stored response {response_id} for user {user.uid}")
                            except Exception as e:
                                logger.error(f"Failed to store response for user {user.uid}: {e}")
                                ui_response['storage_error'] = str(e)
                        
                        # 4. Send the UI-compatible response to the client
                        final_response_wrapper = {
                            'type': 'final',
                            'data': ui_response
                        }
                        yield f"data: {json.dumps(final_response_wrapper)}\n\n"
                        return  # End stream after final response

                    except ValidationError as e:
                        logger.error(f"Agent response validation failed for user {user.uid}. Error: {e}. Data: {event}")
                        error_response = create_error_response(f"Agent returned invalid data structure: {e}")
                        yield f"data: {json.dumps(error_response)}\n\n"
                        return

                elif event.get('type') == 'error':
                    # Forward error events to the client
                    yield f"data: {json.dumps(event)}\n\n"
                    return

        except Exception as e:
            logger.error(f"Stream processing error: {e}")
            logger.error(traceback.format_exc())
            error_response = create_error_response(f"Agent streaming error: {str(e)}")
            yield f"data: {json.dumps(error_response)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

@app.get('/api/history')
async def get_history(user: User = Depends(get_current_user)):
    """Get user's response history from Firestore."""
    try:
        # Get Firestore client with specific database
        current_project_id = os.environ.get('FIREBASE_PROJECT_ID', 'refiner-agent')
        db = firestore.Client(project=current_project_id, database="refiner-agent")
        logger.info(f"[DEBUG] History: Created Firestore client with database 'refiner-agent'")

        # Query by Firebase UID
        user_responses = db.collection('responses') \
            .where('userId', '==', user.uid) \
            .limit(50) \
            .get()

        # Add detailed logging
        logger.info(f"[DEBUG] History: Found {len(user_responses)} responses for authenticated user: {user.uid}")

        # If no responses found, try a wildcard query for debugging
        if len(user_responses) == 0:
            logger.info(f"[DEBUG] History: No responses found for {user.uid}, listing all document IDs for debugging")
            # List all document IDs for debugging
            all_docs = db.collection('responses').limit(10).get()
            user_ids = [doc.to_dict().get('userId', 'unknown') for doc in all_docs]
            logger.info(f"[DEBUG] History: First 10 document user IDs in collection: {user_ids}")

        # Convert to list of dictionaries with direct mapping
        response_list = []
        for doc in user_responses:
            # Get raw data from Firestore
            raw_data = doc.to_dict()

            # Create a simplified response for the history list
            history_item = {
                'id': doc.id,
                'userId': raw_data.get('userId', ''),
                'createdAt': raw_data.get('createdAt'),
            }

            # Extract role, industry, question from finalResponse.metadata
            try:
                metadata = raw_data['finalResponse']['metadata']
                history_item['role'] = metadata.get('role', 'Not specified')
                history_item['industry'] = metadata.get('industry', 'Not specified')
                history_item['question'] = metadata.get('question', 'Untitled Response')
            except (KeyError, TypeError) as e:
                logger.error(f"[ERROR] History - Missing finalResponse.metadata in doc {doc.id}: {e}")
                history_item['role'] = 'Not specified'
                history_item['industry'] = 'Not specified'
                history_item['question'] = 'Untitled Response'

            # Extract STAR answer and rating from finalResponse.iterations
            try:
                iterations = raw_data['finalResponse']['iterations']
                if iterations:
                    # Find highest rated iteration
                    highest_rated = max(iterations,
                                      key=lambda x: x.get('critique', {}).get('rating', 0.0)
                                      if isinstance(x, dict) and isinstance(x.get('critique'), dict)
                                      else 0.0)
                    
                    history_item['starAnswer'] = highest_rated.get('starAnswer', {
                        'situation': 'Not provided',
                        'task': 'Not provided',
                        'action': 'Not provided',
                        'result': 'Not provided'
                    })
                    history_item['rating'] = highest_rated.get('critique', {}).get('rating', 0.0)
                else:
                    # No iterations found
                    history_item['starAnswer'] = {
                        'situation': 'Not provided',
                        'task': 'Not provided',
                        'action': 'Not provided',
                        'result': 'Not provided'
                    }
                    history_item['rating'] = 0.0
            except (KeyError, TypeError) as e:
                logger.error(f"[ERROR] History - Missing finalResponse.iterations in doc {doc.id}: {e}")
                history_item['starAnswer'] = {
                    'situation': 'Not provided',
                    'task': 'Not provided',
                    'action': 'Not provided',
                    'result': 'Not provided'
                }
                history_item['rating'] = 0.0

            # Ensure starAnswer has all required fields
            for field in ['situation', 'task', 'action', 'result']:
                if field not in history_item['starAnswer'] or not history_item['starAnswer'][field]:
                    history_item['starAnswer'][field] = 'Not provided'

            response_list.append(history_item)

        # Sort by timestamp if available (client-side sorting)
        response_list.sort(key=lambda x: (
            x.get('createdAt', {}).get('seconds', 0)
            if isinstance(x.get('createdAt'), dict)
            else 0
        ), reverse=True)

        # Print sample of processed response
        if response_list:
            logger.info(f"[DEBUG] Sample processed history item keys: {list(response_list[0].keys())}")

        return response_list
    except Exception as e:
        import traceback
        logger.error(f"[ERROR] Error getting history: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")

@app.get('/api/responses/{response_id}')
async def get_response(response_id: str, user: User = Depends(get_current_user)):
    """Get a specific response by ID."""
    try:
        # Get Firestore client with specific database
        current_project_id = os.environ.get('FIREBASE_PROJECT_ID', 'refiner-agent')
        db = firestore.Client(project=current_project_id, database="refiner-agent")
        logger.info(f"[DEBUG] Response: Created Firestore client with database 'refiner-agent'")

        # Get the response document
        response = db.collection('responses').document(response_id).get()

        # Check if it exists
        if not response.exists:
            raise HTTPException(status_code=404, detail="Response not found")

        # Get raw data from Firestore
        raw_data = response.to_dict()
        logger.info(f"[DEBUG] Raw response keys: {list(raw_data.keys())}")

        # Check if it belongs to the authenticated user (unless in development mode)
        response_user_id = raw_data.get('userId')
        if not os.environ.get('DISABLE_AUTH') == 'true' and not os.environ.get('FLASK_ENV') == 'development':
            if response_user_id != user.uid:
                logger.debug(f"[DEBUG] Access denied: Response belongs to {response_user_id}, but requester is {user.uid}")
                raise HTTPException(status_code=403, detail="Access denied")

        # Create the basic response structure
        formatted_response = {
            'id': response.id,
            'userId': raw_data.get('userId', ''),
            'createdAt': raw_data.get('createdAt'),
        }

        # Extract role, industry, question from finalResponse.metadata
        try:
            metadata = raw_data['finalResponse']['metadata']
            formatted_response['role'] = metadata.get('role', 'Not specified')
            formatted_response['industry'] = metadata.get('industry', 'Not specified')
            formatted_response['question'] = metadata.get('question', 'Untitled Response')
        except (KeyError, TypeError) as e:
            logger.error(f"[ERROR] Response - Missing finalResponse.metadata in doc {response_id}: {e}")
            formatted_response['role'] = 'Not specified'
            formatted_response['industry'] = 'Not specified'
            formatted_response['question'] = 'Untitled Response'

        # Extract STAR answer and rating from finalResponse.iterations
        try:
            iterations = raw_data['finalResponse']['iterations']
            if iterations:
                # Find highest rated iteration
                highest_rated = max(iterations,
                                  key=lambda x: x.get('critique', {}).get('rating', 0.0)
                                  if isinstance(x, dict) and isinstance(x.get('critique'), dict)
                                  else 0.0)
                
                formatted_response['starAnswer'] = highest_rated.get('starAnswer', {
                    'situation': 'Not provided',
                    'task': 'Not provided',
                    'action': 'Not provided',
                    'result': 'Not provided'
                })
                formatted_response['rating'] = highest_rated.get('critique', {}).get('rating', 0.0)
            else:
                # No iterations found
                formatted_response['starAnswer'] = {
                    'situation': 'Not provided',
                    'task': 'Not provided',
                    'action': 'Not provided',
                    'result': 'Not provided'
                }
                formatted_response['rating'] = 0.0
        except (KeyError, TypeError) as e:
            logger.error(f"[ERROR] Response - Missing finalResponse.iterations in doc {response_id}: {e}")
            formatted_response['starAnswer'] = {
                'situation': 'Not provided',
                'task': 'Not provided',
                'action': 'Not provided',
                'result': 'Not provided'
            }
            formatted_response['rating'] = 0.0

        # Ensure all required fields are present in starAnswer
        for field in ['situation', 'task', 'action', 'result']:
            if field not in formatted_response['starAnswer'] or not formatted_response['starAnswer'][field]:
                formatted_response['starAnswer'][field] = 'Not provided'

        # Create feedback object from rating
        formatted_response['feedback'] = {
            'rating': formatted_response.get('rating', 0.0),
            'suggestions': []
        }

        # Add iteration history from finalResponse.iterations
        try:
            formatted_response['finalResponse'] = raw_data['finalResponse']
            formatted_response['history'] = raw_data['finalResponse']['iterations']
        except (KeyError, TypeError) as e:
            logger.error(f"[ERROR] Response - Missing finalResponse.iterations for history in doc {response_id}: {e}")
            # Create a single history item with the available data
            formatted_response['history'] = [{
                'iterationNumber': 1,
                'starAnswer': formatted_response['starAnswer'],
                'critique': formatted_response.get('feedback', {'rating': 0.0})
            }]

        # Validate each history item to ensure UI compatibility
        for i, item in enumerate(formatted_response['history']):
            if not isinstance(item, dict):
                logger.warning(f"[WARNING] History item {i} is not a dictionary: {item}")
                continue

            # Ensure starAnswer exists and has all required fields
            if 'starAnswer' in item and isinstance(item['starAnswer'], dict):
                for field in ['situation', 'task', 'action', 'result']:
                    if field not in item['starAnswer'] or not item['starAnswer'][field]:
                        item['starAnswer'][field] = 'Not available'
            else:
                item['starAnswer'] = {
                    'situation': 'Not available',
                    'task': 'Not available',
                    'action': 'Not available',
                    'result': 'Not available'
                }

            # Ensure critique exists
            if 'critique' not in item:
                item['critique'] = {
                    'rating': 0.0,
                    'suggestions': []
                }

        return formatted_response
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"[ERROR] Error getting response: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to retrieve response: {str(e)}")

@app.get('/api/auth-status')
async def auth_status(user: User = Depends(get_current_user)):
    """Test endpoint to check authentication status."""
    return {
        'authenticated': True,
        'user_id': user.uid,
        'user_email': user.email,
        'user_name': user.name,
        'env': {
            'DISABLE_AUTH': os.environ.get('DISABLE_AUTH', 'Not set'),
            'FLASK_ENV': os.environ.get('FLASK_ENV', 'Not set')
        }
    }

# Simple health check
@app.get('/health')
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# Import the hello router
from fastapi_backend.hello import router as hello_router

# Include the hello router
app.include_router(hello_router)

def main():
    """Entry point for poetry script."""
    import uvicorn
    port = int(os.environ.get("PORT", 5005))
    reload_enabled = os.environ.get("RELOAD", "false").lower() == "true"
    log_level = os.environ.get("LOG_LEVEL", "info").lower()

    logger.info(f"Starting FastAPI server on http://0.0.0.0:{port}")
    logger.info(f"Using backend configuration:")
    logger.info(f"  - AGENT_LOCATION: {os.environ.get('AGENT_LOCATION', 'local')}")
    logger.info(f"  - AUTO_RELOAD: {reload_enabled}")
    logger.info(f"  - LOG_LEVEL: {log_level}")

    # Run the FastAPI application using uvicorn
    uvicorn.run(
        "fastapi_backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
        log_level=log_level,
    )

# Main entry point
if __name__ == "__main__":
    main()