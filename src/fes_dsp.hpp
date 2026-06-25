#pragma once
// fes_dsp.hpp — Pure-math core for the Functional Envelope Sequencer.
//
// No VCV Rack SDK headers are included here so this file can be unit-tested
// without linking against libRack.  All public symbols live in namespace fes.
//
// Define FES_ENABLE_ASSERTIONS before including this header (e.g. via
// -DFES_ENABLE_ASSERTIONS on the compiler command line) to enable range-checking
// assertions in clamp_checked.  This is done automatically by the Makefile's
// cpp-test target.

#include <algorithm>  // std::sort, std::max
#include <cassert>    // assert
#include <cmath>      // std::pow, std::fmod

namespace fes {

// ---------------------------------------------------------------------------
// clamp — available in std:: only from C++17, but the Rack SDK build uses
// C++11.  Define our own so the header compiles in both contexts.
// ---------------------------------------------------------------------------
template <typename T>
inline T clamp(T value, T lo, T hi) {
    return value < lo ? lo : (value > hi ? hi : value);
}

// ---------------------------------------------------------------------------
// clamp_checked — like clamp, but asserts that the input is within
// [lo - tolerance, hi + tolerance] when FES_ENABLE_ASSERTIONS is defined.
// Use this instead of clamp wherever an out-of-range input indicates a
// programming error (i.e. the caller is responsible for passing valid values).
// Use plain clamp for internal floating-point overshoot guards.
// ---------------------------------------------------------------------------
template <typename T>
inline T clamp_checked(T value, T lo, T hi) {
#ifdef FES_ENABLE_ASSERTIONS
    constexpr T tolerance = T(1e-6);
    assert(value >= lo - tolerance && value <= hi + tolerance);
#endif
    return clamp(value, lo, hi);
}

// ---------------------------------------------------------------------------
// Constants (mirror Python envelope.py)
// ---------------------------------------------------------------------------

constexpr float TIME_START            = 0.0f;
constexpr float TIME_END              = 2.0f;
constexpr float TIME_MIDPOINT         = (TIME_START + TIME_END) / 2.0f;  // 1.0
constexpr float SLOPE_TIME_MIN        = 0.001f;
constexpr float INTERVAL_MIN          = 0.05f;
constexpr float INTERVAL_MAX          = 0.5f;
constexpr float AMPLITUDE_MIN         = 0.0f;
constexpr float AMPLITUDE_MAX         = 1.0f;
constexpr float AMPLITUDE_LOWER_CUTOFF = 0.01f;
constexpr float SHAPE_MIN             = 0.0f;
constexpr float SHAPE_MAX             = 1.0f;

// ---------------------------------------------------------------------------
// adShape — attack/decay curve shaper
//
// Maps a normalized progress value x ∈ [0,1] through a shape curve
// parameterised by s ∈ [0,1]:
//
//   f(s, x) = (1−s)·x^(1+s)  +  s·x^(10^s)
//
// Boundary guarantees (independent of s):
//   f(s, 0) = 0,   f(s, 1) = 1
//
// Extremes:
//   s = 0 → linear (f = x)
//   s = 1 → degree-10 polynomial (f = x^10)
// ---------------------------------------------------------------------------
inline float adShape(float shape, float progress) {
    shape    = clamp_checked(shape,    SHAPE_MIN, SHAPE_MAX);
    progress = clamp_checked(progress, 0.0f,      1.0f);

    const float s = shape;
    const float x = progress;

    // Linear branch dominates when s → 0
    const float lin  = std::pow(x, 1.0f + s);
    // Exponential branch dominates when s → 1 (exponent = 10^s)
    const float quad = std::pow(x, std::pow(10.0f, s));

    return (1.0f - s) * lin + s * quad;
}

// ---------------------------------------------------------------------------
// EnvelopeSettings — per-channel parameters
// ---------------------------------------------------------------------------
struct EnvelopeSettings {
    float attack;     // seconds; expected in [SLOPE_TIME_MIN, TIME_MIDPOINT]
    float decay;      // seconds; expected in [SLOPE_TIME_MIN, TIME_MIDPOINT]
    float shape;      // expected in [SHAPE_MIN, SHAPE_MAX]
    float amplitude;  // expected in [AMPLITUDE_MIN, AMPLITUDE_MAX]

    bool isEnabled() const { return amplitude > AMPLITUDE_LOWER_CUTOFF; }
};

// ---------------------------------------------------------------------------
// adEnvelope — single A/D envelope fixed on [TIME_START, TIME_END]
//
// The peak is always at TIME_MIDPOINT regardless of attack/decay values.
// Returns amplitude·adShape(progress) during attack and decay windows,
// and 0 outside them.  Returns 0 immediately for disabled envelopes.
// ---------------------------------------------------------------------------
inline float adEnvelope(const EnvelopeSettings& s, float time) {
#ifdef FES_ENABLE_ASSERTIONS
    assert(TIME_START <= time && time <= TIME_END);
#endif

    if (!s.isEnabled()) return 0.0f;

    const float attack    = clamp_checked(s.attack,    SLOPE_TIME_MIN, TIME_MIDPOINT);
    const float decay     = clamp_checked(s.decay,     SLOPE_TIME_MIN, TIME_MIDPOINT);
    const float shape     = clamp_checked(s.shape,     SHAPE_MIN,      SHAPE_MAX);
    const float amplitude = clamp_checked(s.amplitude, AMPLITUDE_MIN,  AMPLITUDE_MAX);

    float value;
    if (time <= TIME_MIDPOINT) {
        // Attack phase
        const float start = TIME_MIDPOINT - attack;
        if (time < start) return 0.0f;
        const float progress = (time - start) / attack;
        value = adShape(shape, progress);
    } else {
        // Decay phase
        const float end = TIME_MIDPOINT + decay;
        if (time > end) return 0.0f;
        const float progress = (end - time) / decay;
        value = adShape(shape, progress);
    }

    return value * amplitude;
}

// ---------------------------------------------------------------------------
// EnvelopeStatus — computed snapshot for one envelope at one point in time
// ---------------------------------------------------------------------------
struct EnvelopeStatus {
    float time;      // the local time used for this envelope (wraps at TIME_END)
    float midpoint;  // the global time at which this envelope's peak occurs
    float value;     // adEnvelope output
    bool  enabled;   // mirrors EnvelopeSettings::isEnabled()
};

// ---------------------------------------------------------------------------
// offsetEnvelopes — compute status for N evenly-spaced envelopes
//
// Envelope i has its peak offset by interval*i seconds.
// `out` must point to storage for at least `n` EnvelopeStatus values.
// ---------------------------------------------------------------------------
inline void offsetEnvelopes(
        const EnvelopeSettings* settings,
        int                     n,
        float                   interval,
        float                   time,
        EnvelopeStatus*         out) {

    interval = clamp_checked(interval, INTERVAL_MIN, INTERVAL_MAX);

    for (int i = 0; i < n; ++i) {
        const float offset    = interval * static_cast<float>(i);
        const float envTime   = std::fmod(time - offset + 4.0f * TIME_END, TIME_END);
        const float midpoint  = std::fmod(offset + TIME_MIDPOINT,          TIME_END);

        out[i] = EnvelopeStatus{
            envTime,
            midpoint,
            adEnvelope(settings[i], envTime),
            settings[i].isEnabled()
        };
    }
}

// ---------------------------------------------------------------------------
// Combiner helpers
// ---------------------------------------------------------------------------

inline float combineMax(const EnvelopeStatus& left, const EnvelopeStatus& right, float /*time*/) {
    return std::max(left.value, right.value);
}

inline float combineLinear(const EnvelopeStatus& left, const EnvelopeStatus& right, float time) {
    // Distance between the two peaks (wrapping)
    const float peakDistance = std::fmod(
        right.midpoint - left.midpoint + TIME_END, TIME_END);

    if (peakDistance == 0.0f) {
        // Should not happen (interval > 0), but guard against divide-by-zero
        return left.value;
    }

    const float progressAbsolute = std::fmod(
        time - left.midpoint + TIME_END, TIME_END);

    // Clamp to guard against floating-point overshoot — not a user-error site,
    // so plain clamp (not clamp_checked) is appropriate here.
    const float progress = clamp(progressAbsolute / peakDistance, 0.0f, 1.0f);

    return (1.0f - progress) * left.value + progress * right.value;
}

// ---------------------------------------------------------------------------
// combineEnvelopes — find the bracketing pair and combine them
//
// statuses must have at least `n` entries.
// useLinear selects between combineLinear (true) and combineMax (false).
// ---------------------------------------------------------------------------
inline float combineEnvelopes(
        const EnvelopeStatus* statuses,
        int                   n,
        float                 time,
        bool                  useLinear) {

    time = std::fmod(time + 2.0f * TIME_END, TIME_END);

    // Collect enabled envelopes (use a small fixed-size scratch array;
    // the max channel count for FES modules is bounded at compile time)
    constexpr int MAX_N = 64;
    const EnvelopeStatus* active[MAX_N];
    int activeCount = 0;

    for (int i = 0; i < n && activeCount < MAX_N; ++i) {
        if (statuses[i].enabled) {
            active[activeCount++] = &statuses[i];
        }
    }

    if (activeCount == 0) return 0.0f;
    if (activeCount == 1) return active[0]->value;

    // Sort by midpoint
    std::sort(active, active + activeCount,
              [](const EnvelopeStatus* a, const EnvelopeStatus* b) {
                  return a->midpoint < b->midpoint;
              });

    // Find the pair whose midpoints bracket `time`
    for (int i = 0; i < activeCount - 1; ++i) {
        if (active[i]->midpoint <= time && time <= active[i + 1]->midpoint) {
            return useLinear
                ? combineLinear(*active[i], *active[i + 1], time)
                : combineMax(*active[i], *active[i + 1], time);
        }
    }

    // time is outside all midpoints → wrap: combine last and first
    return useLinear
        ? combineLinear(*active[activeCount - 1], *active[0], time)
        : combineMax(*active[activeCount - 1], *active[0], time);
}

}  // namespace fes
