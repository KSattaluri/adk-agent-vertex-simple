"""
STAR Answer Orchestrator Agent
"""

import datetime
import json
import logging
import warnings
from typing import AsyncGenerator, Dict, Any, List, Optional
from typing_extensions import override

# Suppress OpenTelemetry context warnings/errors in async generators
warnings.filterwarnings("ignore", message=".*Failed to detach context.*")
warnings.filterwarnings("ignore", message=".*was created in a different Context.*")

# Also suppress the underlying ValueError from OpenTelemetry
import logging
opentelemetry_logger = logging.getLogger("opentelemetry")
opentelemetry_logger.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import ValidationError, Field
from schemas import IterationData, STARResponse, Critique 
from .callbacks import iteration_history_callback, final_formatting_callback
from .config import MAX_ITERATIONS, RATING_THRESHOLD
from .flow_control import rating_checker
from .subagents.generator.agent import star_generator
from .subagents.critique.agent import star_critique
from .subagents.refiner.agent import star_refiner
from .timing import TimingTracker

from shared_utils.error_utils import create_structured_error_response

# Refinement Loop Agent Configuration
refinement_loop_agent = LoopAgent(
    name="refinement_loop",
    max_iterations=MAX_ITERATIONS,
    sub_agents=[
        star_critique, 
        rating_checker,
        star_refiner
    ]
    # Note: Moved iteration_history_callback to star_critique agent
)
logger.info(f"Refinement Loop Agent '{refinement_loop_agent.name}' configured with max iterations: {MAX_ITERATIONS}")

class STAROrchestrator(Agent):
    """
    Orchestrates STAR answer generation and refinement using a sequential flow.
    Relies on callbacks for state management and final output formatting.
    """
    star_generator: Agent
    refinement_loop_agent: LoopAgent
    timing_tracker: TimingTracker
    sequential_agent: SequentialAgent
    def __init__(
        self,
        name: str,
        star_generator: Agent,
        refinement_loop_agent: LoopAgent,
    ):
        # Create dependent objects first
        timing_tracker = TimingTracker()
        # Create the callback and log its creation
        final_callback = self._create_final_callback_with_timing()
        print(f"🏗️ Created final callback for orchestrator: {name}")
        logger.warning(f"🏗️ Created final callback for orchestrator: {name}")
        
        sequential_agent = SequentialAgent(
            name=f"{name}_sequential_flow",
            sub_agents=[star_generator, refinement_loop_agent],
            description="Internal sequential flow for STAR generation and refinement.",
            after_agent_callback=final_callback
        )
        
        # Pass all declared fields to super().__init__ for Pydantic validation
        super().__init__(
            name=name,
            description="Orchestrates STAR answer generation and iterative refinement.",
            star_generator=star_generator,
            refinement_loop_agent=refinement_loop_agent,
            timing_tracker=timing_tracker,
            sequential_agent=sequential_agent
        )

    def _create_final_callback_with_timing(self):
        """Create a callback that has access to the timing tracker"""
        def timing_aware_final_callback(callback_context):
            # Add timing data to state before calling the original callback
            print(f"🔥 TIMING_AWARE_FINAL_CALLBACK triggered for invocation: {callback_context.invocation_id}")
            logger.warning(f"🔥 TIMING_AWARE_FINAL_CALLBACK triggered for invocation: {callback_context.invocation_id}")
            
            self.timing_tracker.end("total_workflow")
            timing_data = self.timing_tracker.get_timings()
            if timing_data:
                callback_context.state["timing_data"] = timing_data
                logger.warning(f"STAROrchestrator: Added timing data to state: {timing_data}")
                print(f"📊 Added timing data: {timing_data}")
            
            # Call the original final formatting callback
            return final_formatting_callback(callback_context)
        
        return timing_aware_final_callback

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        logger.info(f"STAROrchestrator '{self.name}' invoked. Invocation ID: {ctx.invocation_id}")
        
        self.timing_tracker.reset()
        self.timing_tracker.start("total_workflow")

        try:
            # Validate required fields are present (input validation only)
            if not all(ctx.session.state.get(key) for key in ["role", "industry", "question"]):
                logger.error(f"Missing required fields. Available keys: {list(ctx.session.state.keys())}")
                error_payload = create_structured_error_response(
                    "Missing required input fields (role, industry, or question)",
                    component="orchestrator",
                    details={
                        "available_keys": list(ctx.session.state.keys()),
                        "missing_keys": [key for key in ["role", "industry", "question"] 
                                        if not ctx.session.state.get(key)]
                    }
                )
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text=error_payload)])
                )
                return

            logger.debug(
                f"Proceeding with: role='{ctx.session.state.get('role')}', "
                f"industry='{ctx.session.state.get('industry')}', "
                f"question='{ctx.session.state.get('question', '')[:50]}...'"
            )

            # Pure delegation to sequential agent - let ADK and callbacks handle state management
            async for event in self.sequential_agent.run_async(ctx):
                yield event

        except Exception as e:
            logger.error(f"Sequential agent failed: {e}", exc_info=True)
            error_payload = create_structured_error_response(
                f"Agent execution failed: {str(e)}",
                component="orchestrator",
                details={"error_type": type(e).__name__}
            )
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=error_payload)])
            )
        finally:
            # Timing data is now handled in the sequential agent callback
            logger.info(f"STAROrchestrator: Workflow completed.")

    # Remove the _execute_workflow method - no longer needed