"""Utilities for preparing agent requests and session state"""
import datetime
import logging
from typing import Dict, Any, Optional

from schemas import OrchestratorInput, ResponseMetadata

logger = logging.getLogger(__name__)

def create_session_state(data, include_user_data=True, user_id=None, user_email=None, user_name=None) -> Dict[str, Any]:
    """
    Create a structured session state for the agent.
    Includes all necessary data for STAR answer generation.
    
    Args:
        data: The validated STARRequest data
        include_user_data: Whether to include user identity data
        user_id: Optional user ID
        user_email: Optional user email
        user_name: Optional user name
        
    Returns:
        Dictionary containing the session state
    """
    # Start with basic input data
    try:
        # Validate with OrchestratorInput schema
        input_data = OrchestratorInput(
            role=data.role,
            industry=data.industry,
            question=data.question,
            resume=data.resume or "",
            jobDescription=data.job_description or ""
        )
        
        # Convert to dict
        validated_data = input_data.dict()
        
        # Create structured metadata
        metadata = ResponseMetadata(
            role=data.role,
            industry=data.industry,
            question=data.question,
            resume=data.resume or "",
            jobDescription=data.job_description or "",
            status="IN_PROGRESS",
            createdAt=datetime.datetime.now().isoformat(),
            userId=user_id or ""
        )
        
        # Initialize session state with validated data
        session_state = {
            # Input data
            "role": validated_data["role"],
            "industry": validated_data["industry"],
            "question": validated_data["question"],
            "resume": validated_data["resume"],
            "jobDescription": validated_data["jobDescription"],
            
            # Processing directives
            "task": "generate_star_answer",
            "timestamp": datetime.datetime.now().isoformat(),
            
            # State management
            "final_status": "IN_PROGRESS",
            "metadata": metadata.dict()
        }
        
    except Exception as e:
        # If validation fails, fall back to unvalidated structure
        logger.warning(f"Error creating validated session state: {e}")
        session_state = {
            "role": data.role,
            "industry": data.industry,
            "question": data.question,
            "resume": data.resume or "",
            "jobDescription": data.job_description or "",
            "task": "generate_star_answer",
            "timestamp": datetime.datetime.now().isoformat(),
            "final_status": "IN_PROGRESS"
        }

    # Add user identity data if requested and available
    if include_user_data and user_id:
        session_state.update({
            "user_id": user_id,
            "user_email": user_email or '',
            "user_name": user_name or ''
        })

    return session_state