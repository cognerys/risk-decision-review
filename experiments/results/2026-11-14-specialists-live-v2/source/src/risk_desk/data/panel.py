"""Seeded return panel for the empirical VaR proxy.

Ordinary vols are calm on purpose: transaction cost then exceeds the tail
benefit of hedging, which is what makes `hold` the scorecard action on an
inside-limits book. Cold-spell and break regimes are wider. The checked-in
fixture is what scoring reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

SEED = 42
DAYS = 60
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "returns.json"

# power, gas, carbon daily vols and (power-gas, power-carbon, gas-carbon) correlations.
REGIME_SPECS: dict[str, tuple[float, float, float, float, float, float]] = {
    "ordinary": (0.004, 0.0035, 0.003, 0.60, 0.30, 0.20),
    "cold_spell_thin_liquidity": (0.045, 0.040, 0.020, 0.85, 0.40, 0.25),
    "correlation_break": (0.030, 0.030, 0.025, 0.05, -0.20, 0.00),
}

SHOCKS: dict[str, dict[str, float]] = {
    "ordinary": {"power": -0.004, "gas": -0.003, "carbon": -0.002},
    "cold_spell_thin_liquidity": {"power": -0.12, "gas": -0.10, "carbon": -0.04},
    "correlation_break": {"power": -0.08, "gas": 0.06, "carbon": -0.05},
}

SPREADS = {"normal": 0.004, "thin": 0.018}


def _draws(spec: tuple[float, float, float, float, float, float], rng: np.random.Generator) -> list[dict[str, float]]:
    vol_p, vol_g, vol_c, c_pg, c_pc, c_gc = spec
    corr = np.array(
        [[1.0, c_pg, c_pc], [c_pg, 1.0, c_gc], [c_pc, c_gc, 1.0]],
        dtype=float,
    )
    chol = np.linalg.cholesky(corr)
    shocks = rng.standard_normal((DAYS, 3)) @ chol.T
    vols = np.array([vol_p, vol_g, vol_c])
    rows = shocks * vols
    return [
        {"power": float(row[0]), "gas": float(row[1]), "carbon": float(row[2])}
        for row in rows
    ]


def build_panel(seed: int = SEED) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    regimes = {name: _draws(spec, rng) for name, spec in REGIME_SPECS.items()}
    return {"seed": seed, "days": DAYS, "regimes": regimes, "shocks": SHOCKS, "spreads": SPREADS}


def write_fixture(path: Path = FIXTURE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_panel(), indent=2) + "\n", encoding="utf-8")


def load_panel(path: Path = FIXTURE_PATH) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
