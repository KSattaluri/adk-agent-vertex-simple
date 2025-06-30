"""
Cloud Run Agent HTTP Client
Handles communication with agent deployed on Cloud Run via HTTP API
"""

import json
import logging
import asyncio
import aiohttp
import requests
from typing import AsyncGenerator, Dict, Any, Optional
from shared_utils.error_utils import create_error_response

logger = logging.getLogger(__name__)

class CloudRunAgent:
    """Client for communicating with agent deployed on Cloud Run"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout for LLM calls
    
    async def stream_query(
        self,
        user_id: str,
        session_id: str,
        initial_state: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streams a query to the agent service using two-step process for local ADK agent."""
        
        # Step 1: Create session with initial state
        create_session_payload = {
            "app_name": "refiner_agent",
            "user_id": user_id,
            "session_id": session_id
        }
        create_session_payload.update(initial_state)
        
        # Step 2: Run agent with trigger message
        run_payload = {
            "app_name": "refiner_agent",
            "user_id": user_id,
            "session_id": session_id,
            "new_message": {
                "role": "user",
                "parts": [{"text": "Start"}]
            }
        }

        logger.info(f"[CLOUD_RUN] Creating session for user {user_id} with session {session_id}")
        logger.debug(f"[CLOUD_RUN] Initial state: {json.dumps(initial_state, indent=2)}")

        http_session = None
        try:
            http_session = aiohttp.ClientSession(timeout=self.timeout)
            
            # Step 1: Create or update the session with initial state
            async with http_session.post(
                f"{self.base_url}/apps/refiner_agent/users/{user_id}/sessions/{session_id}",
                json=create_session_payload,
                headers={"Content-Type": "application/json"}
            ) as create_response:
                if create_response.status not in [200, 201, 409]:
                    error_text = await create_response.text()
                    logger.error(f"[CLOUD_RUN] Session creation failed for {session_id}: {create_response.status} - {error_text}")
                    yield create_error_response(
                        f"Session creation failed: {create_response.status} ({error_text[:100]})",
                        error_type="session_creation_error",
                        status_code=create_response.status,
                        component="cloud_run_agent",
                        return_format="dict"
                    )
                    return
                else:
                    logger.info(f"[CLOUD_RUN] Session {session_id} created successfully (status: {create_response.status})")

            # Step 2: Run the agent with streaming
            async with http_session.post(
                f"{self.base_url}/run_sse",
                json=run_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[CLOUD_RUN] Stream request failed: {response.status} - {error_text}")
                    yield create_error_response(
                        f"Agent service error: {response.status} ({error_text[:100]})",
                        error_type="agent_service_error",
                        status_code=response.status,
                        component="cloud_run_agent",
                        return_format="dict",
                    )
                    return

                async for line in response.content:
                    if not line:
                        continue
                    
                    line_text = line.decode("utf-8").strip()
                    if not line_text.startswith("data: "):
                        continue

                    try:
                        json_data = line_text[len("data: "):]
                        if not json_data:
                            continue
                        
                        adk_event = json.loads(json_data)
                        if (
                            isinstance(adk_event, dict) and
                            "content" in adk_event and
                            isinstance(adk_event["content"], dict) and
                            "parts" in adk_event["content"]
                        ):
                            for part in adk_event["content"]["parts"]:
                                if "text" in part:
                                    try:
                                        event_data = json.loads(part["text"])
                                        logger.debug(f"[CLOUD_RUN] Streamed Event Data: {event_data}")
                                        yield event_data
                                    except json.JSONDecodeError:
                                        logger.info(f"[CLOUD_RUN] Plain text from agent: {part['text']}")
                                        yield {"type": "status", "message": part["text"]}
                    except json.JSONDecodeError as e:
                        logger.warning(f"[CLOUD_RUN] Failed to parse stream line: {line_text[:100]}... - {e}")
                    except Exception as e:
                        logger.error(f"[CLOUD_RUN] Stream processing error: {e}", exc_info=True)

        except asyncio.TimeoutError:
            logger.error(f"[CLOUD_RUN] Request timeout after {self.timeout.total} seconds")
            yield create_error_response(
                "Request timeout",
                error_type="timeout_error",
                component="cloud_run_agent",
                details={"timeout_seconds": self.timeout.total},
                return_format="dict",
            )
        except Exception as e:
            logger.error(f"[CLOUD_RUN] Stream query error: {e}", exc_info=True)
            yield create_error_response(
                f"Connection error: {str(e)}",
                error_type="connection_error",
                component="cloud_run_agent",
                details={"exception": str(e)},
                return_format="dict",
            )
        finally:
            if http_session and not http_session.closed:
                await http_session.close()
    
    def health_check(self) -> bool:
        """Check if the Cloud Run agent service is healthy"""
        try:
            response = requests.get(
                f"{self.base_url}/",
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[CLOUD_RUN] Health check failed: {e}")
            return False