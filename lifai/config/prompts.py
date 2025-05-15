"""
Prompt configuration and loader for LifAi2.

Prompts are now managed via JSON in lifai/modules/prompt_editor/prompts.json.
This file provides runtime loading utilities and maintains backward compatibility
for system/default prompts and legacy code. All prompt editing and ordering should
be performed via the Prompt Editor UI and JSON file.

Functions:
    - load_all_prompts: Load all prompts from JSON as a list of dicts.
    - get_prompt_dict_by_name: Return a dict mapping prompt names to prompt data.
    - get_prompt_order: Return the current prompt order (list of UUIDs).
Variables:
    - llm_prompts: Dict of prompts keyed by name (for backward compatibility).
    - system_prompts: List of system-level prompts (optional).
    - prompt_order: List of prompt UUIDs in order.
"""

import os
import json

PROMPTS_JSON = os.path.join(os.path.dirname(__file__), "../modules/prompt_editor/prompts.json")

def load_all_prompts():
    """Load all prompts from the JSON file as a list of dicts."""
    if not os.path.exists(PROMPTS_JSON):
        return []
    with open(PROMPTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("prompts", [])

def get_prompt_dict_by_name():
    """Return a dict mapping prompt names to prompt data."""
    prompts = load_all_prompts()
    return {p["name"]: p for p in prompts}

# For backward compatibility, provide llm_prompts as a dict keyed by name
llm_prompts = get_prompt_dict_by_name()

# Optionally, define system/default prompts here if needed
system_prompts = []  # Add any system-level prompts if required

# Prompt order (list of UUIDs)
def get_prompt_order():
    if not os.path.exists(PROMPTS_JSON):
        return []
    with open(PROMPTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("order", [])

prompt_order = get_prompt_order()

def reload_prompts():
    """Reload prompts from the JSON file and update global variables."""
    global llm_prompts, prompt_order
    llm_prompts = get_prompt_dict_by_name()
    prompt_order = get_prompt_order()
    return llm_prompts, prompt_order
