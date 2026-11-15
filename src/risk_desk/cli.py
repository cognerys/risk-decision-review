"""Command line. Runs stay offline unless live mode is enabled; probe is explicit."""

from __future__ import annotations

import argparse
import json
import sys

from risk_desk.config import Settings
from risk_desk.llm import reasoning_note_for


def _show_config() -> int:
    settings = Settings.from_env()
    print(f"model={settings.model}")
    print(f"live={'true' if settings.live else 'false'}")
    print(f"reasoning_note={reasoning_note_for(settings)}")
    return 0


def _run(card_id: str, arm: str) -> int:
    from risk_desk.graphs.review import build_research_graph

    # Each batch run is an independent review: no checkpointer, no inherited state.
    graph = build_research_graph(arm, checkpointer=None)
    result = graph.invoke({"card_id": card_id, "arm": arm}, config={"recursion_limit": 30})
    print(json.dumps(result["recommendation"]))
    if result["verification"].get("fallback"):
        print("note: the proposal failed a check, so this is the deterministic scorecard's action", file=sys.stderr)
    return 0


def _scorecard(card_id: str) -> int:
    from risk_desk.data.cards import load_card
    from risk_desk.engine.score import scorecard

    try:
        card = load_card(card_id)
    except KeyError:
        print(f"unknown card {card_id}", file=sys.stderr)
        return 1
    print(scorecard(card).model_dump_json())
    return 0


def _view(port: int) -> int:
    from risk_desk.viewer.server import serve

    serve(port)
    return 0


def _probe() -> int:
    from risk_desk.llm import probe_model

    settings = Settings.from_env()
    try:
        probe_model(settings)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"probe_ok model={settings.model}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="risk-desk")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show-config")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--card", required=True)
    run_parser.add_argument("--arm", default="challenged", choices=("single", "specialists", "challenged", "self_review"),
                            help="Review configuration (default: challenged)")
    score_parser = sub.add_parser("scorecard")
    score_parser.add_argument("card_id")
    view_parser = sub.add_parser("view")
    view_parser.add_argument("--port", type=int, default=8765)
    sub.add_parser("probe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--probe"]:
        args = ["probe"]
    namespace = _parser().parse_args(args)
    if namespace.command == "show-config":
        return _show_config()
    if namespace.command == "run":
        return _run(namespace.card, namespace.arm)
    if namespace.command == "scorecard":
        return _scorecard(namespace.card_id)
    if namespace.command == "view":
        return _view(namespace.port)
    if namespace.command == "probe":
        return _probe()
    return 2


if __name__ == "__main__":
    sys.exit(main())
