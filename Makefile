# If RACK_DIR is not defined when calling the Makefile, default to two directories above
RACK_DIR ?= ../..

# FLAGS will be passed to both the C and C++ compiler
FLAGS +=
CFLAGS +=
CXXFLAGS +=

# Careful about linking to shared libraries, since you can't assume much about the user's environment and library search path.
# Static libraries are fine, but they should be added to this plugin's build system.
LDFLAGS +=

# Add .cpp files to the build
SOURCES += $(wildcard src/*.cpp)

# Add files to the ZIP package when running `make dist`
# The compiled plugin and "plugin.json" are automatically added.
DISTRIBUTABLES += res
DISTRIBUTABLES += $(wildcard LICENSE*)
DISTRIBUTABLES += $(wildcard presets)

# Include the Rack plugin Makefile framework
include $(RACK_DIR)/plugin.mk

# ---------------------------------------------------------------------------
# C++ unit tests (fes_dsp.hpp, independent of the Rack SDK)
# Run with:  make cpp-test
# ---------------------------------------------------------------------------
CPP_TEST_SRC = src/tests/cpp/test_fes_dsp.cpp
CPP_TEST_BIN = src/tests/cpp/test_fes_dsp

$(CPP_TEST_BIN): $(CPP_TEST_SRC) src/fes_dsp.hpp
	$(CXX) -std=c++17 -Wall -Wextra -I src -o $@ $< -lCatch2Main -lCatch2

cpp-test: $(CPP_TEST_BIN)
	$(CPP_TEST_BIN)

.PHONY: cpp-test
