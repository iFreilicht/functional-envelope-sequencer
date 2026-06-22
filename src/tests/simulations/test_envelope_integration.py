"""Integration tests for the full offset → combine pipeline.

These tests exercise the complete data path:
    EnvelopeSettings → offset_envelopes → combine_envelopes

They are kept in a separate file because they build on top of the
unit-tested primitives and tend to be slower (time sweeps, multiple
envelopes).
"""

import pytest
from faker import Faker
from simulations.envelope import (
    AMPLITUDE_LOWER_CUTOFF,
    AMPLITUDE_MAX,
    TIME_END,
    TIME_START,
    CombineFn,
    EnvelopeSettings,
    combine_envelopes,
    combine_interpolate_linear,
    combine_max,
    offset_envelopes,
)

fake = Faker()


def _random_enabled_settings() -> EnvelopeSettings:
    return EnvelopeSettings(
        attack=fake.pyfloat(min_value=0.05, max_value=0.9),
        decay=fake.pyfloat(min_value=0.05, max_value=0.9),
        shape=fake.pyfloat(min_value=0.001, max_value=0.999),
        amplitude=fake.pyfloat(min_value=AMPLITUDE_LOWER_CUTOFF + 0.05, max_value=0.95),
    )


def _disabled_settings() -> EnvelopeSettings:
    return EnvelopeSettings(
        attack=fake.pyfloat(min_value=0.05, max_value=0.9),
        decay=fake.pyfloat(min_value=0.05, max_value=0.9),
        shape=fake.pyfloat(min_value=0.001, max_value=0.999),
        amplitude=0.0,
    )


_TIME_STEPS = [TIME_START + (TIME_END - TIME_START) * i / 99 for i in range(100)]
_COMBINERS = [combine_max, combine_interpolate_linear]
_COMBINER_IDS = ["max", "linear"]


@pytest.mark.parametrize("combiner", _COMBINERS, ids=_COMBINER_IDS)
class TestFullPipelineOutputRange:
    def test_output_in_range_enabled_envelopes(self, combiner: CombineFn):
        """For any combination of enabled envelopes, every output must lie in
        [0, AMPLITUDE_MAX] across the full time range."""
        n = fake.pyint(min_value=4, max_value=8)
        settings_list = [_random_enabled_settings() for _ in range(n)]
        interval = 0.25

        for time in _TIME_STEPS:
            statuses = offset_envelopes(settings_list, interval, time)
            result = combine_envelopes(settings_list, statuses, combiner)
            assert 0.0 <= result <= AMPLITUDE_MAX + 1e-9, (
                f"Out-of-range result {result} at time={time}"
            )

    def test_all_disabled_always_zero(self, combiner: CombineFn):
        """When every envelope is disabled the output must be 0 everywhere."""
        n = fake.pyint(min_value=2, max_value=6)
        settings_list = [_disabled_settings() for _ in range(n)]
        interval = fake.pyfloat(min_value=0.1, max_value=0.4)

        for time in _TIME_STEPS:
            statuses = offset_envelopes(settings_list, interval, time)
            result = combine_envelopes(settings_list, statuses, combiner)
            assert result == 0.0, f"Expected 0 at time={time}, got {result}"
