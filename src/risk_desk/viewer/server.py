"""Local page that draws each review configuration and can run one card through it."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from risk_desk.data.cards import card_ids
from risk_desk.graphs.review import ARMS, build_research_graph
from risk_desk.viewer.graph_view import describe

_PAGE_PATH = Path(__file__).resolve().parent / "index.html"


def _page() -> bytes:
    return _PAGE_PATH.read_text(encoding="utf-8").encode()


def _fmt(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.0f}" if abs(value) >= 10 else f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, dict):
        return ", ".join(f"{key} {_fmt(item)}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _proposal_line(proposal: dict | None) -> str:
    proposal = proposal or {}
    return f"{proposal.get('action_or_abstain') or 'no usable reply'} — {proposal.get('reason') or 'no reason given'}"


def _lines_from(name: str, payloads: list[dict]) -> list[str]:
    last = payloads[-1] if payloads else {}
    if name == "evidence":
        bundle = last.get("evidence_bundle") or {}
        feasible = [item["action"] for item in bundle.get("actions", []) if item.get("feasible")]
        return [f"{len(bundle.get('evidence', {}))} evidence rows", "feasible: " + ", ".join(feasible)]
    if name in {"market_physical", "credit_governance"}:
        report = (last.get("specialist_reports") or [{}])[-1]
        validation = report.get("validation") or {}
        admitted = validation.get("admitted_findings", validation.get("admitted"))
        lines = [f"report {'admitted' if validation.get('accepted', validation.get('pass')) else 'not admitted'}"]
        if admitted is not None:
            lines.append(f"findings passed on: {_fmt(admitted)}")
        return lines
    if name == "propose":
        return ["proposal: " + _proposal_line(last.get("proposal"))]
    if name == "challenge":
        challenge = last.get("challenge") or {}
        return [f"usable challenge: {_fmt(bool(challenge.get('usable')))}",
                f"asks for revision: {_fmt(bool(challenge.get('requires_revision')))}"]
    if name in {"revise", "self_review"}:
        return [f"pass {len(payloads)}: " + _proposal_line(last.get("proposal"))]
    if name == "verify":
        verification = last.get("verification") or {}
        recommendation = last.get("recommendation") or {}
        return [f"checks passed: {_fmt(bool(verification.get('primary_contract_pass')))}",
                f"fell back to scorecard: {_fmt(bool(verification.get('fallback')))}",
                f"final: {recommendation.get('action_or_abstain')} — {recommendation.get('reason')}"]
    return []


def _evidence_rows(bundle: dict, action: str | None) -> list[dict]:
    """The figures behind the final action, for the page's evidence table."""
    card_id = (bundle.get("card") or {}).get("card_id")
    evidence = bundle.get("evidence") or {}
    target = action if action and f"{card_id}:action:{action}:utility" in evidence else "hold"
    rows = []
    for field in ("utility", "var_95", "cvar_95", "stress_loss", "liquidity_cost", "governance_penalty"):
        value = evidence.get(f"{card_id}:action:{target}:{field}")
        if isinstance(value, (int, float)):
            rows.append({"kind": f"{target} {field}", "units": "EUR", "value": value})
    return rows


def run_arm(arm: str, card_id: str, *, live: bool) -> dict:
    if arm not in ARMS:
        raise KeyError(arm)
    if card_id not in card_ids():
        raise KeyError(card_id)
    previous = os.environ.get("RISK_DESK_LIVE")
    os.environ["RISK_DESK_LIVE"] = "1" if live else "0"
    try:
        graph = build_research_graph(arm, checkpointer=None)
        visited: list[str] = []
        buckets: dict[str, list[dict]] = {}
        for update in graph.stream({"card_id": card_id, "arm": arm}, config={"recursion_limit": 30}, stream_mode="updates"):
            for node_name, payload in update.items():
                if node_name not in visited:
                    visited.append(node_name)
                if isinstance(payload, dict):
                    buckets.setdefault(node_name, []).append(payload)
        outputs = {name: [line for line in _lines_from(name, payloads) if line] for name, payloads in buckets.items()}
        verify = (buckets.get("verify") or [{}])[-1]
        recommendation = verify.get("recommendation") or {}
        bundle = (buckets.get("evidence") or [{}])[-1].get("evidence_bundle") or {}
        return {
            "arm": arm,
            "card_id": card_id,
            "live": live,
            "visited": visited,
            "outputs": outputs,
            "fallback": bool((verify.get("verification") or {}).get("fallback")),
            "recommendation": recommendation,
            "evidence": _evidence_rows(bundle, recommendation.get("action_or_abstain")),
        }
    finally:
        if previous is None:
            os.environ.pop("RISK_DESK_LIVE", None)
        else:
            os.environ["RISK_DESK_LIVE"] = previous


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path)
        if path.path == "/":
            body = _page()
            self._send(200, "text/html; charset=utf-8", body)
            return
        if path.path == "/api/meta":
            self._json(200, {"arms": list(ARMS), "cards": card_ids()})
            return
        if path.path == "/api/graph":
            arm = parse_qs(path.query).get("arm", ["challenged"])[0]
            try:
                self._json(200, describe(arm))
            except KeyError:
                self._json(404, {"error": "unknown arm"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/run":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("content-length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = run_arm(
                str(payload.get("arm") or "challenged"),
                str(payload.get("card_id") or ""),
                live=bool(payload.get("live")),
            )
        except KeyError as exc:
            self._json(404, {"error": f"unknown {exc}"})
            return
        except Exception as exc:  # surface a run failure on the page
            self._json(500, {"error": str(exc)})
            return
        self._json(200, result)

    def log_message(self, fmt: str, *args) -> None:
        return

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self._send(status, "application/json", body)

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = 8765) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    print(f"graph viewer http://127.0.0.1:{port}", flush=True)
    server.serve_forever()
