# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

# NOTE: Currently not supported as of CircuitPython 9.2.1

import audiobusio
import audiomixer
import synthio
import ulab.numpy as np

import zero_stomp

# Constants
MIN_SPEED = 0.1
MAX_SPEED = 4.0

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
waveform = 0

# Device configuration
device = zero_stomp.ZeroStomp()
device.title = "Tremolo"
device.mix = 1.0

# Audio Objects
# TODO: Support for I2SInOut in CircuitPython core
audio_in = audiobusio.I2SIn(
    bit_clock=zero_stomp.I2S_BCLK,
    word_select=zero_stomp.I2S_LRCLK,
    data=zero_stomp.I2S_DIN,
    channel_count=zero_stomp.CHANNELS,
    sample_rate=zero_stomp.SAMPLE_RATE,
)

audio_mixer = audiomixer.Mixer(
    voice_count=1,
    sample_rate=zero_stomp.SAMPLE_RATE,
    channel_count=zero_stomp.CHANNELS,
)
audio_mixer.voice[0].level = synthio.Math(
    synthio.MathOperation.SCALE_OFFSET,
    synthio.LFO(
        waveform=waveforms[waveform],
        scale=0.5,
        offset=-0.5,
    ),
    synthio.Math(
        synthio.MathOperation.SUM,
        0.0, # Depth
        0.0, # Expression
        0.0 # defaults to 1.0
    )
    1.0 # Level
)

audio_out = audiobusio.I2SOut(
    bit_clock=zero_stomp.I2S_BCLK,
    word_select=zero_stomp.I2S_LRCLK,
    data=zero_stomp.I2S_DOUT,
)

# Audio Chain
audio_mixer.play(audio_in)
audio_out.play(audio_mixer)

# Assign controls
def set_waveform(index: int):
    waveform = index % len(waveforms)
    audio_mixer.voice[0].level.a.waveform = waveforms[waveform]

device.assign_knob("Rate", audio_mixer.voice[0].level.a, "rate", MIN_SPEED, MAX_SPEED)
device.assign_knob("Depth", audio_mixer.voice[0].level.b, "a")
device.add_knob(
    title="Wave",
    value=waveform / (len(waveforms) - 1),
    callback=lambda value: set_waveform(round(value * (len(waveforms) - 1))),
)

# Update Loop
while True:
    device.update()
    audio_mixer.voice[0].level.b.b = device.expression
    device.led = 0 if device.bypassed else audio_mixer.voice[0].level.value
