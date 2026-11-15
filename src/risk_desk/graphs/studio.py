"""LangGraph Studio entry: the challenged review configuration.

Studio owns checkpointing. Model calls stay scripted unless RISK_DESK_LIVE is
enabled in the process environment. Each completed run makes five model calls.
Use experiments/run_study.py for a study with a call cap and full records.
"""

from risk_desk.graphs.review import build_research_graph

graph = build_research_graph("challenged", checkpointer=None)
