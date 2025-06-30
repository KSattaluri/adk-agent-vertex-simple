"""
Shared error handling utilities for the STAR Answer Generation system.

This module provides standardized error response generation and validation
helpers that can be used across all components of the system.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Type, Union
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

def create_error_response(
    message: str,
    error_type: str = "error",
    details: Optional[Dict[str, Any]] = None,
    status_code: Optional[int] = None,
    component: Optional[str] = None,
    return_format: str = "dict"
) -> Union[Dict[str, Any], str]:
    """
    Create a standardized error response format.
    
    Args:
        message: The error message to include
        error_type: Type of error (default: "error")
        details: Optional additional details about the error
        status_code: Optional HTTP status code
        component: Optional component name that generated the error
        return_format: Format to return - "dict" for Dict[str, Any] or "json" for JSON string
        
    Returns:
        Dictionary or JSON string with error information in structured format
    """
    try:
        # Create base error response structure
        response = {
            "type": error_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add optional fields
        if details:
            response["details"] = details
        if status_code:
            response["status_code"] = status_code
        if component:
            response["component"] = component
            
        # For UI compatibility, add standard fields expected by the frontend
        if return_format == "dict":
            # Add UI-compatible structure
            response.update({
                "error": message,  # Explicit error field for UI
                "status": f"{error_type.upper()}: {message}",
                "starAnswer": {
                    "situation": "Not provided",
                    "task": "Not provided", 
                    "action": "Not provided",
                    "result": "Not provided"
                },
                "feedback": {
                    "rating": 0.0,
                    "suggestions": []
                },
                "history": [],
                "performanceMetrics": {
                    "totalWorkflowTime": 0.0,
                    "generationTime": 0.0,
                    "critiqueTimes": [],
                    "refinementTimes": []
                }
            })
            
        # Return in requested format
        if return_format == "json":
            return json.dumps(response, indent=2)
        else:
            return response
            
    except Exception as e:
        logger.error(f"Error creating error response: {e}")
        # Ultimate fallback
        fallback_response = {
            "error": message,
            "type": error_type,
            "fallback": True
        }
        
        if return_format == "json":
            return json.dumps(fallback_response)
        else:
            return fallback_response


def create_structured_error_response(
    message: str,
    component: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a structured error response using the FinalResponse model format.
    
    This is specifically for components that need to return JSON strings
    compatible with the FinalResponse schema (like tools.py).
    
    Args:
        message: The error message
        component: Optional component name
        details: Optional error details
        
    Returns:
        JSON string with FinalResponse structure
    """
    try:
        # Import here to avoid circular imports
        from schemas import FinalResponse, ResponseMetadata, PerformanceMetrics
        
        # Create structured error response
        error_response = FinalResponse(
            metadata=ResponseMetadata(
                role="",
                industry="",
                question="",
                status=f"ERROR: {message}",
                userId=""
            ),
            iterations=[],
            performanceMetrics=PerformanceMetrics(
                totalWorkflowTime=0.0,
                generationTime=0.0
            )
        )
        
        # Add component info if provided
        if component:
            error_response.metadata.status = f"ERROR ({component}): {message}"
            
        return error_response.model_dump_json(indent=2)
        
    except Exception as e:
        logger.error(f"Error creating structured error response: {e}")
        # Fallback to simple JSON
        fallback = {
            "error": message,
            "component": component,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        return json.dumps(fallback, indent=2)


def validate_with_model(
    model_class: Type[BaseModel],
    data: Dict[str, Any],
    context: str = "data validation",
    component: str = "unknown"
) -> Tuple[Optional[BaseModel], Optional[Dict[str, Any]]]:
    """
    Validate data with a Pydantic model.
    
    Args:
        model_class: The Pydantic model class to validate against
        data: The data to validate
        context: Description of what's being validated (for logging)
        component: Component performing the validation
        
    Returns:
        Tuple of (validated_model, error_response)
        If validation succeeds, error_response is None
        If validation fails, validated_model is None
    """
    try:
        validated = model_class(**data)
        logger.debug(f"✅ {context} successful for {model_class.__name__} in {component}")
        return validated, None
        
    except ValidationError as e:
        error_msg = f"Failed {context}"
        logger.error(f"❌ {error_msg} in {component}: {e}")
        
        # Create detailed error response
        error_response = create_error_response(
            error_msg,
            details={
                "validation_errors": e.errors(),
                "model": model_class.__name__,
                "context": context
            },
            component=component,
            return_format="dict"
        )
        
        return None, error_response
        
    except Exception as e:
        error_msg = f"Unexpected error during {context}"
        logger.error(f"❌ {error_msg} in {component}: {e}")
        
        error_response = create_error_response(
            error_msg,
            details={"exception": str(e)},
            component=component,
            return_format="dict"
        )
        
        return None, error_response


def validate_with_model_json(
    model_class: Type[BaseModel],
    data: Dict[str, Any],
    context: str = "data validation",
    component: str = "unknown"
) -> Tuple[Optional[BaseModel], Optional[str]]:
    """
    Validate data with a Pydantic model, returning JSON string error.
    
    This is a convenience function for components that need JSON string errors
    (like tools.py).
    
    Args:
        model_class: The Pydantic model class to validate against
        data: The data to validate
        context: Description of what's being validated (for logging)
        component: Component performing the validation
        
    Returns:
        Tuple of (validated_model, error_json_string)
        If validation succeeds, error_json_string is None
        If validation fails, validated_model is None
    """
    validated_model, error_dict = validate_with_model(
        model_class, data, context, component
    )
    
    if error_dict:
        # Convert dict error to JSON string
        error_json = create_structured_error_response(
            error_dict["message"],
            component=component,
            details=error_dict.get("details")
        )
        return None, error_json
    else:
        return validated_model, None 