"""Combiner functions for merging adjacent envelope values into a single output.

To add a new combiner, define a function with the :class:`CombineFn` signature
and add it to the :data:`COMBINERS` registry.  The CLI and any other consumer
that builds its choice list from ``COMBINERS.keys()`` will pick it up
automatically.
"""

from simulations.envelope import TIME_MIDPOINT, CombineFn, EnvelopeStatus

__all__ = [
    "COMBINERS",
    "CombineFn",
    "combine_interpolate_linear",
    "combine_max",
]


def combine_max(left: EnvelopeStatus, right: EnvelopeStatus) -> float:
    """Combine two adjacent envelopes by choosing the higher value."""
    return max(left.value, right.value)


def combine_interpolate_linear(left: EnvelopeStatus, right: EnvelopeStatus) -> float:
    """Combine two adjacent envelopes by interpolating between them linearly."""
    scale = 1 / (right.time - left.time)
    raw_weight = TIME_MIDPOINT - left.time
    weight = raw_weight * scale
    interpolated = (1 - weight) * left.value + weight * right.value
    return interpolated


COMBINERS: dict[str, CombineFn] = {
    "max": combine_max,
    "linear": combine_interpolate_linear,
}
