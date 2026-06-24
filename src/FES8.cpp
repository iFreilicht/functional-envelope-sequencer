#include "plugin.hpp"
#include "fes_dsp.hpp"

#include <cmath>  // std::pow, std::fmod


struct FES8 : Module {
	static constexpr int NUM_ENVELOPES = 8;

	enum ParamId {
		// Global controls
		START_PARAM,
		STOP_PARAM,
		TEMPO_PARAM,
		INTERVAL_PARAM,
		COMBINER_PARAM,
		// Per-envelope controls — grouped consecutively so loop arithmetic works
		ATTACK1_PARAM,
		ATTACK2_PARAM,
		ATTACK3_PARAM,
		ATTACK4_PARAM,
		ATTACK5_PARAM,
		ATTACK6_PARAM,
		ATTACK7_PARAM,
		ATTACK8_PARAM,
		DECAY1_PARAM,
		DECAY2_PARAM,
		DECAY3_PARAM,
		DECAY4_PARAM,
		DECAY5_PARAM,
		DECAY6_PARAM,
		DECAY7_PARAM,
		DECAY8_PARAM,
		SHAPE1_PARAM,
		SHAPE2_PARAM,
		SHAPE3_PARAM,
		SHAPE4_PARAM,
		SHAPE5_PARAM,
		SHAPE6_PARAM,
		SHAPE7_PARAM,
		SHAPE8_PARAM,
		AMPLITUDE1_PARAM,
		AMPLITUDE2_PARAM,
		AMPLITUDE3_PARAM,
		AMPLITUDE4_PARAM,
		AMPLITUDE5_PARAM,
		AMPLITUDE6_PARAM,
		AMPLITUDE7_PARAM,
		AMPLITUDE8_PARAM,
		PARAMS_LEN
	};
	enum InputId {
		INPUTS_LEN
	};
	enum OutputId {
		TIMEOUT_OUTPUT,
		OUT1_OUTPUT,
		OUT2_OUTPUT,
		OUT3_OUTPUT,
		OUT4_OUTPUT,
		OUT5_OUTPUT,
		OUT6_OUTPUT,
		OUT7_OUTPUT,
		OUT8_OUTPUT,
		COMBINEDOUT_OUTPUT,
		OUTPUTS_LEN
	};
	enum LightId {
		PEAK1_LIGHT,
		PEAK2_LIGHT,
		PEAK3_LIGHT,
		PEAK4_LIGHT,
		PEAK5_LIGHT,
		PEAK6_LIGHT,
		PEAK7_LIGHT,
		PEAK8_LIGHT,
		LIGHTS_LEN
	};

	// Runtime state
	float phase = 0.f;    // current position in [0, TIME_END)
	bool running = true; // TODO: make this false again!
	dsp::SchmittTrigger startTrigger;
	dsp::SchmittTrigger stopTrigger;
	dsp::PulseGenerator timeoutPulse;

	FES8() {
		config(PARAMS_LEN, INPUTS_LEN, OUTPUTS_LEN, LIGHTS_LEN);

		// Global controls
		configButton(START_PARAM,   "Start");
		configButton(STOP_PARAM,    "Stop");
		configParam(TEMPO_PARAM,    0.f, 1.f, 0.5f, "Tempo",   " Hz", 8.f, 0.5f);
		configParam(INTERVAL_PARAM, 0.f, 1.f, 0.5f, "Interval (peak spacing)");
		configSwitch(COMBINER_PARAM, 0.f, 1.f, 0.f, "Combiner", {"Max", "Linear"});

		// Per-envelope controls
		const char* chNames[NUM_ENVELOPES] = {"1", "2", "3", "4", "5", "6", "7", "8"};
		for (int i = 0; i < NUM_ENVELOPES; ++i) {
			configParam(ATTACK1_PARAM    + i, 0.f, 1.f, 0.5f,
				rack::string::f("Channel %s attack",    chNames[i]));
			configParam(DECAY1_PARAM     + i, 0.f, 1.f, 0.5f,
				rack::string::f("Channel %s decay",     chNames[i]));
			configParam(SHAPE1_PARAM     + i, 0.f, 1.f, 0.0f,
				rack::string::f("Channel %s shape",     chNames[i]));
			configParam(AMPLITUDE1_PARAM + i, 0.f, 1.f, 1.0f,
				rack::string::f("Channel %s amplitude", chNames[i]));
		}

		// Outputs
		configOutput(TIMEOUT_OUTPUT,    "Timeout (loop-wrap trigger)");
		for (int i = 0; i < NUM_ENVELOPES; ++i) {
			configOutput(OUT1_OUTPUT + i,
				rack::string::f("Envelope %s", chNames[i]));
		}
		configOutput(COMBINEDOUT_OUTPUT, "Combined envelope");
	}

	void process(const ProcessArgs& args) override {
		// --- START / STOP buttons ---
		if (startTrigger.process(params[START_PARAM].getValue())) {
			running = true;
			phase   = 0.f;
		}
		if (stopTrigger.process(params[STOP_PARAM].getValue())) {
			running = false;
		}

		// --- Advance phase ---
		if (running) {
			// Exponential tempo mapping: knob 0→0.5 Hz, 0.5→2 Hz, 1→4 Hz
			// rate = 0.5 * 8^knob  →  [0.5, 4.0] Hz
			const float tempoKnob = params[TEMPO_PARAM].getValue();
			const float rate      = 0.5f * std::pow(8.f, tempoKnob);

			phase += rate * args.sampleTime;
			if (phase >= fes::TIME_END) {
				phase = std::fmod(phase, fes::TIME_END);
				timeoutPulse.trigger(1e-3f);  // 1 ms trigger on loop wrap
			}
		}

		// --- Build per-envelope settings ---
		fes::EnvelopeSettings settings[NUM_ENVELOPES];
		for (int i = 0; i < NUM_ENVELOPES; ++i) {
			// Exponential attack/decay mapping: knob 0 → SLOPE_TIME_MIN, 1 → TIME_MIDPOINT
			const float attackKnob = params[ATTACK1_PARAM + i].getValue();
			const float decayKnob  = params[DECAY1_PARAM  + i].getValue();

			settings[i] = {
				fes::SLOPE_TIME_MIN * std::pow(fes::TIME_MIDPOINT / fes::SLOPE_TIME_MIN, attackKnob),
				fes::SLOPE_TIME_MIN * std::pow(fes::TIME_MIDPOINT / fes::SLOPE_TIME_MIN, decayKnob),
				params[SHAPE1_PARAM     + i].getValue(),
				params[AMPLITUDE1_PARAM + i].getValue()
			};
		}

		// --- Interval ---
		const float intervalKnob = params[INTERVAL_PARAM].getValue();
		const float interval = fes::INTERVAL_MIN
			+ intervalKnob * (fes::INTERVAL_MAX - fes::INTERVAL_MIN);

		// --- Compute envelope status for all channels ---
		fes::EnvelopeStatus statuses[NUM_ENVELOPES];
		fes::offsetEnvelopes(settings, NUM_ENVELOPES, interval, phase, statuses);

		// --- Individual envelope outputs and peak lights ---
		for (int i = 0; i < NUM_ENVELOPES; ++i) {
			// Scale 0–1 → 0–10 V (VCV Rack unipolar CV convention)
			outputs[OUT1_OUTPUT + i].setVoltage(statuses[i].value * 10.f);

			// Peak light: smooth fade, lights up near the envelope peak
			const float brightness = (statuses[i].value >= 0.99f) ? 1.f : 0.f;
			lights[PEAK1_LIGHT + i].setBrightnessSmooth(brightness, args.sampleTime);
		}

		// --- Combined output ---
		const bool useLinear = params[COMBINER_PARAM].getValue() >= 0.5f;
		const float combined = fes::combineEnvelopes(
			statuses, NUM_ENVELOPES, phase, useLinear);
		outputs[COMBINEDOUT_OUTPUT].setVoltage(combined * 10.f);

		// --- Timeout output ---
		outputs[TIMEOUT_OUTPUT].setVoltage(
			timeoutPulse.process(args.sampleTime) ? 10.f : 0.f);
	}
};


struct FES8Widget : ModuleWidget {
	FES8Widget(FES8* module) {
		setModule(module);
		setPanel(createPanel(asset::plugin(pluginInstance, "res/FES8.svg")));

		addChild(createWidget<ScrewSilver>(Vec(RACK_GRID_WIDTH, 0)));
		addChild(createWidget<ScrewSilver>(Vec(box.size.x - 2 * RACK_GRID_WIDTH, 0)));
		addChild(createWidget<ScrewSilver>(Vec(RACK_GRID_WIDTH, RACK_GRID_HEIGHT - RACK_GRID_WIDTH)));
		addChild(createWidget<ScrewSilver>(Vec(box.size.x - 2 * RACK_GRID_WIDTH, RACK_GRID_HEIGHT - RACK_GRID_WIDTH)));

		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(24.459, 25.297)), module, FES8::START_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(56.618, 47.163)), module, FES8::ATTACK1_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(70.74, 47.156)), module, FES8::ATTACK2_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(84.908, 47.191)), module, FES8::ATTACK3_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(99.034, 47.179)), module, FES8::ATTACK4_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(113.202, 47.214)), module, FES8::ATTACK5_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(24.977, 48.167)), module, FES8::STOP_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(127.363, 47.204)), module, FES8::ATTACK6_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(141.489, 47.192)), module, FES8::ATTACK7_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(155.657, 47.227)), module, FES8::ATTACK8_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(9.772, 53.281)), module, FES8::TEMPO_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(56.606, 63.722)), module, FES8::DECAY1_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(70.728, 63.715)), module, FES8::DECAY2_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(84.895, 63.75)), module, FES8::DECAY3_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(99.022, 63.738)), module, FES8::DECAY4_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(113.19, 63.773)), module, FES8::DECAY5_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(127.35, 63.763)), module, FES8::DECAY6_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(141.477, 63.751)), module, FES8::DECAY7_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(155.645, 63.786)), module, FES8::DECAY8_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(56.618, 81.001)), module, FES8::SHAPE1_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(70.739, 80.994)), module, FES8::SHAPE2_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(84.907, 81.029)), module, FES8::SHAPE3_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(99.034, 81.017)), module, FES8::SHAPE4_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(113.201, 81.052)), module, FES8::SHAPE5_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(127.362, 81.042)), module, FES8::SHAPE6_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(141.489, 81.03)), module, FES8::SHAPE7_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(155.656, 81.065)), module, FES8::SHAPE8_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(25.079, 86.013)), module, FES8::INTERVAL_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(56.584, 97.926)), module, FES8::AMPLITUDE1_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(70.706, 97.919)), module, FES8::AMPLITUDE2_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(84.874, 97.954)), module, FES8::AMPLITUDE3_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(99.0, 97.942)), module, FES8::AMPLITUDE4_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(113.168, 97.977)), module, FES8::AMPLITUDE5_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(127.329, 97.967)), module, FES8::AMPLITUDE6_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(141.455, 97.955)), module, FES8::AMPLITUDE7_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(155.623, 97.99)), module, FES8::AMPLITUDE8_PARAM));
		addParam(createParamCentered<RoundBlackKnob>(mm2px(Vec(17.883, 116.031)), module, FES8::COMBINER_PARAM));

		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(189.284, 75.255)), module, FES8::TIMEOUT_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(56.59, 116.567)), module, FES8::OUT1_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(70.819, 116.56)), module, FES8::OUT2_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(85.074, 116.56)), module, FES8::OUT3_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(99.33, 116.56)), module, FES8::OUT4_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(113.585, 116.56)), module, FES8::OUT5_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(127.841, 116.56)), module, FES8::OUT6_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(142.097, 116.56)), module, FES8::OUT7_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(156.352, 116.56)), module, FES8::OUT8_OUTPUT));
		addOutput(createOutputCentered<PJ301MPort>(mm2px(Vec(189.284, 116.284)), module, FES8::COMBINEDOUT_OUTPUT));

		addChild(createLightCentered<MediumLight<RedLight>>(mm2px(Vec(56.34, 108.443)), module, FES8::PEAK1_LIGHT));
		addChild(createLightCentered<MediumLight<RedLight>>(mm2px(Vec(70.635, 108.443)), module, FES8::PEAK2_LIGHT));
		addChild(createLightCentered<MediumLight<RedLight>>(mm2px(Vec(84.93, 108.443)), module, FES8::PEAK3_LIGHT));
		addChild(createLightCentered<MediumLight<RedLight>>(mm2px(Vec(99.224, 108.443)), module, FES8::PEAK4_LIGHT));
		addChild(createLightCentered<MediumLight<RedLight>>(mm2px(Vec(113.519, 108.443)), module, FES8::PEAK5_LIGHT));
		addChild(createLightCentered<MediumLight<RedLight>>(mm2px(Vec(127.814, 108.443)), module, FES8::PEAK6_LIGHT));
		addChild(createLightCentered<MediumLight<RedLight>>(mm2px(Vec(142.108, 108.443)), module, FES8::PEAK7_LIGHT));
		addChild(createLightCentered<MediumLight<RedLight>>(mm2px(Vec(156.403, 108.443)), module, FES8::PEAK8_LIGHT));

		// mm2px(Vec(126.796, 31.699))
		addChild(createWidget<Widget>(mm2px(Vec(41.81, 4.099))));
	}
};


Model* modelFES8 = createModel<FES8, FES8Widget>("FES8");
