import logging
from typing import AsyncGenerator
from typing_extensions import override

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

# Assuming your Critique schema is in .schemas and has a 'rating' field
# from .schemas import Critique # We'll fetch the dict from state directly

logger = logging.getLogger(__name__)

class RatingChecker(BaseAgent):
    """Checks critique rating and escalates to stop refinement if rating >= threshold."""
    
    rating_threshold: float = 4.6  # Define as a class field for Pydantic

    def __init__(self, name: str, rating_threshold: float = 4.6):
        super().__init__(name=name, rating_threshold=rating_threshold)
        logger.info(f"RatingChecker '{name}' initialized with threshold: {self.rating_threshold}")

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Checks the critique rating from session state and yields an escalation event if threshold is met."""
        logger.debug(f"'{self.name}' started. Invocation ID: {ctx.invocation_id}")

        # The star_critique agent should have placed its output (Critique model) 
        # into state, e.g., under the key "current_critique".
        critique_output = ctx.session.state.get("current_critique")

        if critique_output is None:
            logger.warning(
                f"'{self.name}': Critique output not found in session state under key 'current_critique'. Proceeding without escalation."
            )
            yield Event(author=self.name)
            return

        # Assuming critique_output is a dictionary representation of the Critique Pydantic model
        # or the Pydantic model itself which can be accessed like a dict.
        try:
            rating = critique_output.get("rating") if isinstance(critique_output, dict) else critique_output.rating
            if rating is None:
                raise ValueError("'rating' field is missing or None in critique_output")
            rating = float(rating) # Ensure it's a float
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(
                f"'{self.name}': Error accessing rating from critique_output. "
                f"Critique data: {critique_output}. Error: {e}. Proceeding without escalation."
            )
            yield Event(author=self.name)
            return

        logger.info(f"'{self.name}': Found rating {rating} in state. Threshold is {self.rating_threshold}.")

        if rating >= self.rating_threshold:
            logger.info(
                f"'{self.name}': Rating {rating} >= threshold {self.rating_threshold}. Escalating to stop loop."
            )
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            logger.info(
                f"'{self.name}': Rating {rating} < threshold {self.rating_threshold}. Continuing loop."
            )
            yield Event(author=self.name) # Continue loop

        logger.debug(f"'{self.name}' finished.")

# Create an instance of RatingChecker with the configured threshold
from .config import RATING_THRESHOLD
rating_checker = RatingChecker(name="rating_checker", rating_threshold=RATING_THRESHOLD)
