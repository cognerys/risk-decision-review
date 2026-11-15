"""Local page that draws the compiled arms and can run one card."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from risk_desk.data.cards import card_ids
from risk_desk.viewer.graph_view import ARMS, BUILDERS, describe

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


def _lines_from(name: str, payloads: list[dict]) -> list[str]:
    last = payloads[-1] if payloads else {}
    if name == "evidence" or name == "score":
        rows = last.get("evidence") or []
        wanted = ("var_95", "cvar_95", "stress_loss", "breach", "feasible_actions", "net_delta")
        by_kind = {row.get("kind"): row for row in rows}
        lines = []
        for kind in wanted:
            row = by_kind.get(kind)
            if row:
                units = row.get("units") if row.get("units") == "EUR" else ""
                lines.append(f"{kind.replace('_', ' ')}: {_fmt(row.get('value'))} {units}".strip())
        recommendation = last.get("recommendation") or {}
        if recommendation:
            lines.append(
                f"action: {recommendation.get('action_or_abstain')} — {recommendation.get('reason')}"
            )
        return lines
    if name == "book":
        lines = []
        for payload in payloads:
            for snap in payload.get("snapshots") or []:
                lines.append(f"{snap.get('book_id')}: quantity {_fmt(snap.get('quantity'))}")
        return lines
    if name == "supervisor":
        return ["routes: " + ", ".join(last.get("routes") or [])]
    if name == "propose":
        proposal = last.get("proposal") or {}
        return [
            f"model reply: {proposal.get('action_or_abstain') or 'no action'} — {proposal.get('reason') or 'no reason'}",
            "The verifier keeps this only when the reply cites evidence ids.",
        ]
    if name == "challenger":
        dissent = bool(last.get("dissent"))
        return ["dissent: yes" if dissent else "dissent: no"]
    if name in {"verify", "committee"}:
        recommendation = last.get("recommendation") or {}
        return [
            f"action: {recommendation.get('action_or_abstain')} — {recommendation.get('reason')}",
            str(recommendation.get("procedural") or ""),
            str(recommendation.get("economic") or ""),
            str(recommendation.get("evidential") or ""),
        ]
    return []


def run_arm(arm: str, card_id: str, *, live: bool) -> dict:
    if arm not in BUILDERS:
        raise KeyError(arm)
    if card_id not in card_ids():
        raise KeyError(card_id)
    previous = os.environ.get("RISK_DESK_LIVE")
    os.environ["RISK_DESK_LIVE"] = "1" if live else "0"
    try:
        graph = BUILDERS[arm](checkpointer=None)
        state = {
            "card_id": card_id,
            "arm": arm,
            "snapshots": [],
            "evidence": [],
            "auto_committee": True,
            "step_cap": 8,
        }
        visited: list[str] = []
        buckets: dict[str, list[dict]] = {}
        for update in graph.stream(
            state,
            config={"configurable": {"thread_id": f"view-{arm}-{card_id}"}},
            stream_mode="updates",
        ):
            for node_name, payload in update.items():
                if node_name not in visited:
                    visited.append(node_name)
                if isinstance(payload, dict):
                    buckets.setdefault(node_name, []).append(payload)
        outputs = {name: [line for line in _lines_from(name, payloads) if line] for name, payloads in buckets.items()}
        last_recommendation = {}
        for name in ("committee", "verify", "score"):
            if name in buckets and buckets[name][-1].get("recommendation"):
                last_recommendation = buckets[name][-1]["recommendation"]
                break
        evidence_rows = []
        for name in ("evidence", "score"):
            if name in buckets and buckets[name][-1].get("evidence"):
                evidence_rows = buckets[name][-1]["evidence"]
                break
        return {
            "arm": arm,
            "card_id": card_id,
            "live": live,
            "visited": visited,
            "outputs": outputs,
            "routes": (buckets.get("supervisor") or [{}])[-1].get("routes") or [],
            "recommendation": last_recommendation,
            "evidence": evidence_rows,
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
            arm = parse_qs(path.query).get("arm", ["desk"])[0]
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
                str(payload.get("arm") or "desk"),
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
