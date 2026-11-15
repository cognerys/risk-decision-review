"""Opt-in Studio entry for the bounded specialist/challenger research graph.

Studio owns checkpointing. Model calls stay scripted unless RISK_DESK_LIVE is
enabled in the effective process environment. Each completed invocation uses
five role calls; use the study runner for campaign-wide budgets and provenance.
"""

from risk_desk.graphs.specialists import build_research_graph

graph = build_research_graph("challenged", checkpointer=None)
