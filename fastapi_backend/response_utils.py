"""Utilities for preparing UI-compatible responses from validated Pydantic models and creating standardized error responses."""
from typing import Dict, Any, Optional
import json
from datetime import datetime
from schemas import FinalResponse, ResponseMetadata, PerformanceMetrics, STARResponse, Critique, IterationData
from shared_utils.error_utils import create_error_response as shared_create_error_response

def prepare_ui_response_from_model(final_response: FinalResponse) -> Dict[str, Any]:
    """
    Prepare a UI-compatible response from a FinalResponse model.

    This function leverages our standardized Pydantic model with camelCase field names
    to create a UI-friendly response structure.

    Args:
        final_response: A validated FinalResponse Pydantic model

    Returns:
        Dictionary with standardized data structure for UI display
    """
    # Convert model to dictionary - our model uses camelCase field names
    response_dict = final_response.model_dump()
    
    # Get the best STAR answer for the UI
    best_star_answer = final_response.get_best_star_answer()
    
    # Add the best STAR answer at the top level for easy access
    if best_star_answer:
        response_dict["starAnswer"] = best_star_answer.model_dump()
    else:
        # Fallback for empty iterations
        response_dict["starAnswer"] = {
            "situation": "Not provided",
            "task": "Not provided",
            "action": "Not provided",
            "result": "Not provided"
        }
    
    # Add feedback with highest rating for UI
    highest_rating = 0.0
    suggestions = []
    if final_response.iterations:
        highest_rated = max(final_response.iterations, key=lambda x: x.critique.rating)
        highest_rating = highest_rated.critique.rating
        suggestions = highest_rated.critique.suggestions or []
    
    response_dict["feedback"] = {
        "rating": highest_rating,
        "suggestions": suggestions
    }
    
    # Add rating at top level for sorting/filtering
    response_dict["rating"] = highest_rating
    
    # Ensure top-level fields from metadata for easier access
    if hasattr(final_response, 'metadata') and final_response.metadata:
        for field in ['role', 'industry', 'question', 'status']:
            if hasattr(final_response.metadata, field):
                response_dict[field] = getattr(final_response.metadata, field)
    
    return response_dict

def create_error_response(error_message: str, status_code: str = "ERROR") -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    This function maintains backward compatibility by wrapping the shared error utility.

    Args:
        error_message: The error message to include
        status_code: The status code to use (default: "ERROR")

    Returns:
        Dictionary with error information in structured format
    """
    return shared_create_error_response(
        message=error_message,
        error_type=status_code,
        component="response_utils",
        return_format="dict"
    )