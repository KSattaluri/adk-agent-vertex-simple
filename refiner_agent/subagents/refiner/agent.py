"""
STAR Answer Refiner Agent

This agent refines STAR format answers based on critique feedback.
"""

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from ...config import STAR_REFINER_MODEL
from schemas import STARResponse  # Added import for STARResponse
import time
import logging

logger = logging.getLogger(__name__)

# Timing callbacks for refinement
def refinement_before_callback(callback_context: CallbackContext):
    """Record refinement start time"""
    callback_context.state["refinement_start_time"] = time.time()

def refinement_after_callback(callback_context: CallbackContext):
    """Record refinement completion time"""
    start_time = callback_context.state.get("refinement_start_time")
    if start_time:
        duration = time.time() - start_time
        refinement_times = callback_context.state.get("refinement_times", [])
        refinement_times.append(duration)
        callback_context.state["refinement_times"] = refinement_times
        logger.info(f"STAR refinement completed in {duration:.3f}s")

# Define the STAR Answer Refiner Agent
star_refiner = LlmAgent(
    name="STARAnswerRefiner",
    model=STAR_REFINER_MODEL,
    instruction="""You are an expert career coach helping someone improve their interview answer.
They are applying for a {role} position in {industry}.

## CONTEXT
Question: {question}
Current answer: {current_star_answer}
Feedback received: {current_critique}

## YOUR TASK
As their coach, help them improve their STAR answer based on the feedback.
Focus on the specific suggestions while maintaining their authentic voice and experience.
Make it more compelling for this {role} role in {industry}.

Respond using the STARResponse schema format with JSON output only.""",
    description="Refines STAR format answers based on specific critique feedback",
    output_key="current_star_answer",
    output_schema=STARResponse,  # Added output_schema
    before_agent_callback=refinement_before_callback,
    after_agent_callback=refinement_after_callback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True
)