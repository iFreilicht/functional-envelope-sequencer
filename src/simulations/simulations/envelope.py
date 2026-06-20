from dataclasses import dataclass
import math

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
TIME_START = 0.0
TIME_END = 2.0
TIME_MIDPOINT = (TIME_START + TIME_END) / 2


def a_d_shape(shape: float, progress: float) -> float:
    r"""Function describing the shape of an attack- or decay-slope.

    If `shape` is $s$ and `progress` is $x$:

    $$f\left(x\right)=\left(1-s\right)x^{\left(1+s\right)}+sx^{10^{s}}$$
    """
    assert PROGRESS_MIN <= progress <= PROGRESS_MAX
    assert SHAPE_MIN <= shape <= SHAPE_MAX

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
    3. From `TIME_MIPOINT` to `TIME_MIDPOINT + decay`, return the decay envelope based on `shape`
    4. From `TIME_MIDPOINT + decay` to `TIME_END`, return 0
    """
    attack, decay, shape, amplitude = (
        settings.attack,
        settings.decay,
        settings.shape,
        settings.amplitude,
    )

    assert TIME_START <= time <= TIME_END
    if amplitude < settings.is_disabled():
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
    value: float


def offset_envelopes(
    envelopes_settings: list[EnvelopeSettings], time: float
) -> list[EnvelopeStatus]:
    """Function calculating offset envelope values."""
    envelopes_status: list[EnvelopeStatus] = []
    # TODO: How can I know the number of envelopes in practice? For example,
    # when a user connects the time-output of one envelope to the time-input
    # of another to create a shortcut? Is that just an impossible feature?
    num_envs = len(envelopes_settings)
    offset = (TIME_START + TIME_END) / num_envs
    times_offset = [(time - offset * i) % TIME_END for i in range(num_envs)]
    for env_settings, env_time in zip(envelopes_settings, times_offset):
        value = a_d_envelope(env_settings, env_time)
        envelopes_status.append(EnvelopeStatus(time=env_time, value=value))

    return envelopes_status
