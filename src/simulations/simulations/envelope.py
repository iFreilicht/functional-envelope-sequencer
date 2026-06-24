import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Protocol

from simulations.helpers import clamp_checked

# Max and min values for inputs.
SHAPE_MIN = 0.0
SHAPE_MAX = 1.0
AMPLITUDE_MIN = 0.0
AMPLITUDE_LOWER_CUTOFF = 0.01
AMPLITUDE_MAX = 1.0
PROGRESS_MIN = 0.0
PROGRESS_MAX = 1.0
INTERVAL_MIN = 0.05
INTERVAL_MAX = 0.5

# Loop timing
# The minimum time a slope is allowed to last, to avoid subnormal values
# and the resulting loss of precision
SLOPE_TIME_MIN = 0.001
TIME_START = 0.0
TIME_MIN = TIME_START + SLOPE_TIME_MIN
# Time is taken modulo `TIME_END` in many contexts, so this value is never actually
# reached, but functions should be able to handle it and treat it like 0.0
TIME_END = 2.0
TIME_MIDPOINT = (TIME_START + TIME_END) / 2


def a_d_shape(shape: float, progress: float) -> float:
    r"""Function describing the shape of an attack- or decay-slope.

    If `shape` is $s$ and `progress` is $x$:

    $$f\left(x\right)=\left(1-s\right)x^{\left(1+s\right)}+sx^{10^{s}}$$

    At progress 0 and 1 the output is independent of shape:

    >>> a_d_shape(0.0, 0.0)
    0.0
    >>> a_d_shape(0.5, 0.0)
    0.0
    >>> a_d_shape(1.0, 0.0)
    0.0
    >>> a_d_shape(0.0, 1.0)
    1.0
    >>> a_d_shape(0.5, 1.0)
    1.0
    >>> a_d_shape(1.0, 1.0)
    1.0

    With shape 0 the function is linear (returns `progress` unchanged):

    >>> a_d_shape(0.0, 0.2)
    0.2
    >>> a_d_shape(0.0, 0.5)
    0.5
    >>> a_d_shape(0.0, 0.7)
    0.7

    With shape 1 the function is a degree-10 polynomial:

    >>> import math
    >>> math.isclose(a_d_shape(1.0, 0.2), 0.2 ** 10)
    True
    >>> math.isclose(a_d_shape(1.0, 0.5), 0.5 ** 10)
    True
    >>> math.isclose(a_d_shape(1.0, 0.7), 0.7 ** 10)
    True
    """
    progress = clamp_checked(progress, PROGRESS_MIN, PROGRESS_MAX)
    shape = clamp_checked(shape, SHAPE_MIN, SHAPE_MAX)

    exponent = 10.0  # Exponent for "quadratic" envelope, eyeballed in Desmos
    s, x = shape, progress
    lin = x  # Linear envelope, should be the only one when shape is 0
    quad = math.pow(
        x, math.pow(exponent, s)
    )  # "Quadratic" envelope, should be the only one when shape is 1
    # Interpolation is not quite linear, but looks very natural when sweeping over s
    interpolated = (1 - s) * math.pow(lin, (1 + s)) + s * quad
    return interpolated


@dataclass(frozen=True, kw_only=True)
class EnvelopeSettings:
    attack: float
    decay: float
    shape: float
    amplitude: float

    def __post_init__(self):
        object.__setattr__(
            self, "attack", clamp_checked(self.attack, TIME_MIN, TIME_MIDPOINT)
        )
        object.__setattr__(
            self, "decay", clamp_checked(self.decay, TIME_MIN, TIME_MIDPOINT)
        )
        object.__setattr__(
            self, "shape", clamp_checked(self.shape, SHAPE_MIN, SHAPE_MAX)
        )
        object.__setattr__(
            self,
            "amplitude",
            clamp_checked(self.amplitude, AMPLITUDE_MIN, AMPLITUDE_MAX),
        )

    def is_enabled(self):
        return self.amplitude > AMPLITUDE_LOWER_CUTOFF


def a_d_envelope(settings: EnvelopeSettings, time: float) -> float:
    """Single Attack/Decay (A/D) envelope fixed in the interval
    `[TIME_START, TIME_END]`, with the peak always at `TIME_MIDPOINT`.

    `attack` is the time for the attack slope to rise from 0 to the peak.
    `decay` is the time for the decay slope to fall from the peak to 0.

    1. From `TIME_START` to `TIME_MIDPOINT - attack`, return 0
    2. From `TIME_MIDPOINT - attack` to `TIME_MIDPOINT`, return the
       attack envelope shaped by `shape`
    3. From `TIME_MIDPOINT` to `TIME_MIDPOINT + decay`, return the
       decay envelope shaped by `shape`
    4. From `TIME_MIDPOINT + decay` to `TIME_END`, return 0

    The peak at TIME_MIDPOINT always equals `amplitude`:

    >>> s = EnvelopeSettings(attack=0.5, decay=0.5, shape=0.0, amplitude=1.0)
    >>> a_d_envelope(s, TIME_MIDPOINT)
    1.0

    Regions outside the attack/decay window return 0:

    >>> a_d_envelope(s, TIME_START)
    0.0
    >>> a_d_envelope(s, TIME_END)
    0.0

    A disabled envelope (amplitude ≤ AMPLITUDE_LOWER_CUTOFF) always returns 0:

    >>> disabled = EnvelopeSettings(attack=0.5, decay=0.5, shape=0.0, amplitude=0.0)
    >>> a_d_envelope(disabled, TIME_MIDPOINT)
    0.0
    """
    assert TIME_START <= time <= TIME_END

    attack, decay, shape, amplitude = (
        settings.attack,
        settings.decay,
        settings.shape,
        settings.amplitude,
    )

    if not settings.is_enabled():
        return 0.0

    # Attack phase
    if time <= TIME_MIDPOINT:
        start = TIME_MIDPOINT - attack
        if time < start:
            return 0.0

        progress = (time - start) / attack
        value = a_d_shape(shape, progress)
    # Decay phase
    else:
        end = TIME_MIDPOINT + decay
        if time > end:
            return 0.0

        progress = (-time + end) / decay
        value = a_d_shape(shape, progress)

    return value * amplitude


@dataclass(frozen=True)
class EnvelopeStatus:
    time: float
    """The current time input that was used to generate `value`, i.e. how
    much time has passed since this envelope started.

    Expected to wrap back to `TIME_START` once `TIME_END` is reached.
    """

    midpoint: float
    """The global time at which this envelope's peak occurs. This is used to determine
    which two envelopes to combine at any given point in time."""

    value: float
    """The value of this envelope at `time`."""

    enabled: float
    """Whether this envelope is enabled. If `False`, this envelope will not be
    considered for interpolation, no matter what the other values are.

    This is not equivalent to when `value=0.0` as that can also happen for
    enabled envelopes.
    """

    def __post_init__(self):
        object.__setattr__(self, "time", clamp_checked(self.time, TIME_START, TIME_END))
        object.__setattr__(
            self, "midpoint", clamp_checked(self.midpoint, TIME_START, TIME_END)
        )
        object.__setattr__(
            self, "value", clamp_checked(self.value, AMPLITUDE_MIN, AMPLITUDE_MAX)
        )


def offset_envelopes(
    envelopes_settings: Sequence[EnvelopeSettings], interval: float, time: float
) -> list[EnvelopeStatus]:
    """Calculate values at `time` for envelopes in `envelopes_settings`,
    spaced evenly apart with peaks occurring every `interval`."""
    interval = clamp_checked(interval, INTERVAL_MIN, INTERVAL_MAX)

    envelopes_status: list[EnvelopeStatus] = []
    for i, env_settings in enumerate(envelopes_settings):
        env_offset = interval * i
        env_time = (time - env_offset) % TIME_END
        env_midpoint = (env_offset + TIME_MIDPOINT) % TIME_END
        value = a_d_envelope(env_settings, env_time)
        envelopes_status.append(
            EnvelopeStatus(
                time=env_time,
                midpoint=env_midpoint,
                value=value,
                enabled=env_settings.is_enabled(),
            )
        )

    return envelopes_status


class CombineFn(Protocol):
    @staticmethod
    def __call__(left: EnvelopeStatus, right: EnvelopeStatus, time: float) -> float: ...


def combine_envelopes(
    envelopes_status: Sequence[EnvelopeStatus],
    time: float,
    combiner: CombineFn,
) -> float:
    """
    Find the two envelopes whose peaks are currently closest and call `combiner`
    on them to get a combined value.

    Consider the example below, where `envelopes_status` has eight elements,
    represented by the letters a-h. `y` is the `EnvelopeStatus.time` value,
    `x` is the global timeline, `t` is the parameter `time`.

    ```
                  y
         TIME_END ^g h a b c d e f |
                  |/ / / / / / / / |
                  | / / / / / / / /|
    TIME_MIDPOINT |/ / /⊙/ / / / / |
                  | / / / / / / / /|
                  |/ / /|/ / / / / |
       TIME_START +----------------+> x
                        | |        |
                        t |     TIME_END
                          |
                  TIME_MIDPOINT
    ```

    The `⊙` is the point under inspection, where `x=time` and
    `status.time=TIME_MIDPOINT`. We look for the two envelopes to the left
    and right of `⊙` — those are the ones whose peaks the current `time`
    lies between, so they are the pair we need to combine.

    The illustration is somewhat inaccurate; the slopes may be much shallower
    and closer together, so multiple slopes can overlap at once.

    It does accurately depict the wrapping behavior, however; `time` is always taken
    modulo `TIME_END`, so the envelopes effectively wrap around. This means that desipte
    envelope `a` starting at `t=0`, the one having its peak at `t=0` is a different one.
    (Which one exactly depends on the interval they're spaced at.)

    Disabled envelopes are skipped, so if `c` and `d` were disabled, envelope
    `b` would be combined with `e` when their slopes overlap.
    """
    # TODO: Special handling on the first time loop (time < 1.0) so the envelope can
    # start smoothly
    time = time % TIME_END

    # Discard all envelopes that are disabled so combining longer envelopes that aren't
    # directly adjacent to each other works as expected
    active_envelopes: list[EnvelopeStatus] = [s for s in envelopes_status if s.enabled]

    # In the rare but possible case that all envelopes are disabled,
    # we cannot call `combiner` and have to return 0
    if len(active_envelopes) < 1:
        return 0.0

    # If only one envelope is active there is nothing to combine;
    # calling the combiner with the same envelope on both sides would be
    # meaningless (and would cause ZeroDivisionError for the linear combiner)
    if len(active_envelopes) == 1:
        return active_envelopes[0].value

    active_envelopes.sort(key=lambda s: s.midpoint)

    # Find the pair of envelopes we need to combine at the current point in time
    for left, right in pairwise(active_envelopes):
        if left.midpoint <= time <= right.midpoint:
            return combiner(left, right, time)

    # If no pair was found, we're either to the left of the first or to the right of
    # the last envelope. Because we're wrapping around, these cases are equivalent
    return combiner(active_envelopes[-1], active_envelopes[0], time)
