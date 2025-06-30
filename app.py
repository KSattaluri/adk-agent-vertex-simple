"""
Unified entry point for the STAR Answer Agent.
Auto-detects environment (local vs Cloud Run) and configures accordingly.
Uses ADK's FastAPI integration.
"""

import os
import sys
import uvicorn
import warnings
import logging
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

# Suppress OpenTelemetry context errors (common with ADK + Python 3.13)
warnings.filterwarnings("ignore", message=".*Failed to detach context.*")
warnings.filterwarnings("ignore", message=".*was created in a different Context.*")
logging.getLogger("opentelemetry").setLevel(logging.ERROR)

# Environment detection
IS_CLOUD_RUN = os.environ.get("K_SERVICE") is not None
ENVIRONMENT = "Cloud Run" if IS_CLOUD_RUN else "Local"

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Environment-specific configuration
if IS_CLOUD_RUN:
    # Cloud Run configuration
    PORT_ENV_VAR = "PORT"
    DEFAULT_PORT = 8080
    SESSION_DB_URL = f"sqlite:///{os.path.join(BASE_DIR, 'sessions.db')}"
    VERBOSE_LOGGING = False
    TRACE_TO_CLOUD = None  # Use ADK default for Cloud Run
else:
    # Local development configuration  
    PORT_ENV_VAR = "ADK_PORT"  # Preserve the port fix
    DEFAULT_PORT = 8080
    SESSION_DB_URL = "sqlite:///./sessions.db"
    VERBOSE_LOGGING = True
    TRACE_TO_CLOUD = False

# Common configuration
ALLOWED_ORIGINS = ["*"]
SERVE_WEB_INTERFACE = True

print(f"Environment: {ENVIRONMENT}")
print(f"ADK will scan for agent packages in: {BASE_DIR}")
print(f"Using database URL: {SESSION_DB_URL}")

# This will hold the FastAPI app instance
app: FastAPI | None = None

def create_app():
    """Create and configure the FastAPI app based on environment."""
    global app
    
    try:
        # Prepare get_fast_api_app arguments
        app_args = {
            "agents_dir": BASE_DIR,
            "session_service_uri": SESSION_DB_URL,
            "allow_origins": ALLOWED_ORIGINS,
            "web": SERVE_WEB_INTERFACE,
        }
        
        # Add trace_to_cloud only for local (preserve existing behavior)
        if TRACE_TO_CLOUD is not None:
            app_args["trace_to_cloud"] = TRACE_TO_CLOUD

        # Initialize ADK app
        app = get_fast_api_app(**app_args)
        
        success_msg = f"Successfully initialized ADK app for {ENVIRONMENT.lower()} deployment"
        print(success_msg)
        
        # Environment-specific logging
        if VERBOSE_LOGGING:
            port = int(os.environ.get(PORT_ENV_VAR, DEFAULT_PORT))
            print(f"ADK Dev UI should be available at http://localhost:{port}/dev-ui/")
            print("Registered routes:")
            for route in app.routes:
                print(f"  Path: {getattr(route, 'path', 'N/A')}, Name: {getattr(route, 'name', 'N/A')}, Methods: {getattr(route, 'methods', 'N/A')}")

        # Add health check endpoint
        @app.get("/health")
        async def health_check():
            return {
                "status": "ok", 
                "mode": f"ADK Integration ({ENVIRONMENT})",
                "environment": ENVIRONMENT
            }

    except Exception as adk_init_exception:
        adk_error_message = str(adk_init_exception)
        print(f"Error initializing ADK app: {adk_error_message}", file=sys.stderr)
        
        fallback_msg = f"Falling back to basic FastAPI app for {ENVIRONMENT.lower()} deployment"
        print(fallback_msg)
        
        # Create fallback app
        app = FastAPI(title=f"STAR Answer Agent ({ENVIRONMENT} Fallback)")

        @app.get("/health")
        async def health_check_fallback():
            return {
                "status": "ok", 
                "mode": f"Fallback ({ENVIRONMENT})", 
                "adk_error": adk_error_message,
                "environment": ENVIRONMENT
            }

        @app.get("/")
        async def root_fallback():
            return {
                "message": f"STAR Answer Agent API ({ENVIRONMENT} Fallback Mode)",
                "status": "running",
                "error": "ADK integration failed",
                "error_details": adk_error_message,
                "environment": ENVIRONMENT
            }
    
    return app

def run_server():
    """Run the server with environment-specific configuration."""
    port = int(os.environ.get(PORT_ENV_VAR, DEFAULT_PORT))

    print(f"Configuring Uvicorn server ({ENVIRONMENT}) on host 0.0.0.0, port {port}")
    print(f"Using port environment variable: {PORT_ENV_VAR}")
    print(f"Starting FastAPI server ({ENVIRONMENT}) on http://0.0.0.0:{port}")

    # Use uvicorn.run() for better signal handling and graceful shutdown.
    # The first argument "app:app" tells uvicorn to look for the object
    # named 'app' in the file named 'app.py'.
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False  # Set to True for auto-reload on code changes
    )

# Initialize the app at module level
create_app()

if __name__ == "__main__":
    run_server()