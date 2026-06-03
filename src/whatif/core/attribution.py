"""Exact per-parameter attribution.

No SHAP needed: the indicator engine is an exact, known function, so we step from the
baseline parameters to the what-if parameters one change-group at a time (in a fixed order)
and record each group's marginal effect on every indicator. Because every differing field is
covered by exactly one group, the walk ends exactly at the target and the contributions sum
exactly to the total delta per indicator. (Optional stretch: average over orderings for
order-independent Shapley values.)
"""
from __future__ import annotations

from whatif.core.catalogue import ATTRIBUTION_GROUPS, INDICATOR_NAMES
from whatif.core.generator import scenario_from_params
from whatif.core.indicators import compute_indicators
from whatif.core.schema import Assets, ScenarioParams


def attribute(
    base_params: ScenarioParams,
    target_params: ScenarioParams,
    assets: Assets,
    groups: "list | None" = None,
) -> dict:
    """Return ``{group_key: {indicator: contribution}}`` that sums to the total delta."""
    groups = groups or ATTRIBUTION_GROUPS
    current = base_params.as_dict()
    target = target_params.as_dict()

    prev = compute_indicators(scenario_from_params(ScenarioParams(**current), assets))
    contributions: dict = {key: {ind: 0.0 for ind in INDICATOR_NAMES} for key, _ in groups}

    for key, fields in groups:
        if all(current[f] == target[f] for f in fields):
            continue  # group unchanged → zero contribution
        for f in fields:
            current[f] = target[f]
        now = compute_indicators(scenario_from_params(ScenarioParams(**current), assets))
        for ind in INDICATOR_NAMES:
            contributions[key][ind] = getattr(now, ind) - getattr(prev, ind)
        prev = now

    return contributions
