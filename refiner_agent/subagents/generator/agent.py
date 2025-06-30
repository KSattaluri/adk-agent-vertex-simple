"""
STAR Answer Generator Agent

This agent creates the initial STAR format answer based on user inputs.
"""

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from ...config import STAR_GENERATOR_MODEL
from schemas import STARResponse  # Added import
import time
import logging

logger = logging.getLogger(__name__)

# Timing callbacks for generation
def generation_before_callback(callback_context: CallbackContext):
    """Record generation start time"""
    callback_context.state["generation_start_time"] = time.time()

def generation_after_callback(callback_context: CallbackContext):
    """Record generation completion time"""
    start_time = callback_context.state.get("generation_start_time")
    if start_time:
        duration = time.time() - start_time
        callback_context.state["generation_time"] = duration
        logger.info(f"STAR generation completed in {duration:.3f}s")

# Define the STAR Answer Generator Agent
star_generator = LlmAgent(
    name="STARAnswerGenerator",
    model=STAR_GENERATOR_MODEL,
    instruction="""You are an expert career coach helping someone prepare for their interview.
They are applying for a {role} position in {industry}.

## CONTEXT
Question: {question}
{% if resume %}Background: Review {resume} and choose appropriate background information to include in your answer.{% endif %}
{% if jobDescription %}Job Details: Picked situation should be relevant to {jobDescription}.{% endif %}

## YOUR TASK
Create a compelling STAR format answer (Situation, Task, Action, Result) that showcases the candidate's qualifications for this {role} role.
Make it specific, professional, and tailored to {industry}.

Respond using the STARResponse schema format with JSON output only.""",
    description="Generates initial STAR format answers for interview questions",
    output_key="current_star_answer",
    output_schema=STARResponse,  # Added output_schema
    before_agent_callback=generation_before_callback,
    after_agent_callback=generation_after_callback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True
)