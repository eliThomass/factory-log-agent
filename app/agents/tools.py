from google.genai import types
import json
import os
from typing import Dict, Any, List
from google.adk.runners import Runner

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Build the path to the JSON file. 
# -> IF YOUR JSON IS IN THE SAME FOLDER AS tools.py:
MOCK_DB_PATH = os.path.join(CURRENT_DIR, "mock_factory.json")

async def call_agent_async(query: str, runner: Runner, user_id: str, session_id: str) -> None:
    print(f"\n>>> User Query: {query}")
    content = types.Content(role="user", parts=[types.Part(text=query)])
    final_response_text = "Agent did not produce a final response."

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate:
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"

    print(f"\n>>> Final Agent Response: {final_response_text}")

def check_inventory_alerts() -> Dict[str, Any]:
    """
    Scans the factory database for low inventory stock levels.
    
    Returns a structured summary containing a flag if action is needed,
    along with a detailed list of depleted items to pass to an LLM agent.
    """
    try:
        with open(MOCK_DB_PATH, 'r') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {
            "status": "ERROR",
            "message": f"Failed to read factory database: {str(e)}",
            "alerts_found": 0,
            "low_stock_items": []
        }
    
    inventory = data.get("inventory_stock", {})
    low_stock_items: List[Dict[str, Any]] = []
    
    # Iterate through inventory entries to catch items marked "LOW"
    for item_id, item_details in inventory.items():
        if item_details.get("status") == "LOW":
            low_stock_items.append({
                "sku": item_id,
                "name": item_details.get("name"),
                "current_quantity": item_details.get("quantity"),
                "unit": item_details.get("unit")
            })
            
    # Determine critical severity based on findings
    action_required = len(low_stock_items) > 0
    
    return {
        "status": "SUCCESS",
        "action_required": action_required,
        "alerts_found": len(low_stock_items),
        "low_stock_items": low_stock_items
    }

def check_bottleneck(line_id: str) -> Dict[str, Any]:
    """
    Identifies the primary bottleneck station for a specific assembly line
    based on the highest queue count and lowest design capacity.
    """
    try:
        with open(MOCK_DB_PATH, 'r') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"status": "ERROR", "message": str(e)}

    # Find the requested assembly line
    target_line = next((line for line in data.get("assembly_lines", []) if line["line_id"] == line_id), None)
    
    if not target_line:
        return {"status": "ERROR", "message": f"Assembly line '{line_id}' not found."}

    stations = target_line.get("stations", [])
    if not stations:
        return {"status": "SUCCESS", "message": f"Line {line_id} has no active stations.", "bottleneck_detected": False}

    # Find the bottleneck: sorting by highest queue count, breaking ties with lowest hourly capacity
    bottleneck_station = max(stations, key=lambda s: (s["current_queue_count"], -s["max_capacity_per_hour"]))

    return {
        "status": "SUCCESS",
        "line_id": line_id,
        "line_name": target_line["name"],
        "bottleneck_detected": bottleneck_station["current_queue_count"] > 10 or bottleneck_station["status"] != "OPERATIONAL",
        "bottleneck_station": {
            "station_id": bottleneck_station["station_id"],
            "name": bottleneck_station["name"],
            "current_status": bottleneck_station["status"],
            "current_queue": bottleneck_station["current_queue_count"],
            "cycle_time_seconds": bottleneck_station["cycle_time_seconds"],
            "max_capacity_per_hour": bottleneck_station["max_capacity_per_hour"]
        },
        "recommendation": f"Station {bottleneck_station['station_id']} ({bottleneck_station['name']}) is restricting flow with {bottleneck_station['current_queue_count']} units backed up."
    }
import json
from typing import Dict, Any, List

def calculate_throughput() -> Dict[str, Any]:
    """
    Calculates the throughput efficiency percentage for every assembly line in the factory.
    Provides a comprehensive overview of current vs target outputs and flags lines 
    operating below an 80% threshold.
    """
    try:
        with open(MOCK_DB_PATH, 'r') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"status": "ERROR", "message": f"Failed to read factory database: {str(e)}"}

    lines_report: List[Dict[str, Any]] = []
    underperforming_count = 0
    lines = data.get("assembly_lines", [])

    for line in lines:
        target = line.get("target_output_per_hour", 1)  # Avoid division by zero
        current = line.get("current_output_per_hour", 0)
        
        # Calculate throughput efficiency percentage
        efficiency = round((current / target) * 100, 1)
        is_underperforming = efficiency < 80.0
        
        if is_underperforming:
            underperforming_count += 1

        # Gather any immediate bottleneck details if the line is struggling
        culprit_stations = []
        if is_underperforming:
            culprit_stations = [
                {
                    "station_id": s["station_id"],
                    "name": s["name"],
                    "status": s["status"],
                    "queue_count": s["current_queue_count"]
                }
                for s in line.get("stations", [])
                if s["status"] != "OPERATIONAL" or s["current_queue_count"] > 15
            ]

        lines_report.append({
            "line_id": line["line_id"],
            "name": line["name"],
            "status": line["status"],
            "current_output": current,
            "target_output": target,
            "throughput_percentage": efficiency,
            "underperforming": is_underperforming,
            "suspected_constraints": culprit_stations
        })

    return {
        "status": "SUCCESS",
        "factory_id": data.get("factory_metadata", {}).get("factory_id"),
        "total_lines_monitored": len(lines_report),
        "underperforming_lines_count": underperforming_count,
        "summary": lines_report
    }
