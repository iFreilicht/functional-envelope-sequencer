import math


def a_d_shape(shape: float, progress: float) -> float:
    r"""Function describing the shape of an attack- or decay-slope.

    If `shape` is $s$ and `progress` is $x$:

    $$f\left(x\right)=\left(1-s\right)x^{\left(1+s\right)}+sx^{10^{s}}$$
    """
    assert 0 <= progress <= 1.001
    assert 0 <= shape <= 1
    EXPONENT = 10.0  # Exponent for "quadratic" envelope, eyeballed in Desmos
    s, x = shape, progress
    lin = x  # Linear envelope, should be the only one when shape is 0
    quad = math.pow(
        x, math.pow(EXPONENT, s)
    )  # "Quadratic" envelope, should be the only one when shape is 1
    # Interpolation is not quite linear, but looks very natural when sweeping over s
    interpolated = (1 - s) * math.pow(lin, (1 + s)) + s * quad
    return interpolated


TIME_START = 0
TIME_END = 2
TIME_MIDPOINT = (TIME_START + TIME_END) / 2

SHAPE_MIN = 0
SHAPE_MAX = 1


def a_d_envelope(
    attack: float, decay: float, shape: float, amplitude: float, time: float
) -> float:
    """Function describing a single Attack/Decay (A/D) envelope that is fixed in an interval between
    `time=TIME_START` and `time=TIME_END`, with the peak always occurring at `time=TIME_MIDPOINT`.

    `attack` is the time it takes for the attack-slope to reach the peak when starting at level 0.
    `decay` is the time it takes for the delay-slope to reach level 0 when starting from the peak.

    1. From `TIME_START` to `TIME_MIDPOINT - attack`, return 0
    2. From `TIME_MIDPOINT - attack` to `TIME_MIDPOINT`, return the attack envelope based on `shape`
    3. From `TIME_MIPOINT` to `TIME_MIDPOINT + decay`, return the decay envelope based on `shape`
    4. From `TIME_MIDPOINT + decay` to `TIME_END`, return 0
    """
    assert TIME_START <= attack <= TIME_MIDPOINT
    assert TIME_START <= decay <= TIME_MIDPOINT
    assert SHAPE_MIN <= shape <= SHAPE_MAX
    assert TIME_START <= time <= TIME_END
    if amplitude < 0.01:
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
