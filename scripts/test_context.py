import json
from src.agents.briefing import _build_context

ctx = _build_context("2023-10-01")
print(json.dumps(ctx, indent=2))
