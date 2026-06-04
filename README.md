# factory-log-agent

factory-log-agent is a FastAPI-based backend for a factory operations assistant built with Google ADK. It exposes an API that receives user requests, creates or retrieves session state, and delegates the request to a root agent for processing.

## Project structure

- `app/`
  - `api/main.py` - FastAPI application entry point and request handling logic.
  - `api/schemas.py` - Pydantic models for request and response validation.
  - `agents/agent.py` - Agent creation and coordination logic.
  - `agents/tools.py` - Domain-specific helper functions used by the agents.

## Requirements

- Python 3.11+ (or the version compatible with the installed dependencies)
- `uvicorn`
- `fastapi`
- `google.adk` and related Google ADK dependencies

Install dependencies in a virtual environment before running the app.

## Running the application

From the project root directory, run:

```bash
uvicorn app.api.main:app --reload
```

This starts the FastAPI server with automatic reload enabled.

## API endpoints

- `GET /health` - Basic health check.
- `POST /agent/chat` - Send a message to the agent and receive a structured response.

## Notes

- Ensure your Python environment can resolve the `app` package by running from the repository root.
