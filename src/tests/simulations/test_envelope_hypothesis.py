"""Property-based tests for simulations.envelope using Hypothesis.

These tests express mathematical invariants as universally-quantified properties
over the full valid input domain.  They complement the faker-based tests in
`test_envelope_unit.py` and `test_envelope_integration.py`, which sample random
inputs with a fixed seed.

The key advantage over faker is **shrinking**: when Hypothesis finds a failing
input it automatically reduces it to the *minimal* counterexample before
reporting, making failures much easier to diagnose.
"""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from simulations.envelope import (
    AMPLITUDE_LOWER_CUTOFF,
    AMPLITUDE_MAX,
    AMPLITUDE_MIN,
    INTERVAL_MAX,
    INTERVAL_MIN,
    PROGRESS_MAX,
    PROGRESS_MIN,
    SHAPE_MAX,
    SHAPE_MIN,
    SLOPE_TIME_MIN,
    TIME_END,
    TIME_MIDPOINT,
    TIME_START,
    CombineFn,
    EnvelopeSettings,
    a_d_envelope,
    a_d_shape,
    combine_envelopes,
    combine_interpolate_linear,
    combine_max,
    offset_envelopes,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------


# Disallow NaN/inf/subnormals so asserts inside envelope.py never fire
# on ill-formed floats — those are not part of the valid input domain.
def floats_helper(min_value: float, max_value: float) -> st.SearchStrategy[float]:
    return st.floats(
        min_value=min_value,
        max_value=max_value,
        allow_nan=False,
        allow_infinity=False,
        allow_subnormal=False,
    )


_shape_strategy = floats_helper(min_value=SHAPE_MIN, max_value=SHAPE_MAX)
_progress_strategy = floats_helper(min_value=PROGRESS_MIN, max_value=PROGRESS_MAX)
_attack_decay_strategy = floats_helper(
    min_value=SLOPE_TIME_MIN, max_value=TIME_MIDPOINT
)
_amlitude_strategy = floats_helper(min_value=AMPLITUDE_MIN, max_value=AMPLITUDE_MAX)
enabled_amplitude_strategy = floats_helper(
    min_value=AMPLITUDE_LOWER_CUTOFF + 1e-6, max_value=AMPLITUDE_MAX
)
_disabled_amplitude_strategy = floats_helper(
    min_value=AMPLITUDE_MIN, max_value=AMPLITUDE_LOWER_CUTOFF - 1e-6
)
_time_strategy = floats_helper(min_value=TIME_START, max_value=TIME_END)
_interval_strategy = floats_helper(min_value=INTERVAL_MIN, max_value=INTERVAL_MAX)

_settings_strategy = st.builds(
    EnvelopeSettings,
    attack=_attack_decay_strategy,
    decay=_attack_decay_strategy,
    shape=_shape_strategy,
    amplitude=_amlitude_strategy,
)
_enabled_settings_strategy = st.builds(
    EnvelopeSettings,
    attack=_attack_decay_strategy,
    decay=_attack_decay_strategy,
    shape=_shape_strategy,
    amplitude=enabled_amplitude_strategy,
)
_disabled_settings_strategy = st.builds(
    EnvelopeSettings,
    attack=_attack_decay_strategy,
    decay=_attack_decay_strategy,
    shape=_shape_strategy,
    amplitude=_disabled_amplitude_strategy,
)

# ---------------------------------------------------------------------------
# Block A — a_d_shape() properties
# ---------------------------------------------------------------------------


class TestADShapeProperties:
    @given(shape=_shape_strategy)
    def test_endpoint_zero_independent_of_shape(self, shape: float):
        """For any valid shape, progress=0 always maps to 0."""
        assert a_d_shape(shape, 0.0) == 0.0

    @given(shape=_shape_strategy)
    def test_endpoint_one_independent_of_shape(self, shape: float):
        """For any valid shape, progress=1 always maps to 1."""
        assert a_d_shape(shape, 1.0) == pytest.approx(1.0)

    @given(progress=_progress_strategy)
    def test_linear_at_shape_zero(self, progress: float):
        """At shape=0 the function is the identity — pure linear ramp."""
        assert a_d_shape(0.0, progress) == pytest.approx(progress)

    @given(progress=_progress_strategy)
    def test_exponential_at_shape_one(self, progress: float):
        """At shape=1 the function is a degree-10 polynomial."""
        assert a_d_shape(1.0, progress) == pytest.approx(progress**10)

    @given(
        shape=_shape_strategy,
        p1=floats_helper(min_value=0.0, max_value=0.5),
        p2=floats_helper(min_value=0.5, max_value=1.0),
    )
    def test_monotonicity(self, shape: float, p1: float, p2: float):
        """a_d_shape is monotonically non-decreasing in progress."""
        assert a_d_shape(shape, p1) <= a_d_shape(shape, p2) + 1e-12

    @given(
        shape=_shape_strategy,
        progress=floats_helper(min_value=PROGRESS_MIN, max_value=1.0),
    )
    def test_output_in_unit_range(self, shape: float, progress: float):
        """Output is always within [0, 1] for progress in [0, 1].

        Note: the valid progress range extends slightly above 1.0 to
        PROGRESS_MAX=1.001 to absorb floating-point noise, but the output is
        only guaranteed to be ≤ 1.0 when progress itself is ≤ 1.0.
        """
        result = a_d_shape(shape, progress)
        assert 0.0 <= result <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# Block C — a_d_envelope() properties
# ---------------------------------------------------------------------------


class TestADEnvelopeProperties:
    @given(settings=_enabled_settings_strategy)
    def test_peak_equals_amplitude(self, settings: EnvelopeSettings):
        """The envelope always peaks exactly at amplitude when evaluated at
        TIME_MIDPOINT, regardless of attack, decay, and shape.

        attack=0 is excluded because the attack branch short-circuits to 0
        when attack==0 (progress is undefined when the window has zero width).
        Subnormal attacks where TIME_MIDPOINT - attack == TIME_MIDPOINT in
        float64 are also excluded for the same reason.
        """
        _ = assume(settings.attack > 0.0)
        _ = assume(TIME_MIDPOINT - settings.attack != TIME_MIDPOINT)
        assert a_d_envelope(settings, TIME_MIDPOINT) == pytest.approx(
            settings.amplitude
        )

    @given(settings=_disabled_settings_strategy, time=_time_strategy)
    def test_disabled_always_zero(self, settings: EnvelopeSettings, time: float):
        """Disabled envelopes (amplitude ≤ AMPLITUDE_LOWER_CUTOFF) always
        return 0 regardless of time, attack, decay, and shape."""
        assert a_d_envelope(settings, time) == 0.0

    @given(settings=_settings_strategy, time=_time_strategy)
    def test_output_in_range(self, settings: EnvelopeSettings, time: float):
        """Output is always in [0, amplitude + epsilon]."""
        result = a_d_envelope(settings, time)
        assert 0.0 <= result <= settings.amplitude + 1e-9

    @given(data=st.data())
    def test_amplitude_scales_linearly(self, data: st.DataObject):
        """Doubling amplitude doubles the output at any point in the window."""
        # Draw attack and decay that fit within TIME_MIDPOINT
        attack = data.draw(floats_helper(min_value=0.1, max_value=TIME_MIDPOINT - 0.05))
        decay = data.draw(floats_helper(min_value=0.05, max_value=TIME_MIDPOINT))
        shape = data.draw(_shape_strategy)

        # Draw a time strictly inside the attack window so the envelope is
        # guaranteed to be non-zero (otherwise the ratio is undefined).
        attack_start = TIME_MIDPOINT - attack
        time = data.draw(
            floats_helper(min_value=attack_start + 1e-6, max_value=TIME_MIDPOINT - 1e-6)
        )

        # amplitude_a must be small enough that 2× stays within AMPLITUDE_MAX
        amplitude_a = data.draw(
            floats_helper(
                min_value=AMPLITUDE_LOWER_CUTOFF + 1e-4, max_value=AMPLITUDE_MAX / 2.0
            )
        )
        amplitude_b = amplitude_a * 2.0

        v_a = a_d_envelope(
            EnvelopeSettings(
                attack=attack, decay=decay, shape=shape, amplitude=amplitude_a
            ),
            time,
        )
        # Skip if we accidentally landed in the silent region (shouldn't happen
        # given the time constraint, but floating-point edge cases exist).
        assume(v_a > 1e-10)

        v_b = a_d_envelope(
            EnvelopeSettings(
                attack=attack, decay=decay, shape=shape, amplitude=amplitude_b
            ),
            time,
        )
        assert v_b / v_a == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Block G — full-pipeline properties
# ---------------------------------------------------------------------------


class TestFullPipelineProperties:
    @given(
        settings_list=st.lists(_enabled_settings_strategy, min_size=2, max_size=6),
        interval=_interval_strategy,
        time=_time_strategy,
    )
    def test_output_in_range_max_combiner(
        self,
        settings_list: list[EnvelopeSettings],
        interval: float,
        time: float,
    ):
        """Full pipeline with combine_max always stays in [0, AMPLITUDE_MAX]."""
        statuses = offset_envelopes(settings_list, interval, time)
        result = combine_envelopes(settings_list, statuses, combine_max)
        assert 0.0 <= result <= AMPLITUDE_MAX + 1e-9

    @given(
        settings_list=st.lists(_enabled_settings_strategy, min_size=2, max_size=6),
        interval=_interval_strategy,
        time=_time_strategy,
    )
    def test_output_in_range_linear_combiner(
        self,
        settings_list: list[EnvelopeSettings],
        interval: float,
        time: float,
    ):
        """Full pipeline with combine_interpolate_linear always stays in
        [0, AMPLITUDE_MAX]."""
        statuses = offset_envelopes(settings_list, interval, time)
        result = combine_envelopes(settings_list, statuses, combine_interpolate_linear)
        assert 0.0 <= result <= AMPLITUDE_MAX + 1e-9

    @given(
        settings_list=st.lists(_disabled_settings_strategy, min_size=1, max_size=6),
        interval=_interval_strategy,
        time=_time_strategy,
    )
    def test_all_disabled_always_zero(
        self,
        settings_list: list[EnvelopeSettings],
        interval: float,
        time: float,
    ):
        """When every envelope is disabled both combiners must return exactly 0."""
        statuses = offset_envelopes(settings_list, interval, time)
        for combiner in (combine_max, combine_interpolate_linear):
            result = combine_envelopes(settings_list, statuses, combiner)
            assert result == 0.0

    @given(
        settings_list=st.lists(_enabled_settings_strategy, min_size=2, max_size=6),
        interval=_interval_strategy,
        time=_time_strategy,
    )
    def test_max_combiner_never_less_than_linear(
        self,
        settings_list: list[EnvelopeSettings],
        interval: float,
        time: float,
    ):
        """combine_max must never produce a lower value than
        combine_interpolate_linear, because interpolation between two
        values is always ≤ the maximum of those values."""
        statuses = offset_envelopes(settings_list, interval, time)
        v_max = combine_envelopes(settings_list, statuses, combine_max)
        v_lin = combine_envelopes(settings_list, statuses, combine_interpolate_linear)
        assert v_max >= v_lin - 1e-12

    def _combiner_ids(self) -> list[str]:
        return ["max", "linear"]

    @pytest.mark.parametrize(
        "combiner",
        [combine_max, combine_interpolate_linear],
        ids=["max", "linear"],
    )
    @given(
        settings_list=st.lists(_enabled_settings_strategy, min_size=2, max_size=6),
        interval=_interval_strategy,
    )
    def test_output_consistent_across_time(
        self,
        combiner: CombineFn,
        settings_list: list[EnvelopeSettings],
        interval: float,
    ):
        """The pipeline must not raise for any (settings, interval, time)
        triple — output range is checked across multiple time points."""
        for time in (TIME_START, TIME_MIDPOINT, TIME_END):
            statuses = offset_envelopes(settings_list, interval, time)
            result = combine_envelopes(settings_list, statuses, combiner)
            assert 0.0 <= result <= AMPLITUDE_MAX + 1e-9
