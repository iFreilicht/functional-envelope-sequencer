"""Combiner functions for merging adjacent envelope values into a single output.

To add a new combiner, define a function with the :class:`CombineFn` signature
and add it to the :data:`COMBINERS` registry.  The CLI and any other consumer
that builds its choice list from ``COMBINERS.keys()`` will pick it up
automatically.
"""

from simulations.envelope import TIME_END, CombineFn, EnvelopeStatus

__all__ = [
    "COMBINERS",
    "CombineFn",
    "combine_interpolate_linear",
    "combine_max",
]


def combine_max(left: EnvelopeStatus, right: EnvelopeStatus, time: float) -> float:
    """Combine two adjacent envelopes by choosing the higher value."""
    return max(left.value, right.value)


def combine_interpolate_linear(
    left: EnvelopeStatus, right: EnvelopeStatus, time: float
) -> float:
    """Combine two adjacent envelopes by interpolating between them linearly."""
    # Makes no sense to interpolate between two peaks that are at the same position.
    # Should not occur as the minimum interval is greater than 0
    assert left.midpoint != right.midpoint, f"Both peaks occur at {left.midpoint}"

    peak_distance = (right.midpoint - left.midpoint) % TIME_END
    progress_absolute = (time - left.midpoint) % TIME_END

    assert peak_distance >= progress_absolute, (
        f"Distance between peaks {peak_distance} is smaller than the "
        "current progress {progress_absolute}"
    )

    progress = progress_absolute / peak_distance

    # This should be impossible because of the previous assert
    assert 0.0 <= progress <= 1.0, f"Progress {progress} outside of [0.0,1.0]"

    interpolated = (1 - progress) * left.value + progress * right.value
    return interpolated


COMBINERS: dict[str, CombineFn] = {
    "max": combine_max,
    "linear": combine_interpolate_linear,
}
