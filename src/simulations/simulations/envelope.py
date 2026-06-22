from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
import math
from typing import Protocol

# Max and min values for inputs.
# Maximum is slightly larger than one so asserts don't
# fail because of inaccurate float values
SHAPE_MIN = 0.0
SHAPE_MAX = 1.001
AMPLITUDE_MIN = 0.0
AMPLITUDE_LOWER_CUTOFF = 0.01
AMPLITUDE_MAX = 1.001
PROGRESS_MIN = 0.0
PROGRESS_MAX = 1.001

# Loop timing
# No need for slightly larger maximum because time is always treated
# module TIME_END, so this value is never actually reached
TIME_START = 0.0
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
    assert PROGRESS_MIN <= progress <= PROGRESS_MAX, f"{progress} is outside of limits!"
    assert SHAPE_MIN <= shape <= SHAPE_MAX, f"{shape} is outside of limits!"

    EXPONENT = 10.0  # Exponent for "quadratic" envelope, eyeballed in Desmos
    s, x = shape, progress
    lin = x  # Linear envelope, should be the only one when shape is 0
    quad = math.pow(
        x, math.pow(EXPONENT, s)
    )  # "Quadratic" envelope, should be the only one when shape is 1
    # Interpolation is not quite linear, but looks very natural when sweeping over s
    interpolated = (1 - s) * math.pow(lin, (1 + s)) + s * quad
    return interpolated


@dataclass(frozen=True)
class EnvelopeSettings:
    attack: float
    decay: float
    shape: float
    amplitude: float

    def __post_init__(self):
        assert TIME_START <= self.attack <= TIME_MIDPOINT
        assert TIME_START <= self.decay <= TIME_MIDPOINT
        assert SHAPE_MIN <= self.shape <= SHAPE_MAX
        assert AMPLITUDE_MIN <= self.amplitude <= AMPLITUDE_MAX

    def is_disabled(self):
        return self.amplitude <= AMPLITUDE_LOWER_CUTOFF


def a_d_envelope(settings: EnvelopeSettings, time: float) -> float:
    """Function describing a single Attack/Decay (A/D) envelope that is fixed in an interval between
    `time=TIME_START` and `time=TIME_END`, with the peak always occurring at `time=TIME_MIDPOINT`.

    `attack` is the time it takes for the attack-slope to reach the peak when starting at level 0.
    `decay` is the time it takes for the delay-slope to reach level 0 when starting from the peak.

    1. From `TIME_START` to `TIME_MIDPOINT - attack`, return 0
    2. From `TIME_MIDPOINT - attack` to `TIME_MIDPOINT`, return the attack envelope based on `shape`
    3. From `TIME_MIDPOINT` to `TIME_MIDPOINT + decay`, return the decay envelope based on `shape`
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
    attack, decay, shape, amplitude = (
        settings.attack,
        settings.decay,
        settings.shape,
        settings.amplitude,
    )

    assert TIME_START <= time <= TIME_END
    if settings.is_disabled():
        return 0.0

    # Attack phase
    if time <= TIME_MIDPOINT:
        start = TIME_MIDPOINT - attack
        if time < start or attack == 0.0:
            return 0.0

        progress = (time - start) / attack
        value = a_d_shape(shape, progress)
    # Decay phase
    else:
        end = TIME_MIDPOINT + decay
        if time > end or decay == 0.0:
            return 0.0

        progress = (-time + end) / decay
        value = a_d_shape(shape, progress)

    return value * amplitude


@dataclass(frozen=True)
class EnvelopeStatus:
    time: float
    """The current time input that was used to generate `value`, or, in other words,
    how much time has passed since this envelope started.
    
    Is expected to wrap back to `TIME_START` once `TIME_END` is reached.
    """

    value: float

    def __post_init__(self):
        assert TIME_START <= self.time <= TIME_END
        assert AMPLITUDE_MIN <= self.value <= AMPLITUDE_MAX


def offset_envelopes(
    envelopes_settings: Sequence[EnvelopeSettings], interval: float, time: float
) -> list[EnvelopeStatus]:
    """Function calculating values at `time` for envelopes defined by `envelopes_settings`
    spaced apart evenly with peaks occurring every `interval`."""
    envelopes_status: list[EnvelopeStatus] = []
    for i, env_settings in enumerate(envelopes_settings):
        env_time = (time - interval * i) % TIME_END
        value = a_d_envelope(env_settings, env_time)
        envelopes_status.append(EnvelopeStatus(time=env_time, value=value))

    return envelopes_status


class CombineFn(Protocol):
    @staticmethod
    def __call__(left: EnvelopeStatus, right: EnvelopeStatus) -> float: ...


def combine_envelopes(
    envelopes_settings: Sequence[EnvelopeSettings],
    envelopes_status: Sequence[EnvelopeStatus],
    combiner: CombineFn,
) -> float:
    """
    Find the two envelopes whose peaks are currently closest and call `combiner`
    on them to get a combined value.

    Consider the example below, where `envelopes_status` has eight elements,
    represented by the letters a-h. `y` is the value of the `EnvelopeStatus.time` attribute,
    `x` is the global timeline, `t` is the current global time.

    ```
                  y
         TIME_END ^    a b c d e f g h
                  |    / / / / / / / /
                  |   / / / / / / / /
    TIME_MIDPOINT |  / /⊙/ / / / / /
                  | / / / / / / / /
                  |/ / /|/ / / / /
       TIME_START +--------------------> x
                        |
                        t
    ```

    The `⊙` is the point that we are trying to inspect, where `x=time` and
    `status.time=TIME_MIDPOINT`. Specifically, we're trying to find the two envelopes to
    the left and to the right of `⊙` because those are the two whose peaks the current
    `time` lies between, meaning they are the ones we need to combine.

    The above illustration is somewhat inaccurate; the slope of the envelopes' time-value
    might be much shallower and they might be closer together, so it is very possible that multiple
    slopes overlap at once.

    Disabled envelopes are skipped, so in the above example, if `c` and `d` were disabled,
    envelope `b` would be combined with `e` if `b`'s decay slope overlaps with `e`'s attack slope.
    """
    # Discard all envelopes that are disabled so combining longer envelopes that aren't
    # directly adjacent to each other works as expected
    active_envelopes: list[EnvelopeStatus] = []
    for settings, status in zip(envelopes_settings, envelopes_status, strict=True):
        if settings.is_disabled():
            continue
        active_envelopes.append(status)

    # In the rare but possible case that all envelopes are disabled,
    # we cannot call `combiner` and have to return 0
    if len(active_envelopes) < 1:
        return 0.0

    # If only one envelope is active there is nothing to combine;
    # calling the combiner with the same envelope on both sides would be
    # meaningless (and would cause ZeroDivisionError for the linear combiner)
    if len(active_envelopes) == 1:
        return active_envelopes[0].value

    # Find the pair of envelopes we need to combine at the current point in time
    for left, right in pairwise((*active_envelopes, active_envelopes[0])):
        if left.time > TIME_MIDPOINT >= right.time:
            return combiner(left, right)

    # It is possible that no pair was found. This can happen if they are spaced at
    # an interval that is less than `(TIME_END - TIME_START) / len(envelopes)` or
    # if a lot of the later envelopes were disabled.
    # In this case, we always have the last active envelope on the left and the
    # first on the right.
    return combiner(active_envelopes[-1], active_envelopes[0])


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
