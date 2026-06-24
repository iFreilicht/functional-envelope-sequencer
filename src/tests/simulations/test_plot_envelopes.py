"""Tests for scripts.plot_envelopes (excluding the matplotlib rendering path).

Covers:
- Envelope string parsing
- Interval validation and clamping
- Time-sequence generation
- Tab-separated values output (--format values)
- CLI end-to-end via click.testing.CliRunner
"""

from contextlib import contextmanager
from logging import WARNING
from typing import TYPE_CHECKING, Any

import click
import pytest
from click.testing import CliRunner
from loguru import logger
from simulations.envelope import (
    INTERVAL_MAX,
    INTERVAL_MIN,
    EnvelopeSettings,
)

# loguru's Message type is only defined in the type stubs
if TYPE_CHECKING:
    from loguru import Message
else:
    Message = Any

from scripts.plot_envelopes import _parse_envelope_string, main


@contextmanager
def _save_loguru_messages(containing: str | None = None, of_level: int | None = None):
    """Context-Manager returning a list of ``loguru.Message``s that will contain
    all messages matching the filter criteria which are logged by loguru from
    functions that execute inside the Context-Manager."""
    msgs: list[Message] = []

    def save_msgs(msg: Message):
        if (containing is None or containing in msg) and (
            of_level is None or msg.record["level"].no == of_level
        ):
            msgs.append(msg)

    save_msgs_handler = logger.add(save_msgs)
    yield msgs
    logger.remove(save_msgs_handler)


# ---------------------------------------------------------------------------
# _parse_envelope_string
# ---------------------------------------------------------------------------


class TestParseEnvelopeString:
    def test_parses_valid_string(self):
        result = _parse_envelope_string("attack=0.3,decay=0.5,shape=0.8,amplitude=1.0")
        assert isinstance(result, EnvelopeSettings)
        assert result.attack == pytest.approx(0.3)
        assert result.decay == pytest.approx(0.5)
        assert result.shape == pytest.approx(0.8)
        assert result.amplitude == pytest.approx(1.0)

    def test_order_independent(self):
        """Keys can appear in any order."""
        a = _parse_envelope_string("attack=0.3,decay=0.5,shape=0.8,amplitude=1.0")
        b = _parse_envelope_string("amplitude=1.0,shape=0.8,decay=0.5,attack=0.3")
        assert a == b

    def test_whitespace_tolerant(self):
        """Spaces around keys and values should not cause a failure."""
        result = _parse_envelope_string(
            "attack = 0.3, decay = 0.5, shape = 0.8, amplitude = 1.0"
        )
        assert result.attack == pytest.approx(0.3)

    def test_raises_on_unknown_key(self):
        with pytest.raises(click.BadParameter, match="Unknown envelope parameter"):
            _ = _parse_envelope_string(
                "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0,extra=0.0"
            )

    def test_raises_on_missing_key(self):
        with pytest.raises(click.BadParameter, match="Missing envelope parameters"):
            _ = _parse_envelope_string("attack=0.3,decay=0.5,shape=0.8")

    def test_raises_on_non_float_value(self):
        with pytest.raises(click.BadParameter, match="must be a float"):
            _ = _parse_envelope_string("attack=abc,decay=0.5,shape=0.8,amplitude=1.0")

    def test_raises_on_out_of_range_value(self):
        """Values that fail EnvelopeSettings __post_init__ assertions are re-raised
        as BadParameter."""
        # attack=0.0 is below SLOPE_TIME_MIN and will be rejected by clamp_checked
        with pytest.raises(click.BadParameter):
            _ = _parse_envelope_string("attack=0.0,decay=0.5,shape=0.8,amplitude=1.0")


# ---------------------------------------------------------------------------
# CLI — values output (no matplotlib)
# ---------------------------------------------------------------------------

_BASE_ARGS = [
    "--start",
    "0",
    "--end",
    "1",
    "--rate",
    "4",
    "--envelope",
    "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0",
    "--envelope",
    "attack=0.4,decay=0.4,shape=0.2,amplitude=0.8",
    "--interval",
    "0.25",
    "--format",
    "values",
]


def _data_lines(output: str) -> list[str]:
    """Return only the numeric data lines (time\\tvalue), skipping log/header lines."""
    result: list[str] = []
    for line in output.splitlines():
        if "\t" not in line:
            continue
        try:
            _ = float(line.split("\t")[0].strip())
        except ValueError:
            continue
        else:
            result.append(line)
    return result


class TestCLIValues:
    def test_exit_zero(self):
        runner = CliRunner()
        result = runner.invoke(main, _BASE_ARGS, catch_exceptions=False)
        assert result.exit_code == 0, result.output

    def test_output_has_correct_number_of_lines(self):
        """--start 0 --end 1 --rate 4 → 5 samples (0, 0.25, 0.5, 0.75, 1.0)."""
        runner = CliRunner()
        result = runner.invoke(main, _BASE_ARGS, catch_exceptions=False)
        lines = _data_lines(result.output)
        assert len(lines) == 5

    def test_output_is_tab_separated_two_columns(self):
        runner = CliRunner()
        result = runner.invoke(main, _BASE_ARGS, catch_exceptions=False)
        for line in _data_lines(result.output):
            parts = line.split("\t")
            assert len(parts) == 2, f"Expected 2 tab-separated columns, got: {line!r}"
            _ = float(parts[0])  # must parse as float
            _ = float(parts[1])  # must parse as float

    def test_time_column_matches_expected_sequence(self):
        runner = CliRunner()
        result = runner.invoke(main, _BASE_ARGS, catch_exceptions=False)
        times = [float(line.split("\t")[0]) for line in _data_lines(result.output)]
        expected = [0.0, 0.25, 0.5, 0.75, 1.0]
        assert len(times) == len(expected)
        for t, e in zip(times, expected, strict=True):
            assert t == pytest.approx(e)

    def test_values_in_range(self):
        runner = CliRunner()
        result = runner.invoke(main, _BASE_ARGS, catch_exceptions=False)
        for line in _data_lines(result.output):
            v = float(line.split("\t")[1])
            assert 0.0 <= v <= 1.0 + 1e-9, f"Out-of-range value: {v}"


# ---------------------------------------------------------------------------
# CLI — interval validation
# ---------------------------------------------------------------------------


class TestCLIIntervalValidation:
    def _args_with_interval(self, interval: str) -> list[str]:
        return [
            "--start",
            "0",
            "--end",
            "1",
            "--rate",
            "4",
            "--envelope",
            "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0",
            "--envelope",
            "attack=0.4,decay=0.4,shape=0.2,amplitude=0.8",
            "--interval",
            interval,
            "--format",
            "values",
        ]

    def test_valid_interval_succeeds(self):
        runner = CliRunner()
        result = runner.invoke(
            main, self._args_with_interval("0.25"), catch_exceptions=False
        )
        assert result.exit_code == 0

    def test_interval_below_min_fails(self):
        runner = CliRunner()
        below = str(INTERVAL_MIN / 2)
        result = runner.invoke(main, self._args_with_interval(below))
        assert result.exit_code != 0
        assert "outside the valid range" in result.output

    def test_interval_above_max_fails(self):
        runner = CliRunner()
        above = str(INTERVAL_MAX * 2)
        result = runner.invoke(main, self._args_with_interval(above))
        assert result.exit_code != 0
        assert "outside the valid range" in result.output

    def test_auto_interval_clamps_without_error(self):
        """With 2 envelopes and no --interval, auto = TIME_END / 2 = 1.0 > INTERVAL_MAX.
        The CLI should clamp with a warning on stderr and still produce valid output."""
        runner = CliRunner()
        args = [
            "--start",
            "0",
            "--end",
            "1",
            "--rate",
            "4",
            "--envelope",
            "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0",
            "--envelope",
            "attack=0.4,decay=0.4,shape=0.2,amplitude=0.8",
            "--format",
            "values",
        ]
        with _save_loguru_messages(of_level=WARNING) as msgs:
            result = runner.invoke(main, args, catch_exceptions=False)

        assert "clamped" in msgs[0]
        assert result.exit_code == 0
        assert len(_data_lines(result.output)) == 5


# ---------------------------------------------------------------------------
# CLI — combiner choice
# ---------------------------------------------------------------------------


class TestCLICombinerChoice:
    def _args_with_combiner(self, combiner: str) -> list[str]:
        return [
            "--start",
            "0",
            "--end",
            "1",
            "--rate",
            "4",
            "--envelope",
            "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0",
            "--envelope",
            "attack=0.4,decay=0.4,shape=0.2,amplitude=0.8",
            "--interval",
            "0.25",
            "--combiner",
            combiner,
            "--format",
            "values",
        ]

    @pytest.mark.parametrize("combiner", ["max", "linear"])
    def test_valid_combiner_exits_zero(self, combiner: str):
        runner = CliRunner()
        result = runner.invoke(
            main, self._args_with_combiner(combiner), catch_exceptions=False
        )
        assert result.exit_code == 0

    def test_invalid_combiner_fails(self):
        runner = CliRunner()
        result = runner.invoke(main, self._args_with_combiner("nonexistent"))
        assert result.exit_code != 0

    def test_max_and_linear_give_different_outputs(self):
        """The two combiners should produce distinct outputs for the same input."""
        runner = CliRunner()
        max_result = runner.invoke(
            main, self._args_with_combiner("max"), catch_exceptions=False
        )
        lin_result = runner.invoke(
            main, self._args_with_combiner("linear"), catch_exceptions=False
        )
        assert max_result.output != lin_result.output


# ---------------------------------------------------------------------------
# CLI — edge cases
# ---------------------------------------------------------------------------


class TestCLIEdgeCases:
    def test_single_envelope_with_explicit_interval(self):
        """A single envelope with --interval should not crash."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--start",
                "0",
                "--end",
                "2",
                "--rate",
                "5",
                "--envelope",
                "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0",
                "--interval",
                "0.25",
                "--format",
                "values",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

    def test_missing_envelope_fails(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--start",
                "0",
                "--end",
                "1",
                "--rate",
                "4",
                "--format",
                "values",
            ],
        )
        assert result.exit_code != 0

    def test_start_equals_end_gives_one_sample(self):
        """When start == end, exactly one sample should be produced."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--start",
                "0.5",
                "--end",
                "0.5",
                "--rate",
                "10",
                "--envelope",
                "attack=0.3,decay=0.5,shape=0.8,amplitude=1.0",
                "--envelope",
                "attack=0.4,decay=0.4,shape=0.2,amplitude=0.8",
                "--interval",
                "0.25",
                "--format",
                "values",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        lines = _data_lines(result.output)
        assert len(lines) == 1

    def test_malformed_envelope_fails_with_helpful_message(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--start",
                "0",
                "--end",
                "1",
                "--rate",
                "4",
                "--envelope",
                "notvalid",
                "--format",
                "values",
            ],
        )
        assert result.exit_code != 0
        # Should mention the problematic parameter
        assert "--envelope" in result.output
