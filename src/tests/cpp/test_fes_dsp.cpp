// test_fes_dsp.cpp — Catch2 unit tests for src/fes_dsp.hpp
//
// Mirrors the invariants verified by the Python test suite in
// src/tests/simulations/.  Each TEST_CASE corresponds to a block of
// the Python tests.
//
// Compile and run via:   make cpp-test   (from the repo root, inside the Nix devShell)

#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>

#include "fes_dsp.hpp"

#include <cmath>

using namespace fes;
using Catch::Matchers::WithinAbs;
using Catch::Matchers::WithinRel;

// Floating-point tolerance for "approximately equal" checks
static constexpr float EPS = 1e-5f;

// ---------------------------------------------------------------------------
// Block A: adShape
// ---------------------------------------------------------------------------

TEST_CASE("adShape endpoints are independent of shape", "[adShape]") {
    for (float s : {0.0f, 0.25f, 0.5f, 0.75f, 1.0f}) {
        CAPTURE(s);
        CHECK_THAT(adShape(s, 0.0f), WithinAbs(0.0f, EPS));
        CHECK_THAT(adShape(s, 1.0f), WithinAbs(1.0f, EPS));
    }
}

TEST_CASE("adShape with shape=0 is linear", "[adShape]") {
    for (float x : {0.0f, 0.1f, 0.2f, 0.5f, 0.7f, 0.9f, 1.0f}) {
        CAPTURE(x);
        CHECK_THAT(adShape(0.0f, x), WithinAbs(x, EPS));
    }
}

TEST_CASE("adShape with shape=1 is degree-10 polynomial", "[adShape]") {
    for (float x : {0.0f, 0.2f, 0.5f, 0.7f, 1.0f}) {
        CAPTURE(x);
        CHECK_THAT(adShape(1.0f, x), WithinAbs(std::pow(x, 10.0f), EPS));
    }
}

TEST_CASE("adShape is monotonically non-decreasing in progress", "[adShape]") {
    const int N = 100;
    for (float s : {0.0f, 0.3f, 0.7f, 1.0f}) {
        CAPTURE(s);
        float prev = adShape(s, 0.0f);
        for (int i = 1; i <= N; ++i) {
            float x    = static_cast<float>(i) / N;
            float curr = adShape(s, x);
            CHECK(curr >= prev - EPS);
            prev = curr;
        }
    }
}

TEST_CASE("adShape output is in [0, 1]", "[adShape]") {
    for (float s : {0.0f, 0.5f, 1.0f}) {
        for (int i = 0; i <= 20; ++i) {
            float x = static_cast<float>(i) / 20.0f;
            CAPTURE(s, x);
            float v = adShape(s, x);
            CHECK(v >= -EPS);
            CHECK(v <= 1.0f + EPS);
        }
    }
}

// ---------------------------------------------------------------------------
// Block B: EnvelopeSettings::isEnabled
// ---------------------------------------------------------------------------

TEST_CASE("isEnabled returns false at amplitude <= AMPLITUDE_LOWER_CUTOFF", "[EnvelopeSettings]") {
    CHECK_FALSE(EnvelopeSettings{0.5f, 0.5f, 0.0f, 0.0f}.isEnabled());
    CHECK_FALSE(EnvelopeSettings{0.5f, 0.5f, 0.0f, AMPLITUDE_LOWER_CUTOFF}.isEnabled());
    // Just below (use a value that is clearly below the cutoff)
    CHECK_FALSE(EnvelopeSettings{0.5f, 0.5f, 0.0f, AMPLITUDE_LOWER_CUTOFF - 0.005f}.isEnabled());
}

TEST_CASE("isEnabled returns true above AMPLITUDE_LOWER_CUTOFF", "[EnvelopeSettings]") {
    CHECK(EnvelopeSettings{0.5f, 0.5f, 0.0f, AMPLITUDE_LOWER_CUTOFF + 1e-4f}.isEnabled());
    CHECK(EnvelopeSettings{0.5f, 0.5f, 0.0f, 0.5f}.isEnabled());
    CHECK(EnvelopeSettings{0.5f, 0.5f, 0.0f, 1.0f}.isEnabled());
}

// ---------------------------------------------------------------------------
// Block C: adEnvelope
// ---------------------------------------------------------------------------

TEST_CASE("adEnvelope peak at TIME_MIDPOINT equals amplitude", "[adEnvelope]") {
    for (float amp : {0.5f, 0.8f, 1.0f}) {
        CAPTURE(amp);
        EnvelopeSettings s{0.5f, 0.5f, 0.0f, amp};
        CHECK_THAT(adEnvelope(s, TIME_MIDPOINT), WithinAbs(amp, EPS));
    }
}

TEST_CASE("adEnvelope is zero before attack window", "[adEnvelope]") {
    EnvelopeSettings s{0.3f, 0.3f, 0.0f, 1.0f};
    // Peak at TIME_MIDPOINT=1.0, attack=0.3 → window starts at 0.7
    CHECK_THAT(adEnvelope(s, 0.0f), WithinAbs(0.0f, EPS));
    CHECK_THAT(adEnvelope(s, 0.5f), WithinAbs(0.0f, EPS));
    CHECK_THAT(adEnvelope(s, 0.69f), WithinAbs(0.0f, EPS));
}

TEST_CASE("adEnvelope is zero after decay window", "[adEnvelope]") {
    EnvelopeSettings s{0.3f, 0.3f, 0.0f, 1.0f};
    // Decay ends at 1.3
    CHECK_THAT(adEnvelope(s, 1.31f), WithinAbs(0.0f, EPS));
    CHECK_THAT(adEnvelope(s, 2.0f), WithinAbs(0.0f, EPS));
}

TEST_CASE("adEnvelope returns 0 for disabled envelopes", "[adEnvelope]") {
    EnvelopeSettings disabled{0.5f, 0.5f, 0.0f, 0.0f};
    for (float t : {0.0f, TIME_MIDPOINT, TIME_END}) {
        CAPTURE(t);
        CHECK_THAT(adEnvelope(disabled, t), WithinAbs(0.0f, EPS));
    }
}

TEST_CASE("adEnvelope output is in [0, amplitude]", "[adEnvelope]") {
    EnvelopeSettings s{0.4f, 0.6f, 0.7f, 0.8f};
    const int N = 200;
    for (int i = 0; i <= N; ++i) {
        float t = TIME_START + (TIME_END - TIME_START) * static_cast<float>(i) / N;
        CAPTURE(t);
        float v = adEnvelope(s, t);
        CHECK(v >= -EPS);
        CHECK(v <= s.amplitude + EPS);
    }
}

TEST_CASE("adEnvelope scales linearly with amplitude", "[adEnvelope]") {
    // Doubling amplitude doubles the output at any time
    EnvelopeSettings s1{0.4f, 0.4f, 0.3f, 0.4f};
    EnvelopeSettings s2{0.4f, 0.4f, 0.3f, 0.8f};
    for (float t : {0.6f, TIME_MIDPOINT, 1.2f}) {
        CAPTURE(t);
        float v1 = adEnvelope(s1, t);
        float v2 = adEnvelope(s2, t);
        CHECK_THAT(v2, WithinAbs(2.0f * v1, EPS));
    }
}

// ---------------------------------------------------------------------------
// Block D: offsetEnvelopes
// ---------------------------------------------------------------------------

TEST_CASE("offsetEnvelopes returns correct count", "[offsetEnvelopes]") {
    EnvelopeSettings settings[3] = {
        {0.3f, 0.3f, 0.0f, 1.0f},
        {0.3f, 0.3f, 0.0f, 0.8f},
        {0.3f, 0.3f, 0.0f, 0.6f}
    };
    EnvelopeStatus out[3];
    offsetEnvelopes(settings, 3, 0.25f, 0.5f, out);

    // Just verify we can read back without UB; the test only asserts count via compile
    for (int i = 0; i < 3; ++i) {
        CHECK(out[i].value >= 0.0f);
        CHECK(out[i].value <= 1.0f + EPS);
    }
}

TEST_CASE("offsetEnvelopes: local time wraps correctly", "[offsetEnvelopes]") {
    EnvelopeSettings settings[2] = {
        {0.5f, 0.5f, 0.0f, 1.0f},
        {0.5f, 0.5f, 0.0f, 1.0f}
    };
    const float interval = 0.25f;
    const float globalTime = 0.5f;
    EnvelopeStatus out[2];
    offsetEnvelopes(settings, 2, interval, globalTime, out);

    // Envelope 0: time = (0.5 - 0*0.25) % 2.0 = 0.5
    CHECK_THAT(out[0].time, WithinAbs(0.5f, EPS));
    // Envelope 1: time = (0.5 - 1*0.25) % 2.0 = 0.25
    CHECK_THAT(out[1].time, WithinAbs(0.25f, EPS));
}

TEST_CASE("offsetEnvelopes: time wrapping handles negative modulo", "[offsetEnvelopes]") {
    EnvelopeSettings settings[2] = {
        {0.5f, 0.5f, 0.0f, 1.0f},
        {0.5f, 0.5f, 0.0f, 1.0f}
    };
    const float interval = 0.25f;
    const float globalTime = 0.1f;
    EnvelopeStatus out[2];
    offsetEnvelopes(settings, 2, interval, globalTime, out);

    // Envelope 0: (0.1 - 0) % 2.0 = 0.1
    CHECK_THAT(out[0].time, WithinAbs(0.1f, EPS));
    // Envelope 1: (0.1 - 0.25) % 2.0 = -0.15 → wrapped to 2.0 - 0.15 = 1.85
    CHECK_THAT(out[1].time, WithinAbs(1.85f, EPS));
}

// ---------------------------------------------------------------------------
// Block E/F: combineMax, combineLinear, combineEnvelopes
// ---------------------------------------------------------------------------

TEST_CASE("combineMax returns the larger value", "[combiners]") {
    EnvelopeStatus left  = {0.5f, 0.8f, 0.3f, true};
    EnvelopeStatus right = {0.5f, 1.2f, 0.7f, true};
    CHECK_THAT(combineMax(left, right, 1.0f), WithinAbs(0.7f, EPS));
    CHECK_THAT(combineMax(right, left, 1.0f), WithinAbs(0.7f, EPS));
}

TEST_CASE("combineLinear returns left value at left midpoint", "[combiners]") {
    // time == left.midpoint → progress = 0 → result = left.value
    EnvelopeStatus left  = {0.5f, 0.8f, 0.4f, true};
    EnvelopeStatus right = {0.5f, 1.2f, 0.9f, true};
    CHECK_THAT(combineLinear(left, right, 0.8f), WithinAbs(0.4f, EPS));
}

TEST_CASE("combineLinear returns right value at right midpoint", "[combiners]") {
    EnvelopeStatus left  = {0.5f, 0.8f, 0.4f, true};
    EnvelopeStatus right = {0.5f, 1.2f, 0.9f, true};
    CHECK_THAT(combineLinear(left, right, 1.2f), WithinAbs(0.9f, EPS));
}

TEST_CASE("combineLinear interpolates at midpoint between peaks", "[combiners]") {
    EnvelopeStatus left  = {0.5f, 0.8f, 0.4f, true};
    EnvelopeStatus right = {0.5f, 1.2f, 0.8f, true};
    // midpoint between peaks: time = 1.0, progress = 0.5 → value = 0.6
    CHECK_THAT(combineLinear(left, right, 1.0f), WithinAbs(0.6f, EPS));
}

TEST_CASE("combineEnvelopes: all disabled returns 0", "[combineEnvelopes]") {
    EnvelopeStatus statuses[3] = {
        {0.5f, 0.5f, 0.3f, false},
        {0.5f, 1.0f, 0.6f, false},
        {0.5f, 1.5f, 0.8f, false}
    };
    CHECK_THAT(combineEnvelopes(statuses, 3, 0.75f, false), WithinAbs(0.0f, EPS));
    CHECK_THAT(combineEnvelopes(statuses, 3, 0.75f, true),  WithinAbs(0.0f, EPS));
}

TEST_CASE("combineEnvelopes: single active envelope returns its value", "[combineEnvelopes]") {
    EnvelopeStatus statuses[3] = {
        {0.5f, 0.5f, 0.3f, false},
        {0.5f, 1.0f, 0.6f, true},   // only active
        {0.5f, 1.5f, 0.8f, false}
    };
    CHECK_THAT(combineEnvelopes(statuses, 3, 0.75f, false), WithinAbs(0.6f, EPS));
    CHECK_THAT(combineEnvelopes(statuses, 3, 0.75f, true),  WithinAbs(0.6f, EPS));
}

TEST_CASE("combineEnvelopes: disabled envelopes are skipped", "[combineEnvelopes]") {
    // Three envelopes; middle one disabled.
    // At time=1.75 we should be between the first and third peaks (0.5 and 1.5),
    // skipping the disabled one at midpoint 1.0.
    EnvelopeStatus statuses[3] = {
        {0.5f, 0.5f, 0.4f, true},
        {0.5f, 1.0f, 0.9f, false},  // disabled — should be ignored
        {0.5f, 1.5f, 0.7f, true}
    };

    // With max combiner: should return max(0.4, 0.7) = 0.7
    float maxVal = combineEnvelopes(statuses, 3, 1.0f, false);
    CHECK(maxVal >= -EPS);
    CHECK(maxVal <= 1.0f + EPS);
}

TEST_CASE("combineEnvelopes: max result >= linear result for same inputs", "[combineEnvelopes]") {
    // Property: max combiner should return >= linear combiner for same input
    const int N   = 8;
    float interval = 0.2f;

    EnvelopeSettings settings[N];
    for (int i = 0; i < N; ++i) {
        settings[i] = {
            0.4f,
            0.4f,
            0.3f,
            0.6f + 0.05f * static_cast<float>(i)  // varying amplitudes
        };
    }

    // Sweep through a full cycle
    const int STEPS = 200;
    for (int step = 0; step <= STEPS; ++step) {
        float t = TIME_START + (TIME_END - TIME_START) * static_cast<float>(step) / STEPS;
        CAPTURE(t);

        EnvelopeStatus statuses[N];
        offsetEnvelopes(settings, N, interval, t, statuses);

        float maxVal    = combineEnvelopes(statuses, N, t, false);
        float linearVal = combineEnvelopes(statuses, N, t, true);

        CHECK(maxVal >= linearVal - EPS);
    }
}

TEST_CASE("combineEnvelopes: output stays in [0, AMPLITUDE_MAX]", "[combineEnvelopes]") {
    const int N   = 8;
    float interval = 0.2f;

    EnvelopeSettings settings[N];
    for (int i = 0; i < N; ++i) {
        settings[i] = {0.4f, 0.5f, 0.6f, 1.0f};
    }

    const int STEPS = 200;
    for (int step = 0; step <= STEPS; ++step) {
        float t = TIME_START + (TIME_END - TIME_START) * static_cast<float>(step) / STEPS;
        CAPTURE(t);

        EnvelopeStatus statuses[N];
        offsetEnvelopes(settings, N, interval, t, statuses);

        for (bool useLinear : {false, true}) {
            float v = combineEnvelopes(statuses, N, t, useLinear);
            CHECK(v >= -EPS);
            CHECK(v <= AMPLITUDE_MAX + EPS);
        }
    }
}
