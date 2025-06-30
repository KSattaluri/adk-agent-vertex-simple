"""
Templates module for FastAPI implementation
"""
import os
from fastapi.templating import Jinja2Templates

# Get the absolute path to the templates directory
templates_dir = os.path.dirname(os.path.abspath(__file__))

# Create templates object
login_templates = Jinja2Templates(directory=templates_dir)