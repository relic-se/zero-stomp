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
MIN_Q = 0.7071067811865475
MAX_Q = 2.0

MIN_FILTER = 50
MAX_FILTER = 10000

MIN_SPEED = 0.1
MAX_SPEED = 4.0

# Device configuration
device = zero_stomp.ZeroStomp()
device.title = "Wah"
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

audio_filter = audiofilters.Filter(
    filter=synthio.BlockBiquad(
        synthio.FilterMode.BAND_PASS,
        synthio.Math(
            synthio.MathOperation.SCALE_OFFSET,
            synthio.LFO(scale=0.0), # auto-wah
            (MAX_FILTER - MIN_FILTER) / 2, # max auto-wah depth
            synthio.Math(
                synthio.MathOperation.SUM,
                MIN_FILTER, # knob
                0, # expression
                0 # defaults to 1.0
            )
        ),
        MIN_Q,
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
audio_filter.play(audio_in)
audio_out.play(audio_filter)

# Setup controls
device.assign_knob("Filter", audio_filter.filter.frequency.c, "a", MIN_FILTER, MAX_FILTER)
device.assign_knob("Q", audio_filter.filter, "Q", MIN_Q, MAX_Q)
device.assign_knob("Mix", device, "mix")

device.assign_knob("Speed", audio_filter.filter.frequency.a, "rate", MIN_SPEED, MAX_SPEED)
device.assign_knob("Depth", audio_filter.filter.frequency.a, "scale")

# Update Loop
while True:
    device.update()
    audio_filter.filter.frequency.c.b = device.expression
    device.led = 0 if device.bypassed else (audio_filter.filter.frequency.a.value + 1) / 4 + 0.5
