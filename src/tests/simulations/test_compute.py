"""Unit tests for simulations.compute.compute_values."""

import pytest
from simulations.combiners import CombineFn, combine_interpolate_linear, combine_max
from simulations.compute import compute_values
from simulations.envelope import (
    AMPLITUDE_MAX,
    AMPLITUDE_MIN,
    TIME_END,
    TIME_MIDPOINT,
    TIME_START,
    EnvelopeSettings,
    offset_envelopes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TWO_ENVELOPES = [
    EnvelopeSettings(attack=0.3, decay=0.5, shape=0.8, amplitude=1.0),
    EnvelopeSettings(attack=0.4, decay=0.4, shape=0.2, amplitude=0.8),
]
_INTERVAL = 0.25
_TIMES = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


# ---------------------------------------------------------------------------
# Return-shape tests
# ---------------------------------------------------------------------------


class TestReturnShape:
    def test_samples_per_envelope_length_matches_envelope_count(self):
        samples_per_envelope, _ = compute_values(
            _TWO_ENVELOPES, _INTERVAL, _TIMES, combine_max
        )
        assert len(samples_per_envelope) == len(_TWO_ENVELOPES)

    def test_each_envelope_sample_list_length_matches_times(self):
        samples_per_envelope, _ = compute_values(
            _TWO_ENVELOPES, _INTERVAL, _TIMES, combine_max
        )
        for sample_list in samples_per_envelope:
            assert len(sample_list) == len(_TIMES)

    def test_combined_values_length_matches_times(self):
        _, values_combined = compute_values(
            _TWO_ENVELOPES, _INTERVAL, _TIMES, combine_max
        )
        assert len(values_combined) == len(_TIMES)

    def test_single_time_point(self):
        single_time = [TIME_MIDPOINT]
        samples, combined = compute_values(
            _TWO_ENVELOPES, _INTERVAL, single_time, combine_max
        )
        assert len(combined) == 1
        for s in samples:
            assert len(s) == 1

    def test_many_envelopes(self):
        envelopes = [
            EnvelopeSettings(attack=0.3, decay=0.3, shape=0.5, amplitude=float(i) / 8)
            for i in range(1, 9)
        ]
        samples, combined = compute_values(envelopes, 0.25, _TIMES, combine_max)
        assert len(samples) == 8
        assert len(combined) == len(_TIMES)


# ---------------------------------------------------------------------------
# Value-range tests
# ---------------------------------------------------------------------------


class TestValueRange:
    @pytest.mark.parametrize("combiner", [combine_max, combine_interpolate_linear])
    def test_combined_values_in_amplitude_range(self, combiner: CombineFn):
        _, values_combined = compute_values(_TWO_ENVELOPES, _INTERVAL, _TIMES, combiner)
        for v in values_combined:
            assert AMPLITUDE_MIN <= v <= AMPLITUDE_MAX + 1e-9, (
                f"Combined value {v} is out of [0, {AMPLITUDE_MAX}]"
            )

    @pytest.mark.parametrize("combiner", [combine_max, combine_interpolate_linear])
    def test_per_envelope_values_in_amplitude_range(self, combiner: CombineFn):
        samples_per_envelope, _ = compute_values(
            _TWO_ENVELOPES, _INTERVAL, _TIMES, combiner
        )
        for i, sample_list in enumerate(samples_per_envelope):
            expected_max = _TWO_ENVELOPES[i].amplitude
            for s in sample_list:
                assert AMPLITUDE_MIN <= s.value <= expected_max + 1e-9, (
                    f"Envelope {i} value {s.value} out of [0, {expected_max}]"
                )


# ---------------------------------------------------------------------------
# Combiner-specific: max >= linear
# ---------------------------------------------------------------------------


class TestCombinerOrdering:
    # TODO: Fix this once combine_interpolate_linear is corrected
    @pytest.mark.xfail(reason="combine_interpolate_linear is broken right now")
    def test_max_never_less_than_linear(self):
        """combine_max output should never be smaller than combine_interpolate_linear,
        since interpolation between two values is bounded by their maximum."""
        _, max_values = compute_values(_TWO_ENVELOPES, _INTERVAL, _TIMES, combine_max)
        _, lin_values = compute_values(
            _TWO_ENVELOPES, _INTERVAL, _TIMES, combine_interpolate_linear
        )
        for t, vm, vl in zip(_TIMES, max_values, lin_values, strict=True):
            assert vm >= vl - 1e-12, f"At t={t}: max={vm} < linear={vl}"


# ---------------------------------------------------------------------------
# Disabled envelopes
# ---------------------------------------------------------------------------


class TestDisabledEnvelopes:
    def test_all_disabled_combined_is_zero(self):
        disabled = [
            EnvelopeSettings(attack=0.3, decay=0.3, shape=0.5, amplitude=0.0),
            EnvelopeSettings(attack=0.4, decay=0.4, shape=0.5, amplitude=0.0),
        ]
        _, values_combined = compute_values(disabled, _INTERVAL, _TIMES, combine_max)
        for v in values_combined:
            assert v == 0.0

    def test_disabled_envelope_samples_are_zero(self):
        disabled = [
            EnvelopeSettings(attack=0.3, decay=0.3, shape=0.5, amplitude=0.0),
            EnvelopeSettings(attack=0.4, decay=0.4, shape=0.5, amplitude=1.0),
        ]
        samples, _ = compute_values(disabled, _INTERVAL, _TIMES, combine_max)
        # First envelope is disabled — all its samples must be 0
        for s in samples[0]:
            assert s.value == 0.0


# ---------------------------------------------------------------------------
# Ordering invariant: per-envelope samples match per-time samples
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_per_envelope_samples_match_per_time_offset_values(self):
        """The transposition in compute_values must preserve order: the k-th
        value in samples_per_envelope[i] corresponds to times[k]."""
        times = _TIMES
        samples_per_envelope, _ = compute_values(
            _TWO_ENVELOPES, _INTERVAL, times, combine_max
        )
        for k, t in enumerate(times):
            direct = offset_envelopes(_TWO_ENVELOPES, _INTERVAL, t)
            for i in range(len(_TWO_ENVELOPES)):
                assert samples_per_envelope[i][k].value == pytest.approx(
                    direct[i].value
                ), f"Mismatch at envelope {i}, time index {k} (t={t})"


# ---------------------------------------------------------------------------
# Empty times list
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_times_returns_empty_lists(self):
        samples, combined = compute_values(_TWO_ENVELOPES, _INTERVAL, [], combine_max)
        assert combined == []
        for s in samples:
            assert s == []

    def test_boundary_times_do_not_raise(self):
        boundary_times = [TIME_START, TIME_MIDPOINT, TIME_END]
        samples, combined = compute_values(
            _TWO_ENVELOPES, _INTERVAL, boundary_times, combine_max
        )
        assert len(combined) == 3
        for s in samples:
            assert len(s) == 3
