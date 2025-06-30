"""
STAR Answer Critique Agent

This agent evaluates STAR format answers for quality and provides feedback.
"""

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from ...config import STAR_CRITIQUE_MODEL
from schemas import Critique  # Added import
from ...callbacks import iteration_history_callback
import time
import logging

logger = logging.getLogger(__name__)

# Timing callbacks for critique
def critique_before_callback(callback_context: CallbackContext):
    """Record critique start time"""
    callback_context.state["critique_start_time"] = time.time()

def critique_after_callback(callback_context: CallbackContext):
    """Record critique completion time and call iteration history callback"""
    start_time = callback_context.state.get("critique_start_time")
    if start_time:
        duration = time.time() - start_time
        critique_times = callback_context.state.get("critique_times", [])
        critique_times.append(duration)
        callback_context.state["critique_times"] = critique_times
        logger.info(f"STAR critique completed in {duration:.3f}s")
    
    # Call the original iteration history callback
    iteration_history_callback(callback_context)

# Define the STAR Answer Critique Agent
star_critique = LlmAgent(
    name="STARAnswerCritic",
    model=STAR_CRITIQUE_MODEL,
    instruction="""You are an expert career coach and excellent editor and interview prep coach.
User has come to you looking for advice on preparing for an interview where the interview will be in STAR format.
User's current role is {role} and works in {industry}.

## CONTEXT
Question: {question}
Current answer to evaluate: {current_star_answer}

## YOUR TASK
As their coach, provide a rating (1.0-5.0) and specific feedback to help them improve their STAR answer.
Focus on structure, relevance to their {role} role in {industry}, specific details, and professional impact.

Be encouraging but honest. Most answers score 3.0-4.5. Only exceptional answers score above 4.6.
Respond using the Critique schema format with JSON output only.""",
    description="Evaluates STAR answers and provides specific feedback for improvement",
    tools=[],  # No tools needed - the agent does the evaluation directly
    output_key="current_critique",
    output_schema=Critique,  # Added output_schema
    before_agent_callback=critique_before_callback,
    after_agent_callback=critique_after_callback,  # Now includes timing + iteration history
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True
)