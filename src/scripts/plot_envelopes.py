"""CLI for visualising offset and combined envelopes.

Usage examples::

    # Interactive plot (default)
    plot-envelopes --start 0 --end 4 --rate 100 \\
        --envelope "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0" \\
        --envelope "attack=0.4,decay=0.4,shape=0.2,amplitude=0.8" \\
        --combiner max

    # Print tab-separated time/value pairs to stdout
    plot-envelopes --start 0 --end 2 --rate 50 \\
        --envelope "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0" \\
        --envelope "attack=0.4,decay=0.4,shape=0.2,amplitude=0.8" \\
        --combiner linear --format values
"""

import click
import matplotlib.pyplot as plt
from loguru import logger
from simulations.combiners import COMBINERS, CombineFn
from simulations.compute import compute_values
from simulations.envelope import (
    INTERVAL_MAX,
    INTERVAL_MIN,
    TIME_END,
    EnvelopeSettings,
    EnvelopeStatus,
)


def _parse_envelope_string(raw: str) -> EnvelopeSettings:
    """Parse ``"attack=F,decay=F,shape=F,amplitude=F"`` into an EnvelopeSettings.

    Raises :exc:`click.BadParameter` on malformed input or out-of-range values.
    """
    expected_keys = {"attack", "decay", "shape", "amplitude"}
    pairs: dict[str, float] = {}
    for token in raw.split(","):
        key, _, val = token.partition("=")
        key = key.strip()
        if key not in expected_keys:
            msg = (
                f"Unknown envelope parameter {key!r}. "
                f"Expected one of {sorted(expected_keys)}"
            )
            raise click.BadParameter(msg, param_hint="'--envelope'")
        try:
            pairs[key] = float(val.strip())
        except ValueError:
            msg = f"Value for {key!r} must be a float, got {val.strip()!r}"
            raise click.BadParameter(msg, param_hint="'--envelope'") from None
    missing = expected_keys - pairs.keys()
    if missing:
        msg = f"Missing envelope parameters: {sorted(missing)}"
        raise click.BadParameter(msg, param_hint="'--envelope'")
    try:
        return EnvelopeSettings(
            attack=pairs["attack"],
            decay=pairs["decay"],
            shape=pairs["shape"],
            amplitude=pairs["amplitude"],
        )
    except AssertionError as exc:
        raise click.BadParameter(str(exc), param_hint="'--envelope'") from exc


def _output_plot(
    envelopes: list[EnvelopeSettings],
    times: list[float],
    samples_per_envelope: list[list[EnvelopeStatus]],
    values_combined: list[float],
) -> None:
    logger.info("Displaying plot of separate and combined envelope")
    _, ax = plt.subplots(figsize=(10, 6))
    for i, (env, samples) in enumerate(
        zip(envelopes, samples_per_envelope, strict=True)
    ):
        label = f"Env {i + 1} (a={env.attack:.2f}, d={env.decay:.2f})"
        _ = ax.plot(times, [s.value for s in samples], label=label)  # pyright: ignore[reportUnknownMemberType]
    _ = ax.plot(times, values_combined, label="combined", color="black", linewidth=2.5)  # pyright: ignore[reportUnknownMemberType]
    _ = ax.set_xlabel("time")  # pyright: ignore[reportUnknownMemberType]
    _ = ax.set_ylabel("value")  # pyright: ignore[reportUnknownMemberType]
    _ = ax.set_title("Envelope Combination")  # pyright: ignore[reportUnknownMemberType]
    _ = ax.legend(loc="upper right")  # pyright: ignore[reportUnknownMemberType]
    ax.grid(visible=True, alpha=0.3)  # pyright: ignore[reportUnknownMemberType]
    plt.show()  # pyright: ignore[reportUnknownMemberType]


def _output_values(times: list[float], values_combined: list[float]) -> None:
    logger.info("Printing time and value of combined envelope")
    click.echo("time\t\tvalue")
    for t, v in zip(times, values_combined, strict=True):
        click.echo(f"{t:.6f}\t{v:.6f}")


@click.command()
@click.option("--start", type=float, required=True, help="Start time.")
@click.option("--end", type=float, required=True, help="End time.")
@click.option("--rate", type=int, required=True, help="Samples per unit time.")
@click.option(
    "--envelope",
    type=str,
    multiple=True,
    required=True,
    help="Envelope spec: 'attack=F,decay=F,shape=F,amplitude=F'. Repeatable.",
)
@click.option(
    "--interval",
    type=float,
    default=None,
    show_default=False,
    help="Peak spacing interval. Defaults to TIME_END / number-of-envelopes.",
)
@click.option(
    "--combiner",
    type=click.Choice(list(COMBINERS.keys())),
    default="max",
    show_default=True,
    help="Combiner function.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["plot", "values"]),
    default="plot",
    show_default=True,
    help="Output mode: 'plot' opens a matplotlib figure, 'values' prints samples.",
)
def main(  # noqa: PLR0913
    start: float,
    end: float,
    rate: int,
    envelope: tuple[str, ...],
    interval: float | None,
    combiner: str,
    output_format: str,
) -> None:
    """Visualise offset and combined envelopes over a time range."""
    envelopes = [_parse_envelope_string(raw) for raw in envelope]
    logger.info("Loaded {} envelopes", len(envelopes))

    if interval is not None:
        if not INTERVAL_MIN <= interval <= INTERVAL_MAX:
            msg = (
                f"Interval {interval} is outside the valid range "
                f"[{INTERVAL_MIN}, {INTERVAL_MAX}]."
            )
            raise click.BadParameter(msg, param_hint="'--interval'")
        resolved_interval = interval
    else:
        auto = TIME_END / len(envelopes)
        resolved_interval = max(INTERVAL_MIN, min(auto, INTERVAL_MAX))
        if resolved_interval != auto:
            logger.warning(
                "Auto-computed interval {:.4f} is outside [{}, {}]; clamped to"
                " {:.4f}. Pass --interval explicitly to control this.",
                auto,
                INTERVAL_MIN,
                INTERVAL_MAX,
                resolved_interval,
            )
    logger.info("Using interval {:.4f}", resolved_interval)

    combine_fn: CombineFn = COMBINERS[combiner]

    n_samples = int((end - start) * rate) + 1
    times: list[float] = [start + i / rate for i in range(n_samples)]
    logger.info("Computing {} samples from {} to {}", n_samples, start, end)

    samples_per_envelope, values_combined = compute_values(
        envelopes, resolved_interval, times, combine_fn
    )

    if output_format == "plot":
        _output_plot(envelopes, times, samples_per_envelope, values_combined)
    else:
        _output_values(times, values_combined)
