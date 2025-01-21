# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

# NOTE: Currently not supported as of CircuitPython 9.2.1

import synthio
import ulab.numpy as np

import zero_stomp
zero_stomp.CURRENT = __file__

# Constants
MIN_SPEED = 0.1
MAX_SPEED = 20.0

SAMPLE_SIZE = 1024
SAMPLE_VOLUME = 32767
waveforms = (
    np.concatenate(( # Triangle
        np.linspace(-SAMPLE_VOLUME, SAMPLE_VOLUME, num=SAMPLE_SIZE//2, dtype=np.int16),
        np.linspace(SAMPLE_VOLUME, -SAMPLE_VOLUME, num=SAMPLE_SIZE//2, dtype=np.int16)
    )),
    np.array(np.sin(np.linspace(0, 2 * np.pi, SAMPLE_SIZE, endpoint=False)) * SAMPLE_VOLUME, dtype=np.int16), # Sine
    np.linspace(-SAMPLE_VOLUME, SAMPLE_VOLUME, SAMPLE_SIZE, endpoint=False, dtype=np.int16), # Ramp Up
    np.linspace(-SAMPLE_VOLUME, SAMPLE_VOLUME, SAMPLE_SIZE, endpoint=False, dtype=np.int16), # Ramp Down
    np.concatenate(( # Square
        np.full(SAMPLE_SIZE//2, SAMPLE_VOLUME, dtype=np.int16),
        np.full(SAMPLE_SIZE//2, -SAMPLE_VOLUME, dtype=np.int16)
    )),
)
waveform = -1

# Device configuration
device = zero_stomp.ZeroStomp()
device.title = "Tremolo"
device.mix = 0.0  # Only using analog mixer

# Synth and LFO
synth = synthio.Synthesizer(
    sample_rate=zero_stomp.SAMPLE_RATE,
    channel_count=zero_stomp.CHANNELS,
)

lfo = synthio.Math(
    synthio.MathOperation.SCALE_OFFSET,
    synthio.LFO(
        waveform=np.zeros(SAMPLE_SIZE, dtype=np.int16),
        rate=zero_stomp.map_value(device.knob_value(0), MIN_SPEED, MAX_SPEED),
        scale=0.5,
        offset=-0.5,
    ),
    synthio.Math(
        synthio.MathOperation.SUM,
        device.knob_value(1), # Depth
        0.0, # Expression
        0.0 # defaults to 1.0
    ),
    1.0 # Level
)
synth.blocks.append(lfo)  # Use synth to update LFO

# Audio Chain
device.i2s.play(synth)  # No audio will actually happen

# Assign controls
def set_waveform(index: int):
    global waveform
    if index != waveform:
        waveform = index % len(waveforms)
        # waveform must be updated by element
        for i in range(SAMPLE_SIZE):
            lfo.a.waveform[i] = waveforms[waveform][i]

device.assign_knob("Rate", lfo.a, "rate", MIN_SPEED, MAX_SPEED)
device.assign_knob("Depth", lfo.b, "a")
device.add_knob(
    title="Wave",
    value=device.knob_value(2),
    callback=lambda value: set_waveform(round(value * (len(waveforms) - 1))),
)
device.knobs[2]._do_callback()  # Updates waveform

# Update Loop
while True:
    device.update()
    lfo.b.b = device.expression
    device.level = lfo.value
    device.led = 0 if device.bypassed else lfo.value
