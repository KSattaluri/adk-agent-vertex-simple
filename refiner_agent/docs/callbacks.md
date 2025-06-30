Table of contents
Introduction: What are Callbacks and Why Use Them?
The Callback Mechanism: Interception and Control
Agent Lifecycle Callbacks
Before Agent Callback
After Agent Callback
LLM Interaction Callbacks
Before Model Callback
After Model Callback
Tool Execution Callbacks
Before Tool Callback
After Tool Callback
Design Patterns
1. Guardrails & Policy Enforcement
2. Dynamic State Management
3. Logging and Monitoring
4. Caching
5. Request/Response Modification
6. Conditional Skipping of Steps
7. Tool-Specific Actions (Authentication & Summarization Control)
8. Artifact Handling
Best Practices for Callbacks

Introduction: What are Callbacks and Why Use Them?¶
Callbacks are a cornerstone feature of ADK, providing a powerful mechanism to hook into an agent's execution process. They allow you to observe, customize, and even control the agent's behavior at specific, predefined points without modifying the core ADK framework code.

What are they? In essence, callbacks are standard functions that you define. You then associate these functions with an agent when you create it. The ADK framework automatically calls your functions at key stages, letting you observe or intervene. Think of it like checkpoints during the agent's process:

Before the agent starts its main work on a request, and after it finishes: When you ask an agent to do something (e.g., answer a question), it runs its internal logic to figure out the response.
The Before Agent callback executes right before this main work begins for that specific request.
The After Agent callback executes right after the agent has finished all its steps for that request and has prepared the final result, but just before the result is returned.
This "main work" encompasses the agent's entire process for handling that single request. This might involve deciding to call an LLM, actually calling the LLM, deciding to use a tool, using the tool, processing the results, and finally putting together the answer. These callbacks essentially wrap the whole sequence from receiving the input to producing the final output for that one interaction.
Before sending a request to, or after receiving a response from, the Large Language Model (LLM): These callbacks (Before Model, After Model) allow you to inspect or modify the data going to and coming from the LLM specifically.
Before executing a tool (like a Python function or another agent) or after it finishes: Similarly, Before Tool and After Tool callbacks give you control points specifically around the execution of tools invoked by the agent.
intro_components.png

Why use them? Callbacks unlock significant flexibility and enable advanced agent capabilities:

Observe & Debug: Log detailed information at critical steps for monitoring and troubleshooting.
Customize & Control: Modify data flowing through the agent (like LLM requests or tool results) or even bypass certain steps entirely based on your logic.
Implement Guardrails: Enforce safety rules, validate inputs/outputs, or prevent disallowed operations.
Manage State: Read or dynamically update the agent's session state during execution.
Integrate & Enhance: Trigger external actions (API calls, notifications) or add features like caching.
How are they added:

Code
The Callback Mechanism: Interception and Control¶
When the ADK framework encounters a point where a callback can run (e.g., just before calling the LLM), it checks if you provided a corresponding callback function for that agent. If you did, the framework executes your function.

Context is Key: Your callback function isn't called in isolation. The framework provides special context objects (CallbackContext or ToolContext) as arguments. These objects contain vital information about the current state of the agent's execution, including the invocation details, session state, and potentially references to services like artifacts or memory. You use these context objects to understand the situation and interact with the framework. (See the dedicated "Context Objects" section for full details).

Controlling the Flow (The Core Mechanism): The most powerful aspect of callbacks lies in how their return value influences the agent's subsequent actions. This is how you intercept and control the execution flow:

return None (Allow Default Behavior):

The specific return type can vary depending on the language. In Java, the equivalent return type is Optional.empty(). Refer to the API documentation for language specific guidance.
This is the standard way to signal that your callback has finished its work (e.g., logging, inspection, minor modifications to mutable input arguments like llm_request) and that the ADK agent should proceed with its normal operation.
For before_* callbacks (before_agent, before_model, before_tool), returning None means the next step in the sequence (running the agent logic, calling the LLM, executing the tool) will occur.
For after_* callbacks (after_agent, after_model, after_tool), returning None means the result just produced by the preceding step (the agent's output, the LLM's response, the tool's result) will be used as is.
return <Specific Object> (Override Default Behavior):

Returning a specific type of object (instead of None) is how you override the ADK agent's default behavior. The framework will use the object you return and skip the step that would normally follow or replace the result that was just generated.
before_agent_callback → types.Content: Skips the agent's main execution logic (_run_async_impl / _run_live_impl). The returned Content object is immediately treated as the agent's final output for this turn. Useful for handling simple requests directly or enforcing access control.
before_model_callback → LlmResponse: Skips the call to the external Large Language Model. The returned LlmResponse object is processed as if it were the actual response from the LLM. Ideal for implementing input guardrails, prompt validation, or serving cached responses.
before_tool_callback → dict or Map: Skips the execution of the actual tool function (or sub-agent). The returned dict is used as the result of the tool call, which is then typically passed back to the LLM. Perfect for validating tool arguments, applying policy restrictions, or returning mocked/cached tool results.
after_agent_callback → types.Content: Replaces the Content that the agent's run logic just produced.
after_model_callback → LlmResponse: Replaces the LlmResponse received from the LLM. Useful for sanitizing outputs, adding standard disclaimers, or modifying the LLM's response structure.
after_tool_callback → dict or Map: Replaces the dict result returned by the tool. Allows for post-processing or standardization of tool outputs before they are sent back to the LLM.
Conceptual Code Example (Guardrail):

This example demonstrates the common pattern for a guardrail using before_model_callback.

Code

Python
Java

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from google.adk.runners import Runner
from typing import Optional
from google.genai import types 
from google.adk.sessions import InMemorySessionService

GEMINI_2_FLASH="gemini-2.0-flash"

# --- Define the Callback Function ---
def simple_before_model_modifier(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Inspects/modifies the LLM request or skips the call."""
    agent_name = callback_context.agent_name
    print(f"[Callback] Before model call for agent: {agent_name}")

    # Inspect the last user message in the request contents
    last_user_message = ""
    if llm_request.contents and llm_request.contents[-1].role == 'user':
         if llm_request.contents[-1].parts:
            last_user_message = llm_request.contents[-1].parts[0].text
    print(f"[Callback] Inspecting last user message: '{last_user_message}'")

    # --- Modification Example ---
    # Add a prefix to the system instruction
    original_instruction = llm_request.config.system_instruction or types.Content(role="system", parts=[])
    prefix = "[Modified by Callback] "
    # Ensure system_instruction is Content and parts list exists
    if not isinstance(original_instruction, types.Content):
         # Handle case where it might be a string (though config expects Content)
         original_instruction = types.Content(role="system", parts=[types.Part(text=str(original_instruction))])
    if not original_instruction.parts:
        original_instruction.parts.append(types.Part(text="")) # Add an empty part if none exist

    # Modify the text of the first part
    modified_text = prefix + (original_instruction.parts[0].text or "")
    original_instruction.parts[0].text = modified_text
    llm_request.config.system_instruction = original_instruction
    print(f"[Callback] Modified system instruction to: '{modified_text}'")

    # --- Skip Example ---
    # Check if the last user message contains "BLOCK"
    if "BLOCK" in last_user_message.upper():
        print("[Callback] 'BLOCK' keyword found. Skipping LLM call.")
        # Return an LlmResponse to skip the actual LLM call
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="LLM call was blocked by before_model_callback.")],
            )
        )
    else:
        print("[Callback] Proceeding with LLM call.")
        # Return None to allow the (modified) request to go to the LLM
        return None


# Create LlmAgent and Assign Callback
my_llm_agent = LlmAgent(
        name="ModelCallbackAgent",
        model=GEMINI_2_FLASH,
        instruction="You are a helpful assistant.", # Base instruction
        description="An LLM agent demonstrating before_model_callback",
        before_model_callback=simple_before_model_modifier # Assign the function here
)

APP_NAME = "guardrail_app"
USER_ID = "user_1"
SESSION_ID = "session_001"

# Session and Runner
session_service = InMemorySessionService()
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
runner = Runner(agent=my_llm_agent, app_name=APP_NAME, session_service=session_service)


# Agent Interaction
def call_agent(query):
  content = types.Content(role='user', parts=[types.Part(text=query)])
  events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

  for event in events:
      if event.is_final_response():
          final_response = event.content.parts[0].text
          print("Agent Response: ", final_response)

call_agent("callback example")

By understanding this mechanism of returning None versus returning specific objects, you can precisely control the agent's execution path, making callbacks an essential tool for building sophisticated and reliable agents with ADK.

Types of Callbacks¶
The framework provides different types of callbacks that trigger at various stages of an agent's execution. Understanding when each callback fires and what context it receives is key to using them effectively.

Agent Lifecycle Callbacks¶
These callbacks are available on any agent that inherits from BaseAgent (including LlmAgent, SequentialAgent, ParallelAgent, LoopAgent, etc).

Note

The specific method names or return types may vary slightly by SDK language (e.g., return None in Python, return Optional.empty() or Maybe.empty() in Java). Refer to the language-specific API documentation for details.

Before Agent Callback¶
When: Called immediately before the agent's _run_async_impl (or _run_live_impl) method is executed. It runs after the agent's InvocationContext is created but before its core logic begins.

Purpose: Ideal for setting up resources or state needed only for this specific agent's run, performing validation checks on the session state (callback_context.state) before execution starts, logging the entry point of the agent's activity, or potentially modifying the invocation context before the core logic uses it.

Code
Note on the before_agent_callback Example:

What it Shows: This example demonstrates the before_agent_callback. This callback runs right before the agent's main processing logic starts for a given request.
How it Works: The callback function (check_if_agent_should_run) looks at a flag (skip_llm_agent) in the session's state.
If the flag is True, the callback returns a types.Content object. This tells the ADK framework to skip the agent's main execution entirely and use the callback's returned content as the final response.
If the flag is False (or not set), the callback returns None or an empty object. This tells the ADK framework to proceed with the agent's normal execution (calling the LLM in this case).
Expected Outcome: You'll see two scenarios:
In the session with the skip_llm_agent: True state, the agent's LLM call is bypassed, and the output comes directly from the callback ("Agent... skipped...").
In the session without that state flag, the callback allows the agent to run, and you see the actual response from the LLM (e.g., "Hello!").
Understanding Callbacks: This highlights how before_ callbacks act as gatekeepers, allowing you to intercept execution before a major step and potentially prevent it based on checks (like state, input validation, permissions).
After Agent Callback¶
When: Called immediately after the agent's _run_async_impl (or _run_live_impl) method successfully completes. It does not run if the agent was skipped due to before_agent_callback returning content or if end_invocation was set during the agent's run.

Purpose: Useful for cleanup tasks, post-execution validation, logging the completion of an agent's activity, modifying final state, or augmenting/replacing the agent's final output.

Code
Note on the after_agent_callback Example:

What it Shows: This example demonstrates the after_agent_callback. This callback runs right after the agent's main processing logic has finished and produced its result, but before that result is finalized and returned.
How it Works: The callback function (modify_output_after_agent) checks a flag (add_concluding_note) in the session's state.
If the flag is True, the callback returns a new types.Content object. This tells the ADK framework to replace the agent's original output with the content returned by the callback.
If the flag is False (or not set), the callback returns None or an empty object. This tells the ADK framework to use the original output generated by the agent.
Expected Outcome: You'll see two scenarios:
In the session without the add_concluding_note: True state, the callback allows the agent's original output ("Processing complete!") to be used.
In the session with that state flag, the callback intercepts the agent's original output and replaces it with its own message ("Concluding note added...").
Understanding Callbacks: This highlights how after_ callbacks allow post-processing or modification. You can inspect the result of a step (the agent's run) and decide whether to let it pass through, change it, or completely replace it based on your logic.
LLM Interaction Callbacks¶
These callbacks are specific to LlmAgent and provide hooks around the interaction with the Large Language Model.

Before Model Callback¶
When: Called just before the generate_content_async (or equivalent) request is sent to the LLM within an LlmAgent's flow.

Purpose: Allows inspection and modification of the request going to the LLM. Use cases include adding dynamic instructions, injecting few-shot examples based on state, modifying model config, implementing guardrails (like profanity filters), or implementing request-level caching.

Return Value Effect:
If the callback returns None (or a Maybe.empty() object in Java), the LLM continues its normal workflow. If the callback returns an LlmResponse object, then the call to the LLM is skipped. The returned LlmResponse is used directly as if it came from the model. This is powerful for implementing guardrails or caching.

Code
After Model Callback¶
When: Called just after a response (LlmResponse) is received from the LLM, before it's processed further by the invoking agent.

Purpose: Allows inspection or modification of the raw LLM response. Use cases include

logging model outputs,
reformatting responses,
censoring sensitive information generated by the model,
parsing structured data from the LLM response and storing it in callback_context.state
or handling specific error codes.
Code
Tool Execution Callbacks¶
These callbacks are also specific to LlmAgent and trigger around the execution of tools (including FunctionTool, AgentTool, etc.) that the LLM might request.

Before Tool Callback¶
When: Called just before a specific tool's run_async method is invoked, after the LLM has generated a function call for it.

Purpose: Allows inspection and modification of tool arguments, performing authorization checks before execution, logging tool usage attempts, or implementing tool-level caching.

Return Value Effect:

If the callback returns None (or a Maybe.empty() object in Java), the tool's run_async method is executed with the (potentially modified) args.
If a dictionary (or Map in Java) is returned, the tool's run_async method is skipped. The returned dictionary is used directly as the result of the tool call. This is useful for caching or overriding tool behavior.
Code

Python
Java

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from typing import Optional
from google.genai import types 
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any


GEMINI_2_FLASH="gemini-2.0-flash"

def get_capital_city(country: str) -> str:
    """Retrieves the capital city of a given country."""
    print(f"--- Tool 'get_capital_city' executing with country: {country} ---")
    country_capitals = {
        "united states": "Washington, D.C.",
        "canada": "Ottawa",
        "france": "Paris",
        "germany": "Berlin",
    }
    return country_capitals.get(country.lower(), f"Capital not found for {country}")

capital_tool = FunctionTool(func=get_capital_city)

def simple_before_tool_modifier(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext
) -> Optional[Dict]:
    """Inspects/modifies tool args or skips the tool call."""
    agent_name = tool_context.agent_name
    tool_name = tool.name
    print(f"[Callback] Before tool call for tool '{tool_name}' in agent '{agent_name}'")
    print(f"[Callback] Original args: {args}")

    if tool_name == 'get_capital_city' and args.get('country', '').lower() == 'canada':
        print("[Callback] Detected 'Canada'. Modifying args to 'France'.")
        args['country'] = 'France'
        print(f"[Callback] Modified args: {args}")
        return None

    # If the tool is 'get_capital_city' and country is 'BLOCK'
    if tool_name == 'get_capital_city' and args.get('country', '').upper() == 'BLOCK':
        print("[Callback] Detected 'BLOCK'. Skipping tool execution.")
        return {"result": "Tool execution was blocked by before_tool_callback."}

    print("[Callback] Proceeding with original or previously modified args.")
    return None

my_llm_agent = LlmAgent(
        name="ToolCallbackAgent",
        model=GEMINI_2_FLASH,
        instruction="You are an agent that can find capital cities. Use the get_capital_city tool.",
        description="An LLM agent demonstrating before_tool_callback",
        tools=[capital_tool],
        before_tool_callback=simple_before_tool_modifier
)

APP_NAME = "guardrail_app"
USER_ID = "user_1"
SESSION_ID = "session_001"

# Session and Runner
session_service = InMemorySessionService()
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
runner = Runner(agent=my_llm_agent, app_name=APP_NAME, session_service=session_service)


# Agent Interaction
def call_agent(query):
  content = types.Content(role='user', parts=[types.Part(text=query)])
  events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

  for event in events:
      if event.is_final_response():
          final_response = event.content.parts[0].text
          print("Agent Response: ", final_response)

call_agent("callback example")

After Tool Callback¶
When: Called just after the tool's run_async method completes successfully.

Purpose: Allows inspection and modification of the tool's result before it's sent back to the LLM (potentially after summarization). Useful for logging tool results, post-processing or formatting results, or saving specific parts of the result to the session state.

Return Value Effect:

If the callback returns None (or a Maybe.empty() object in Java), the original tool_response is used.
If a new dictionary is returned, it replaces the original tool_response. This allows modifying or filtering the result seen by the LLM.
Code

Python
Java

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from typing import Optional
from google.genai import types 
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any
from copy import deepcopy

GEMINI_2_FLASH="gemini-2.0-flash"

# --- Define a Simple Tool Function (Same as before) ---
def get_capital_city(country: str) -> str:
    """Retrieves the capital city of a given country."""
    print(f"--- Tool 'get_capital_city' executing with country: {country} ---")
    country_capitals = {
        "united states": "Washington, D.C.",
        "canada": "Ottawa",
        "france": "Paris",
        "germany": "Berlin",
    }
    return {"result": country_capitals.get(country.lower(), f"Capital not found for {country}")}

# --- Wrap the function into a Tool ---
capital_tool = FunctionTool(func=get_capital_city)

# --- Define the Callback Function ---
def simple_after_tool_modifier(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Dict
) -> Optional[Dict]:
    """Inspects/modifies the tool result after execution."""
    agent_name = tool_context.agent_name
    tool_name = tool.name
    print(f"[Callback] After tool call for tool '{tool_name}' in agent '{agent_name}'")
    print(f"[Callback] Args used: {args}")
    print(f"[Callback] Original tool_response: {tool_response}")

    # Default structure for function tool results is {"result": <return_value>}
    original_result_value = tool_response.get("result", "")
    # original_result_value = tool_response

    # --- Modification Example ---
    # If the tool was 'get_capital_city' and result is 'Washington, D.C.'
    if tool_name == 'get_capital_city' and original_result_value == "Washington, D.C.":
        print("[Callback] Detected 'Washington, D.C.'. Modifying tool response.")

        # IMPORTANT: Create a new dictionary or modify a copy
        modified_response = deepcopy(tool_response)
        modified_response["result"] = f"{original_result_value} (Note: This is the capital of the USA)."
        modified_response["note_added_by_callback"] = True # Add extra info if needed

        print(f"[Callback] Modified tool_response: {modified_response}")
        return modified_response # Return the modified dictionary

    print("[Callback] Passing original tool response through.")
    # Return None to use the original tool_response
    return None


# Create LlmAgent and Assign Callback
my_llm_agent = LlmAgent(
        name="AfterToolCallbackAgent",
        model=GEMINI_2_FLASH,
        instruction="You are an agent that finds capital cities using the get_capital_city tool. Report the result clearly.",
        description="An LLM agent demonstrating after_tool_callback",
        tools=[capital_tool], # Add the tool
        after_tool_callback=simple_after_tool_modifier # Assign the callback
    )

APP_NAME = "guardrail_app"
USER_ID = "user_1"
SESSION_ID = "session_001"

# Session and Runner
session_service = InMemorySessionService()
session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
runner = Runner(agent=my_llm_agent, app_name=APP_NAME, session_service=session_service)


# Agent Interaction
async def call_agent(query):
  content = types.Content(role='user', parts=[types.Part(text=query)])
  events = runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

  async for event in events:
      if event.is_final_response():
          final_response = event.content.parts[0].text
          print("Agent Response: ", final_response)

await call_agent("united states")

Design Patterns and Best Practices for Callbacks¶
Callbacks offer powerful hooks into the agent lifecycle. Here are common design patterns illustrating how to leverage them effectively in ADK, followed by best practices for implementation.

Design Patterns¶
These patterns demonstrate typical ways to enhance or control agent behavior using callbacks:

1. Guardrails & Policy Enforcement¶
Pattern: Intercept requests before they reach the LLM or tools to enforce rules.
How: Use before_model_callback to inspect the LlmRequest prompt or before_tool_callback to inspect tool arguments. If a policy violation is detected (e.g., forbidden topics, profanity), return a predefined response (LlmResponse or dict/ Map) to block the operation and optionally update context.state to log the violation.
Example: A before_model_callback checks llm_request.contents for sensitive keywords and returns a standard "Cannot process this request" LlmResponse if found, preventing the LLM call.
2. Dynamic State Management¶
Pattern: Read from and write to session state within callbacks to make agent behavior context-aware and pass data between steps.
How: Access callback_context.state or tool_context.state. Modifications (state['key'] = value) are automatically tracked in the subsequent Event.actions.state_delta for persistence by the SessionService.
Example: An after_tool_callback saves a transaction_id from the tool's result to tool_context.state['last_transaction_id']. A later before_agent_callback might read state['user_tier'] to customize the agent's greeting.
3. Logging and Monitoring¶
Pattern: Add detailed logging at specific lifecycle points for observability and debugging.
How: Implement callbacks (e.g., before_agent_callback, after_tool_callback, after_model_callback) to print or send structured logs containing information like agent name, tool name, invocation ID, and relevant data from the context or arguments.
Example: Log messages like INFO: [Invocation: e-123] Before Tool: search_api - Args: {'query': 'ADK'}.
4. Caching¶
Pattern: Avoid redundant LLM calls or tool executions by caching results.
How: In before_model_callback or before_tool_callback, generate a cache key based on the request/arguments. Check context.state (or an external cache) for this key. If found, return the cached LlmResponse or result directly, skipping the actual operation. If not found, allow the operation to proceed and use the corresponding after_ callback (after_model_callback, after_tool_callback) to store the new result in the cache using the key.
Example: before_tool_callback for get_stock_price(symbol) checks state[f"cache:stock:{symbol}"]. If present, returns the cached price; otherwise, allows the API call and after_tool_callback saves the result to the state key.
5. Request/Response Modification¶
Pattern: Alter data just before it's sent to the LLM/tool or just after it's received.
How:
before_model_callback: Modify llm_request (e.g., add system instructions based on state).
after_model_callback: Modify the returned LlmResponse (e.g., format text, filter content).
before_tool_callback: Modify the tool args dictionary (or Map in Java).
after_tool_callback: Modify the tool_response dictionary (or Map in Java).
Example: before_model_callback appends "User language preference: Spanish" to llm_request.config.system_instruction if context.state['lang'] == 'es'.
6. Conditional Skipping of Steps¶
Pattern: Prevent standard operations (agent run, LLM call, tool execution) based on certain conditions.
How: Return a value from a before_ callback (Content from before_agent_callback, LlmResponse from before_model_callback, dict from before_tool_callback). The framework interprets this returned value as the result for that step, skipping the normal execution.
Example: before_tool_callback checks tool_context.state['api_quota_exceeded']. If True, it returns {'error': 'API quota exceeded'}, preventing the actual tool function from running.
7. Tool-Specific Actions (Authentication & Summarization Control)¶
Pattern: Handle actions specific to the tool lifecycle, primarily authentication and controlling LLM summarization of tool results.
How: Use ToolContext within tool callbacks (before_tool_callback, after_tool_callback).
Authentication: Call tool_context.request_credential(auth_config) in before_tool_callback if credentials are required but not found (e.g., via tool_context.get_auth_response or state check). This initiates the auth flow.
Summarization: Set tool_context.actions.skip_summarization = True if the raw dictionary output of the tool should be passed back to the LLM or potentially displayed directly, bypassing the default LLM summarization step.
Example: A before_tool_callback for a secure API checks for an auth token in state; if missing, it calls request_credential. An after_tool_callback for a tool returning structured JSON might set skip_summarization = True.
8. Artifact Handling¶
Pattern: Save or load session-related files or large data blobs during the agent lifecycle.
How: Use callback_context.save_artifact / await tool_context.save_artifact to store data (e.g., generated reports, logs, intermediate data). Use load_artifact to retrieve previously stored artifacts. Changes are tracked via Event.actions.artifact_delta.
Example: An after_tool_callback for a "generate_report" tool saves the output file using await tool_context.save_artifact("report.pdf", report_part). A before_agent_callback might load a configuration artifact using callback_context.load_artifact("agent_config.json").
Best Practices for Callbacks¶
Keep Focused: Design each callback for a single, well-defined purpose (e.g., just logging, just validation). Avoid monolithic callbacks.
Mind Performance: Callbacks execute synchronously within the agent's processing loop. Avoid long-running or blocking operations (network calls, heavy computation). Offload if necessary, but be aware this adds complexity.
Handle Errors Gracefully: Use try...except/ catch blocks within your callback functions. Log errors appropriately and decide if the agent invocation should halt or attempt recovery. Don't let callback errors crash the entire process.
Manage State Carefully:
Be deliberate about reading from and writing to context.state. Changes are immediately visible within the current invocation and persisted at the end of the event processing.
Use specific state keys rather than modifying broad structures to avoid unintended side effects.
Consider using state prefixes (State.APP_PREFIX, State.USER_PREFIX, State.TEMP_PREFIX) for clarity, especially with persistent SessionService implementations.
Consider Idempotency: If a callback performs actions with external side effects (e.g., incrementing an external counter), design it to be idempotent (safe to run multiple times with the same input) if possible, to handle potential retries in the framework or your application.
Test Thoroughly: Unit test your callback functions using mock context objects. Perform integration tests to ensure callbacks function correctly within the full agent flow.
Ensure Clarity: Use descriptive names for your callback functions. Add clear docstrings explaining their purpose, when they run, and any side effects (especially state modifications).
Use Correct Context Type: Always use the specific context type provided (CallbackContext for agent/model, ToolContext for tools) to ensure access to the appropriate methods and properties.
By applying these patterns and best practices, you can effectively use callbacks to create more robust, observable, and customized agent behaviors in ADK.