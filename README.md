# STAR Interview Answer Generator

An AI agent system built with Google's Agent Development Kit (ADK) that generates and refines STAR format interview answers through multi-agent workflows.

## Architecture

**2-Tier System**: FastAPI Backend + ADK Agent
- **Frontend**: Web UI with Firebase authentication and real-time streaming  
- **Backend**: ADK multi-agent workflow (Generator → Critique → Refiner)

```
User → FastAPI Backend → ADK Agent → Subagents → Iterative Refinement → Response
```

## Highlights

- **Google Cloud Integration**: Utilizes Vertex AI and Cloud Run for scalable deployment
- **Custom ADK Orchestrator**: Demonstrates advanced agent composition with session and state management
- **Type Safety**: Full Pydantic validation throughout the workflow
- **Real-time Streaming**: Live progress updates with Server-Sent Events
- **Multi-deployment Options**: Local development, Cloud Run, or Agent Engine deployment


## Project Structure

```
├── app.py                    # Unified entry point (local/Cloud Run)
├── fastapi_backend/          # Web interface & authentication
├── refiner_agent/            # Core ADK agent implementation
├── shared_utils/             # Common utilities
├── schemas.py                # Pydantic data models
├── pyproject.toml           # Dependencies & scripts
├── Dockerfile               # Cloud Run deployment
└── project_setup.md         # Setup instructions
```

### Key Components

#### **`fastapi_backend/`** - Web Backend
- `main.py` - FastAPI app with streaming endpoints
- `auth.py` - Firebase authentication
- `cloud_run_agent.py` - HTTP client for remote agents
- `static/` - Web UI (HTML/CSS/JS)

#### **`refiner_agent/`** - ADK Agent
- `agent.py` - Root agent orchestrator  
- `orchestrator.py` - Multi-agent workflow coordinator
- `subagents/` - Specialized agents:
  - `generator/` - Creates initial STAR answers
  - `critique/` - Evaluates with ratings (1-5 scale)
  - `refiner/` - Improves based on feedback
- `adk.yaml` - ADK configuration

#### **Root Files**
- `app.py` - Auto-detecting entry point (local vs Cloud Run)
- `schemas.py` - Shared Pydantic models for data validation
- `pyproject.toml` - Poetry deps + scripts (`fast-local`, `fast-remote`)

## Deployment Options
See project_setup.md for setup and deployment steps.

## Features

- **Multi-Agent Workflow**: Generator → Critique → Refiner with quality thresholds
- **Real-Time Streaming**: Live progress updates during processing
- **Firebase Integration**: User authentication and response storage
- **Flexible Deployment**: Local, Cloud Run, or Agent Engine options
- **Session Management**: ADK's built-in session handling with SQLite
- **Quality Assurance**: Iterative refinement until rating threshold (4.6/5.0)

## Quick Start

1. **Setup**: Follow [project_setup.md](project_setup.md) for complete configuration
2. **Install**: `poetry install`
3. **Configure**: Copy `.env.example` to `.env` and update values
4. **Access**: http://localhost:5005/login

## Monitoring

- **Health Check**: `/health` endpoint
- **Logs**: Cloud Logging (for Cloud Run deployments)
- **Real-time**: Status updates via Server-Sent Events