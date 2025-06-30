import logging
import datetime
from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

from schemas import (
    IterationData,
    STARResponse,
    Critique,
    FinalResponse,
    ResponseMetadata,
    PerformanceMetrics
)

logger = logging.getLogger(__name__)

def iteration_history_callback(callback_context: CallbackContext) -> None:
    """Callback to record iteration data (STAR answer + critique) into history.
    
    This callback is attached to the LoopAgent and runs after each loop iteration completes.
    It captures both the STAR answer and critique from the completed iteration.
    """
    logger.debug(f"'iteration_history_callback' triggered during invocation: {callback_context.invocation_id}")

    # Since this callback is attached to the LoopAgent, it runs after each complete iteration
    # No need to check agent names - it will only run when both answer and critique are available

    current_star_answer_dict = callback_context.state.get("current_star_answer")
    current_critique_dict = callback_context.state.get("current_critique")

    if not isinstance(current_star_answer_dict, dict) or not isinstance(current_critique_dict, dict):
        logger.warning(
            "'iteration_history_callback': 'current_star_answer' or 'current_critique' is missing or not a dict in state. "
            "Cannot record history. Answer: %s, Critique: %s",
            type(current_star_answer_dict).__name__,
            type(current_critique_dict).__name__
        )
        return

    try:
        star_answer_obj = STARResponse(**current_star_answer_dict)
        critique_obj = Critique(**current_critique_dict)
    except Exception as e:
        logger.error(f"'iteration_history_callback': Error parsing Pydantic models from state: {e}", exc_info=True)
        return

    iteration_list = callback_context.state.get("fullIterationHistory", [])
    # Get current iteration, initialize if not present
    iteration_number = callback_context.state.get("currentIteration", 0) + 1
    callback_context.state["currentIteration"] = iteration_number 

    iteration_entry = IterationData(
        iterationNumber=iteration_number,
        starAnswer=star_answer_obj,
        critique=critique_obj,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    
    # Convert to dict for JSON serialization before storing in state
    iteration_list.append(iteration_entry.model_dump())
    callback_context.state["fullIterationHistory"] = iteration_list

    # Get highest rating, initialize if not present
    highest_rating = callback_context.state.get("highestRating", 0.0)
    new_highest_rating = max(highest_rating, critique_obj.rating)
    callback_context.state["highestRating"] = new_highest_rating

    logger.info(
        f"'iteration_history_callback': Recorded iteration {iteration_number}. "
        f"Rating: {critique_obj.rating}. Highest rating so far: {new_highest_rating}."
    )

def final_formatting_callback(callback_context: CallbackContext) -> genai_types.Content:
    """Callback to prepare the final structured response from the agent's state."""
    # Force logging at WARNING level to ensure visibility
    logger.warning(f"🔥 FINAL_FORMATTING_CALLBACK TRIGGERED for invocation: {callback_context.invocation_id}")
    print(f"🔥 FINAL_FORMATTING_CALLBACK TRIGGERED for invocation: {callback_context.invocation_id}")  # Also print to console

    full_iteration_history_raw = callback_context.state.get("fullIterationHistory", [])
    processed_history_list = []
    for item_raw in full_iteration_history_raw:
        if isinstance(item_raw, IterationData):
            # Already a validated IterationData object
            processed_history_list.append(item_raw)
        elif isinstance(item_raw, dict):
            # Convert dict to IterationData object
            try:
                processed_history_list.append(IterationData(**item_raw))
            except Exception as e:
                logger.error(f"'final_formatting_callback': Error parsing IterationData from dict in history: {e}", exc_info=True)
                # Skip invalid entries
                continue
        else:
            logger.warning(f"'final_formatting_callback': Unknown item type in history: {type(item_raw)}")
            continue

    # Retrieve initial inputs from state, set by orchestrator
    role = callback_context.state.get("role", "Not provided")
    industry = callback_context.state.get("industry", "Not provided")
    question = callback_context.state.get("question", "Not provided")
    resume = callback_context.state.get("resume", "")
    job_description = callback_context.state.get("jobDescription", "")
    user_id = callback_context.state.get("userId", "anonymous") # Default to anonymous if not set

    metadata = ResponseMetadata(
        role=role,
        industry=industry,
        question=question,
        resume=resume,
        jobDescription=job_description,
        status="COMPLETED", # Can be updated based on error handling in future
        createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        userId=user_id
    )

    # Extract timing data from orchestrator's timing_data and individual agents
    timing_data = callback_context.state.get("timing_data", {})
    generation_time = callback_context.state.get("generation_time", 0.0)
    critique_times = callback_context.state.get("critique_times", [])
    refinement_times = callback_context.state.get("refinement_times", [])
    
    # Force timing logs to WARNING level for visibility
    logger.warning(f"🕐 TIMING DATA - Total workflow: {timing_data}")
    logger.warning(f"🕐 TIMING DATA - Generation time: {generation_time}")
    logger.warning(f"🕐 TIMING DATA - Critique times: {critique_times}")
    logger.warning(f"🕐 TIMING DATA - Refinement times: {refinement_times}")
    print(f"🕐 TIMING: workflow={timing_data}, gen={generation_time}, crit={critique_times}, ref={refinement_times}")
    
    perf_metrics = PerformanceMetrics(
        totalWorkflowTime=timing_data.get("total_workflow", 0.0) if isinstance(timing_data, dict) else 0.0,
        generationTime=generation_time,
        critiqueTimes=critique_times,
        refinementTimes=refinement_times
    )
    logger.info(f"'final_formatting_callback': Created perf_metrics: {perf_metrics.model_dump()}")

    final_response_obj = FinalResponse(
        metadata=metadata,
        iterations=processed_history_list,
        performanceMetrics=perf_metrics
    )

    try:
        final_json_string = final_response_obj.model_dump_json(indent=2)
    except Exception as e:
        logger.error(f"'final_formatting_callback': Error serializing FinalResponse to JSON: {e}", exc_info=True)
        # Fallback or error response
        error_response = {"error": "Failed to generate final response", "details": str(e)}
        import json
        final_json_string = json.dumps(error_response, indent=2)

    logger.info("'final_formatting_callback': Prepared final output successfully.")
    return genai_types.Content(parts=[genai_types.Part(text=final_json_string)])
