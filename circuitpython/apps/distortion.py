# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

# NOTE: Currently not supported as of CircuitPython 9.2.1

import audiobusio
import audiofilters
import synthio

import zero_stomp
zero_stomp.CURRENT = __file__

# Constants
MIN_PRE_GAIN = -60
MAX_PRE_GAIN = 60

MIN_POST_GAIN = -80
MAX_POST_GAIN = 24

MIN_FILTER = 50
MAX_FILTER = 20000

NUM_MODES = 4

# Device configuration
device = zero_stomp.ZeroStomp()
device.title = "Distortion"
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

audio_distortion = audiofilters.Distortion(
    drive=synthio.Math(
        synthio.MathOperation.SUM,
        0.0, # Knob
        0.0, # Expression
        0.0 # 1.0 by default
    ),
    mix=1.0,
    sample_rate=zero_stomp.SAMPLE_RATE,
    channel_count=zero_stomp.CHANNELS,
)

audio_filter = audiofilters.Filter(
    filter=(
        # TODO: Swap with shelf when available
        synthio.BlockBiquad(synthio.FilterMode.HIGH_PASS, MIN_FILTER),
        synthio.BlockBiquad(synthio.FilterMode.LOW_PASS, MAX_FILTER),
    ),
    sample_rate=zero_stomp.SAMPLE_RATE,
    channel_count=zero_stomp.CHANNELS,
)

audio_out = audiobusio.I2SOut(
    bit_clock=zero_stomp.I2S_BCLK,
    word_select=zero_stomp.I2S_LRCLK,
    data=zero_stomp.I2S_DOUT,
)

# Audio Chain
audio_distortion.play(audio_in)
audio_filter.play(audio_distortion)
audio_out.play(audio_filter)

# Assign controls
# TODO: Simplify with single "Level" knob
device.assign_knob("Pre", audio_distortion, "pre_gain", MIN_PRE_GAIN, MAX_PRE_GAIN)
device.assign_knob("Post", audio_distortion, "post_gain", MIN_POST_GAIN, MAX_POST_GAIN)
device.assign_knob("Drive", audio_distortion.drive, "a")

device.assign_knob("Mix", device, "mix")
device.assign_knob("Low", audio_filter.filter[0], "frequency", MAX_FILTER, MIN_FILTER)
device.assign_knob("High", audio_filter.filter[1], "frequency", MIN_FILTER, MAX_FILTER)

device.add_knob(
    title="Mode",
    value=audio_distortion.mode / (NUM_MODES - 1),
    callback=lambda value: zero_stomp.set_attribute(audio_distortion, "mode", int(zero_stomp.map_value(value, 0, NUM_MODES - 1))),
)

# Update Loop
while True:
    device.update()
    audio_distortion.drive.b = device.expression
