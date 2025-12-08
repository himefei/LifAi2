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
from typing import Dict, List, Tuple, Optional

PROMPTS_JSON = os.path.join(os.path.dirname(__file__), "../modules/prompt_editor/prompts.json")

# Cache for prompts data to avoid repeated file I/O
_prompts_cache: Optional[Dict] = None
_cache_mtime: Optional[float] = None

def _load_prompts_data() -> Dict:
    """Load prompts data from JSON file with caching."""
    global _prompts_cache, _cache_mtime
    
    if not os.path.exists(PROMPTS_JSON):
        return {"prompts": [], "order": []}
    
    # Check if file has been modified since last cache
    current_mtime = os.path.getmtime(PROMPTS_JSON)
    
    if _prompts_cache is None or _cache_mtime is None or current_mtime != _cache_mtime:
        with open(PROMPTS_JSON, "r", encoding="utf-8") as f:
            _prompts_cache = json.load(f)
        _cache_mtime = current_mtime
    
    return _prompts_cache

def load_all_prompts() -> List[Dict]:
    """Load all prompts from the JSON file as a list of dicts (cached)."""
    data = _load_prompts_data()
    return data.get("prompts", [])

def get_prompt_dict_by_name() -> Dict[str, Dict]:
    """Return a dict mapping prompt names to prompt data (cached)."""
    prompts = load_all_prompts()
    return {p["name"]: p for p in prompts}

def get_prompt_order() -> List[str]:
    """Return the current prompt order (list of UUIDs) (cached)."""
    data = _load_prompts_data()
    return data.get("order", [])

# For backward compatibility, provide llm_prompts as a dict keyed by name
llm_prompts = get_prompt_dict_by_name()

# Optionally, define system/default prompts here if needed
system_prompts = []  # Add any system-level prompts if required

# Prompt order (list of UUIDs)
prompt_order = get_prompt_order()

def reload_prompts() -> Tuple[Dict[str, Dict], List[str]]:
    """Reload prompts from the JSON file and update global variables."""
    global llm_prompts, prompt_order, _prompts_cache, _cache_mtime
    
    # Invalidate cache to force reload
    _prompts_cache = None
    _cache_mtime = None
    
    llm_prompts = get_prompt_dict_by_name()
    prompt_order = get_prompt_order()
    return llm_prompts, prompt_order
