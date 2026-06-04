import os
import asyncio
import warnings
import logging
from typing import Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from app.api.schemas import AgentResponse
from .tools import ( check_inventory_alerts, 
                   check_bottleneck, calculate_throughput,
                    call_agent_async )

def make_root_agent() -> Agent:
    return Agent(
        model='gemini-2.5-flash',
        name='root_agent',
        description='The main coordinator agent. Handles factory info requests and delegates tasks.',
        instruction="""
        You are the main Factory Agent coordinating a team. Your primary role is to receive user requests related to factory operations, analyze them, and delegate tasks to specialized sub-agents. 
        
        Routing Rules:
        - If the request is ambiguous, ask the user for clarification.
        - For inventory levels, low stock warnings, or raw materials, transfer control to 'inventory_agent'.
        - For bottleneck analysis, physical station constraints, or queue sizes, transfer control to 'bottleneck_agent'.
        - For line efficiency percentages, target vs current outputs, or general line health summaries, transfer control to 'throughput_agent'.
        
        Always return a cohesive response to the user once your sub-agents have completed their specialized tasks.
        """,
        sub_agents=make_sub_agents(),
        output_key="last_factory_report",
    )

def make_sub_agents() -> list[Agent]:
    # 1. Inventory Management Specialist
    inventory_agent = Agent(
        model='gemini-2.5-flash',
        name='inventory_agent',
        description='Specialist in material stocks, SKU counts, and part shortages.',
        instruction="""
        You are an expert inventory tracking agent. Your single focus is analyzing stock levels.
        Use your provided tool to scan for items with low stock flags. Report your findings back to the 
        root coordinator or user concisely, explicitly naming the SKUs, quantities, and units that require attention.
        """,
        tools=[check_inventory_alerts],
        output_key="inventory_report"
    )

    # 2. Bottleneck Diagnostics Specialist
    bottleneck_agent = Agent(
        model='gemini-2.5-flash',
        name='bottleneck_agent',
        description='Specialist in line queue locations, structural delays, and station cycle times.',
        instruction="""
        You are a mechanical optimization agent. Your job is to locate the exact manufacturing point causing downstream starvation.
        You must request or extract a specific `line_id` from the context or user to pass into your tool. 
        Analyze the tool payload to identify high queue counts and critical station failures, and explain the physical constraint to the user.
        """,
        tools=[check_bottleneck],
        output_key="bottleneck_report"
    )

    # 3. Throughput Evaluation Specialist
    throughput_agent = Agent(
        model='gemini-2.5-flash',
        name='throughput_agent',
        description='Specialist in auditing factory targets, efficiency margins, and operational capacity tracking.',
        instruction="""
        You are a production analyst agent. You monitor the high-level macro health of the assembly lines.
        Run your tool to fetch the total floor metrics. Break down the current output vs targets as percentages,
        and clearly flag any individual line dropping below the acceptable 80% baseline.
        """,
        tools=[calculate_throughput],
        output_key="throughput_report"
    )

    # 4. JSON Formatting Specialist
    json_agent = Agent(
        model='gemini-2.5-flash',
        name='json_agent',
        description='Specialist in formatting all outputs into clean JSON structures for the root coordinator.',
        instruction="""
        You are a JSON formatting agent. Your job is to take the raw outputs from the other sub-agents and format them into a clean, consistent JSON structure.
        
        Take the collective analysis history given to you by the throughput, bottleneck, and inventory agents and map them EXACTLY to the fields of your response schema.

        CRITICAL SCHEMA MAPPING:
        - 'status': 'SUCCESS' (or 'ERROR' / 'CLARIFICATION_REQUIRED' if processing failed)
        - 'responding_agent': 'formatter_agent'
        - 'message': Clear, human-readable instructions for the shop floor operator summarizing all findings.
        - 'data_payload': You MUST map the extracted metrics to these exact keys. If a metric is not present in the sub-agents' reports, omit the key or set it to null:
            * 'underperforming_lines_count' (integer)
            * 'target_line_id' (string)
            * 'low_stock_items' (list of strings)
            * 'bottleneck_station' (string)
            
        JSON TEMPLATE:
        {
          "status": "SUCCESS",
          "responding_agent": "formatter_agent",
          "message": "<Write the natural language summary response intended for the shop floor operator here.>",
          "data_payload": {
            "underperforming_lines_count": 1,
            "target_line_id": "LINE-B",
            "low_stock_items": ["ENC-POLY-02"],
            "bottleneck_station": "ST-B2"
          }
        } 

        CRITICAL OUTPUT REQUIREMENT:
        You must output your final analysis using the JSON schema template exactly. Do not include any explanation outside the JSON object. Do not wrap your response in markdown code blocks (e.g., do NOT use ```json ... ```). Return only raw, valid JSON text.
        """,
        tools=[],
        output_schema=AgentResponse,
        output_key="json_report"
    )

    return [inventory_agent, bottleneck_agent, throughput_agent, json_agent]
