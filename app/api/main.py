import os
import signal
import json
import asyncio
from contextlib import asynccontextmanager

# 1. LOAD ENVIRONMENT VARIABLES IMMEDIATELY
from dotenv import load_dotenv
load_dotenv()
print("main.py: 1. LOAD ENVIRONMENT VARIABLES IMMEDIATELY")

from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Google ADK Imports 
from app.agents.agent import make_sub_agents
from app.api.schemas import AgentResponse, UserMessage
from google.adk.sessions import InMemorySessionService
from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.genai import types

app = FastAPI(
    title="Factory Automation Agent API",
    description="Backend API for interacting with the Root Coordinator and Specialized Factory Sub-Agents.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

APP_NAME = "factory_log_app"
session_service = InMemorySessionService()
DEFAULT_USER_ID = "shop_floor_operator"

# ---------------------------------------------------------
# Pydantic Schemas for Request / Response Validation
# ---------------------------------------------------------


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

def silence_adk_bug_handler(loop, context):
    """Intercepts unhandled asyncio exceptions to hide the known google-genai teardown bug."""
    exception = context.get("exception")
    if isinstance(exception, AttributeError) and "_async_httpx_client" in str(exception):
        # We know about this bug. Do nothing and keep the terminal clean.
        pass
    else:
        # If it's a real, different error, let the default handler print it.
        loop.default_exception_handler(context)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply our custom bug silencer to the active event loop when the server starts
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(silence_adk_bug_handler)
    yield
    # Optional: Keep the Windows Ctrl+C fix from before
    os.kill(os.getpid(), signal.SIGTERM)

@app.get("/health", tags=["System"])
async def health_check():
    """
    Basic health probe to ensure the API layer is operational.
    """
    return {"status": "ONLINE", "database_connected": True}

import json

@app.post(
    "/agent/chat", 
    response_model=AgentResponse, 
    status_code=status.HTTP_200_OK,
    tags=["Agent Core"]
)
async def process_agent_request(payload: UserMessage):
    try:
        user_input = payload.text
        session_id = payload.session_id
        print("main.py: Safely Fetch or Create the Session")
        
        # Safely Fetch or Create the Session
        try:
            # Add 'await' and include 'user_id' so it doesn't throw a TypeError
            session_state = await session_service.get_session(
                app_name=APP_NAME, 
                user_id=DEFAULT_USER_ID, 
                session_id=session_id
            )
        except Exception:
            # If the ADK explicitly raises a 'not found' exception, catch it gracefully
            session_state = None

        # Only create the session if it actually returned empty
        if not session_state:
            print("main.py: Creating new session")
            initial_state = {"factory_db_path": "factory_db.json"}
            session_state = await session_service.create_session(
                app_name=APP_NAME, 
                user_id=DEFAULT_USER_ID, 
                session_id=session_id, 
                state=initial_state
            )

        pipeline_agent = SequentialAgent(
            name="root_coordinator",
            description="Central agent that coordinates specialized sub-agents for factory log analysis.",
            sub_agents=make_sub_agents()
        )
        
        # FIX 1: Initialize the ADK Runner to orchestrate the agent
        print("main.py: FIX 1: Initialize the ADK Runner to orchestrate the agent")
        runner = Runner(
            agent=pipeline_agent,
            session_service=session_service,
            app_name=APP_NAME
        )
        
        # FIX 2: Wrap the user's string in ADK's native Content schema
        print("main.py: FIX 2: Wrap the user's string in ADK's native Content schema")
        user_msg = types.Content(role="user", parts=[types.Part(text=user_input)])
        
        # 3. Fire the execution pipeline via the Runner
        print("main.py: 3. Fire the execution pipeline via the Runner")
        final_output_text = None
        
        # runner.run_async yields an event stream, so we loop through it to catch the final response
        async for event in runner.run_async(
            user_id=DEFAULT_USER_ID,
            session_id=session_id,
            new_message=user_msg
        ):
            if event.is_final_response():
                print("main.py: Received final response from Runner")
                final_output_text = event.content.parts[0].text
                
        if not final_output_text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The agent pipeline finished but no final text was yielded."
            )
        
        # 4. Parse the strict JSON string coming out of json_agent
        print("main.py: 4. Parse the strict JSON string coming out of json_agent")
        try:
            structured_json = json.loads(final_output_text)
            print("main.py: Successfully parsed JSON output")
            return structured_json
        except (json.JSONDecodeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The agent pipeline finished but failed to generate a parseable JSON object."
            ) 

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) 