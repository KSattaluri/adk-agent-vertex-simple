# API Overview

## Direct Flow (Primary Path)

  1. User submits a question through the UI
  2. UI sends a request to the FastAPI endpoint /api/chat/stream
  3. FastAPI forwards the request to the agent with validated inputs
  4. Agent processes the request and streams back status updates and the final response
  5. FastAPI receives the final response, validates it with FinalResponse.model_validate()
  6. FastAPI converts it to a UI-friendly format using prepare_ui_response_from_model()
  7. FastAPI stores the validated response in Firebase/Firestore
  8. FastAPI sends the UI-compatible response directly to the client via the streaming response
  9. UI receives the response and displays it to the user

## API Endpoints

| FastAPI Backend Endpoints             | Agent API Endpoints                                            |
|---------------------------------------|---------------------------------------------------------------|
| `/login`                              | `/apps/refiner_agent/users/{user_id}/sessions/{session_id}`    |
| `/logout`                             | `/run_sse`                                                     |
| `/auth/session`                       | `/run`                                                         |
| `/`                                   | `/`                                                            |
| `/api/chat/stream`                    |                                                               |
| `/api/history`                        |                                                               |
| `/api/responses/{response_id}`        |                                                               |
| `/api/auth-status`                    |                                                               |
| `/health`                             |                                                               |

## Pydantic Models

The application uses Pydantic models for data validation and serialization throughout the workflow:

### Core Data Models (schemas.py)

#### **OrchestratorInput**
- Input schema for the orchestrator agent
- Fields: `role`, `industry`, `question`, `resume` (optional), `jobDescription` (optional)

#### **STARResponse** 
- STAR format interview responses
- Fields: `situation`, `task`, `action`, `result`
- All fields default to "Not provided"

#### **Critique**
- STAR answer critiques and feedback
- Fields:
  - `rating`: Float (1.0-5.0) - Overall numerical rating
  - `structureFeedback`: Feedback on STAR structure adherence
  - `relevanceFeedback`: Feedback on relevance to role/industry/question
  - `specificityFeedback`: Feedback on concrete details and metrics
  - `professionalImpactFeedback`: Feedback on professionalism and impact
  - `suggestions`: List of 2-3 actionable improvement suggestions
  - `rawCritiqueText`: Internal field for full critique text
  - `feedback`: Overall feedback summary

#### **IterationData**
- Data for a single iteration of the STAR generation process
- Fields: `iterationNumber`, `starAnswer` (STARResponse), `critique` (Critique), `timestamp`

#### **PerformanceMetrics**
- Timing metrics for the workflow
- Fields: `totalWorkflowTime`, `generationTime`, `critiqueTimes` (list), `refinementTimes` (list)

#### **ResponseMetadata**
- Metadata for the STAR answer generation response
- Fields: `role`, `industry`, `question`, `resume`, `jobDescription`, `status`, `createdAt`, `userId`

#### **FinalResponse**
- Complete response from the STAR answer generation process
- Fields: `metadata` (ResponseMetadata), `iterations` (List[IterationData]), `performanceMetrics`
- Includes utility method `get_best_star_answer()` to find highest rated iteration

### FastAPI Request Models

#### **STARRequest** (fastapi_backend/main.py)
- Input validation for chat stream requests
- Fields: `role`, `industry`, `question`, `resume` (optional), `jobDescription` (optional)
- Includes length validation constraints

#### **SessionRequest** (fastapi_backend/main.py)
- Session creation request validation
- Fields: `token` (optional), `idToken` (optional)

#### **User** (fastapi_backend/auth.py)
- User authentication model
- Fields: `uid`, `email`, `name`

### Data Flow
1. **Input**: `STARRequest` → validated and converted to `OrchestratorInput`
2. **Processing**: Agent generates `STARResponse` and `Critique` objects per iteration
3. **Storage**: Each iteration stored as `IterationData` with timing in `PerformanceMetrics`
4. **Output**: Final validated `FinalResponse` converted to UI-compatible format


Codebase doesn't directly instantiate InMemorySessionService, VertexAiSessionService, or DatabaseSessionService.  Instead, we're using ADK's built-in session management through the get_fast_api_app() function:.
When you call get_fast_api_app() with session_service_uri, ADK automatically:
  Creates a DatabaseSessionService using the SQLite URL you provided
  Sets up the session management infrastructure
  Handles session lifecycle (create, get, update, delete)
  Manages session state and event history
  Provides REST endpoints for session operations

agents access session data through the InvocationContext
Main state keys used in the orchestrator:

  Core Input Data

  - role: Job role for STAR answer
  - industry: Industry sector
  - question: Interview question
  - resume: Optional resume text
  - job_description: Optional job description text

  User Information

  - user_id: User identifier
  - user_email: User's email
  - user_name: User's name
  - userId: Same as user_id (alternate naming)
  - userEmail: Same as user_email (alternate naming)
  - userName: Same as user_name (alternate naming)

  Processing State

  - currentIteration: Current iteration number
  - highestRating: Highest rating achieved
  - finalStatus: Status of the process (IN_PROGRESS, COMPLETED_*)
  - finalRating: Final rating value
  - fullIterationHistory: Array of iteration data

  Agent Output Keys

  - current_answer: Current STAR answer (likely set by generator agent)
  - critique_feedback: Feedback from critique agent
  - timing_data: Performance timing metrics

  Agent Context

  - task: The task being performed ("generate_star_answer")
  - timestamp: When the processing started


  FullIterationHistory: Array of iteration data
[
  {
    "iterationNumber": ...,
    "starAnswer": {
      "situation": "...",
      "task": "...",
      "action": "...",
      "result": "..."
    },
    "critique": {
      "rating": ...,
      "structureFeedback": "...",
      "relevanceFeedback": "...",
      "specificityFeedback": "...",
      "professionalImpactFeedback": "...",
      "suggestions": [...],
      "rawCritiqueText": "...",
      "feedback": "..."
    },
    "timestamp": "..."
  },
  ...
]