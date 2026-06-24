"""Shared computation helpers for envelope analysis."""

from collections.abc import Sequence

from simulations.combiners import CombineFn
from simulations.envelope import (
    EnvelopeSettings,
    EnvelopeStatus,
    combine_envelopes,
    offset_envelopes,
)


def compute_values(
    envelopes: Sequence[EnvelopeSettings],
    interval: float,
    times: Sequence[float],
    combine_fn: CombineFn,
) -> tuple[list[list[EnvelopeStatus]], list[float]]:
    """Compute per-envelope samples and combined values over ``times``.

    Returns a tuple of:

    - ``samples_per_envelope``: one list of ``EnvelopeStatus`` per envelope,
      in the same order as ``envelopes``, each list having one entry per time
      step.
    - ``values_combined``: one combined scalar value per time step.
    """
    offset_values = [offset_envelopes(envelopes, interval, t) for t in times]
    values_combined = [
        combine_envelopes(s, t, combine_fn)
        for s, t in zip(offset_values, times, strict=True)
    ]
    samples_per_envelope: list[list[EnvelopeStatus]] = [[] for _ in envelopes]
    for sample in offset_values:
        for i, env in enumerate(sample):
            samples_per_envelope[i].append(env)
    return samples_per_envelope, values_combined
