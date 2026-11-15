"""Studio entry. Arm D: supervisor, challenger, verifier, committee.

LangGraph API rejects a graph that already carries a checkpointer. Studio
supplies persistence. Local runs pass the SQLite saver explicitly.
"""

from risk_desk.graphs.workflows import build_desk_graph

graph = build_desk_graph(checkpointer=None)
