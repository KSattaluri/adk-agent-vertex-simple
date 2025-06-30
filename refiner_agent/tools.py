"""
Tools for STAR Answer Generation Pipeline
"""

import json
import logging
from typing import Dict, Any, List
from google.adk.tools import ToolContext
from pydantic import ValidationError

from schemas import (
    STARResponse,
    Critique,
    IterationData,
    PerformanceMetrics,
    ResponseMetadata,
    FinalResponse
)
from shared_utils.error_utils import create_structured_error_response

logger = logging.getLogger(__name__)


def retrieve_final_output_from_state(tool_context: ToolContext) -> str:
    """
    Retrieve and format the final output for the frontend using the new structured data format.

    Returns a JSON string with metadata, iterations, and performance metrics.
    """
    logger.info("---- retrieve_final_output_from_state: ENTERED ----")

    try:
        # Get the iteration history
        full_iteration_history = tool_context.session.state.get('fullIterationHistory', [])
        logger.info(f"[TOOLS LOG] full_iteration_history received ({len(full_iteration_history)} items)")

        # Basic validation
        if not isinstance(full_iteration_history, list):
            logger.error(f"[TOOLS LOG] Invalid full_iteration_history type: {type(full_iteration_history)}")
            return create_structured_error_response(
                "Invalid history format",
                component="tools"
            )

        if not full_iteration_history:
            logger.warning("[TOOLS LOG] full_iteration_history is empty.")
            return create_structured_error_response(
                "No history found",
                component="tools"
            )

        # Prepare metadata from session state
        metadata = ResponseMetadata(
            role=tool_context.session.state.get('role', ''),
            industry=tool_context.session.state.get('industry', ''),
            question=tool_context.session.state.get('question', ''),
            resume=tool_context.session.state.get('resume', ''),
            jobDescription=tool_context.session.state.get('jobDescription', tool_context.session.state.get('job_description', '')),
            status=tool_context.session.state.get('finalStatus', 'COMPLETED'),
            userId=tool_context.session.state.get('userId', tool_context.session.state.get('user_id', ''))
        )

        # Convert history to new structured iterations
        iterations: List[IterationData] = []

        for item_from_history in full_iteration_history:
            # The orchestrator now stores items as consistent dictionaries after model_dump()
            if not isinstance(item_from_history, dict):
                logger.warning(f"[TOOLS LOG] Skipping item in history, not a dictionary: {type(item_from_history)}")
                continue

            try:
                # Since the orchestrator now creates consistent IterationData models,
                # we can directly reconstruct the model from the stored dictionary
                iteration_data = IterationData(**item_from_history)
                iterations.append(iteration_data)
                
                logger.debug(f"[TOOLS LOG] Successfully converted history item to IterationData for iteration {iteration_data.iterationNumber}")

            except (KeyError, ValueError, ValidationError) as e:
                logger.error(f"[TOOLS LOG] Error converting history item to IterationData: {e}. Item keys: {list(item_from_history.keys()) if isinstance(item_from_history, dict) else 'Not a dict'}")
                
                # Log the problematic item structure for debugging
                logger.error(f"[TOOLS LOG] Problematic item structure: {item_from_history}")
                
                # Continue processing other iterations rather than failing completely
                continue

        # Format timing data into PerformanceMetrics model
        timing_data = tool_context.session.state.get('timing_data', {})
        metrics = PerformanceMetrics(
            totalWorkflowTime=timing_data.get('total_workflow', 0.0),
            generationTime=timing_data.get('star_generator', 0.0),
            critiqueTimes=[
                timing_data.get(f'star_critique_iteration_{i}', 0.0)
                for i in range(1, len(iterations) + 1)
                if f'star_critique_iteration_{i}' in timing_data
            ],
            refinementTimes=[
                timing_data.get(f'star_refiner_iteration_{i}', 0.0)
                for i in range(1, len(iterations))
                if f'star_refiner_iteration_{i}' in timing_data
            ]
        )

        # Create and validate final response
        final_response = FinalResponse(
            metadata=metadata,
            iterations=iterations,
            performanceMetrics=metrics
        )

        # Serialize to JSON
        logger.info(f"[TOOLS LOG] Created final response with {len(iterations)} iterations")

        # Serialize to JSON using Pydantic v2
        final_json_string = final_response.model_dump_json(indent=2)

        logger.info(f"[TOOLS LOG] Returning JSON string (length: {len(final_json_string)})")

        return final_json_string

    except ValidationError as e:
        logger.error(f"[TOOLS LOG] Validation error in final response: {e}")
        return create_structured_error_response(
            f"Validation error: {str(e)}",
            component="tools",
            details={"validation_errors": e.errors() if hasattr(e, 'errors') else None}
        )
    except Exception as e:
        logger.error(f"[TOOLS LOG] Unexpected error: {e}")
        return create_structured_error_response(
            f"Unexpected error: {str(e)}",
            component="tools"
        )