"""
STAR Answer Refiner Agent using ADK Sequential and Loop Agents
"""

# Import the main generator agent instance
from .subagents.generator.agent import star_generator

# Import the refactored STAROrchestrator class and the pre-configured refinement_loop_agent instance
from .orchestrator import STAROrchestrator, refinement_loop_agent

# Create the root_agent.
# The STAROrchestrator is a SequentialAgent. Its constructor now expects
# the star_generator and the refinement_loop_agent.
# Internal components like critique, refiner, rating_checker, as well as
# MAX_ITERATIONS, RATING_THRESHOLD, and callbacks (iteration_history_callback,
# final_formatting_callback) are encapsulated within the definitions of
# STAROrchestrator and refinement_loop_agent in orchestrator.py.
root_agent = STAROrchestrator(
    name="refiner_agent",  # Must match directory name, passed to the agent constructor
    star_generator=star_generator,  # Argument for STAROrchestrator's __init__
    refinement_loop_agent=refinement_loop_agent  # Argument for STAROrchestrator's __init__
)