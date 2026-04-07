import os
import re
from collections import defaultdict, deque
from anthropic import Anthropic
from dotenv import load_dotenv
from state import state

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a robot task planner for a Franka Panda robot.
The robot has 4 cubes: red, green, yellow, and blue.
Your job is to translate natural language instructions into LTL (Linear Temporal Logic) formulas.

Output your LTL formula on its own line in this exact format:
LTL: <formula>

Use these predicates:
- pick_X  : the robot picks up cube X
- place_X : the robot places cube X in the bin

Always include for each cube X in the plan:
- F(pick_X) ∧ F(place_X)       — eventually pick and place it
- (¬place_X U pick_X)          — must pick before placing

For ordering (cube A must be placed before cube B is picked):
- (¬pick_B U place_A)

Rules:
- Only include cubes the user specifies; if none specified, include all 4
- Respond conversationally in 1-2 sentences, then output the LTL line
- Do NOT explain the LTL line"""


def send_message(user_message: str) -> tuple[str, list, str]:
    """Send message to Claude. Returns (display_text, plan_list, ltl_str)."""
    state.conversation_history.append({
        "role": "user",
        "content": user_message,
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=state.conversation_history,
    )

    raw = response.content[0].text
    state.conversation_history.append({
        "role": "assistant",
        "content": raw,
    })

    ltl  = _extract_ltl(raw)
    plan = _ltl_to_plan(ltl) if ltl else []
    display = re.sub(r'\nLTL:.*', '', raw).strip()
    display = re.sub(r'LTL:.*', '', display).strip()

    return display, plan, ltl


def _extract_ltl(text: str) -> str:
    """Pull the LTL formula string from the LLM response."""
    match = re.search(r'LTL:\s*(.+)', text)
    return match.group(1).strip() if match else ""


def _ltl_to_plan(ltl: str) -> list:
    """Derive an ordered execution plan from an LTL formula.

    Extracts cubes from F(pick_X) predicates, then reads ordering constraints
    of the form (¬pick_B U place_A) — meaning A must be placed before B is
    picked — and topologically sorts to produce the sequence.
    """
    valid = {"red", "green", "yellow", "blue"}

    # Cubes present in plan
    cubes = [c for c in re.findall(r'F\(pick_(\w+)\)', ltl) if c in valid]
    cubes = list(dict.fromkeys(cubes))  # deduplicate, preserve order
    if not cubes:
        return []

    # Ordering edges: (¬pick_B U place_A)  →  A before B
    edges     = defaultdict(list)
    in_degree = defaultdict(int, {c: 0 for c in cubes})

    for B, A in re.findall(r'¬pick_(\w+)\s+U\s+place_(\w+)', ltl):
        if A in in_degree and B in in_degree and B not in edges[A]:
            edges[A].append(B)
            in_degree[B] += 1

    # Kahn's topological sort
    queue  = deque(c for c in cubes if in_degree[c] == 0)
    result = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for nb in edges[node]:
            in_degree[nb] -= 1
            if in_degree[nb] == 0:
                queue.append(nb)

    # Fall back to original order if something went wrong (e.g. cycle)
    return result if len(result) == len(cubes) else cubes
