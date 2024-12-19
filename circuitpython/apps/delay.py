# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

# NOTE: Currently not supported as of CircuitPython 9.2.1

import audiobusio
import audiodelays
import audiofilters
import synthio

import zero_stomp

# Constants
MIN_DELAY = 10
MAX_DELAY = 1000
MAX_EXPRESSION = 500

MIN_SPEED = 0.1
MAX_SPEED = 4.0

MIN_FILTER = 100
MAX_FILTER = 20000

# Device configuration
device = zero_stomp.ZeroStomp()
device.title = "Delay"
device.mix = 0.5

# Audio Objects
# TODO: Support for I2SInOut in CircuitPython core
audio_in = audiobusio.I2SIn(
    bit_clock=zero_stomp.I2S_BCLK,
    word_select=zero_stomp.I2S_LRCLK,
    data=zero_stomp.I2S_DIN,
    channel_count=zero_stomp.CHANNELS,
    sample_rate=zero_stomp.SAMPLE_RATE,
)

delay_ms = synthio.Math(
    synthio.MathOperation.SCALE_OFFSET,
    0.0, # Expression Amount
    MAX_EXPRESSION,
    250 # Delay Value
)
audio_delay = audiodelays.Echo(
    delay_ms=synthio.Math(
        synthio.MathOperation.SCALE_OFFSET,
        synthio.LFO(scale=0.0),
        delay_ms,
        delay_ms
    ),
    mix=1.0,
    sample_rate=zero_stomp.SAMPLE_RATE,
    channel_count=zero_stomp.CHANNELS,
)

audio_filter = audiofilters.Filter(
    filter=synthio.BlockBiquad(synthio.FilterMode.LOW_PASS, MAX_FILTER),
    sample_rate=zero_stomp.SAMPLE_RATE,
    channel_count=zero_stomp.CHANNELS,
)

audio_out = audiobusio.I2SOut(
    bit_clock=zero_stomp.I2S_BCLK,
    word_select=zero_stomp.I2S_LRCLK,
    data=zero_stomp.I2S_DOUT,
)

# Audio Chain
audio_delay.play(audio_in)
audio_filter.play(audio_delay)
audio_out.play(audio_filter)

# Setup controls
device.add_knob(
    title="Mix",
    value=device.mix,
    callback=lambda value: zero_stomp.set_attribute(device, "mix", value),
)
device.add_knob(
    title="Regen",
    value=audio_delay.decay,
    callback=lambda value: zero_stomp.set_attribute(audio_delay, "decay", value),
)
device.add_knob(
    title="Delay",
    value=zero_stomp.unmap_value(delay_ms.c, MIN_DELAY. MAX_DELAY),
    callback=lambda value: zero_stomp.set_attribute(delay_ms, "c", zero_stomp.map_value(value, MIN_DELAY, MAX_DELAY)),
)
device.add_knob(
    title="Speed",
    value=zero_stomp.unmap_value(audio_delay.delay_ms.a.rate, MIN_SPEED, MAX_SPEED),
    callback=lambda value: zero_stomp.set_attribute(audio_delay.delay_ms.a, "rate", zero_stomp.map_value(value, MIN_SPEED, MAX_SPEED))
)
device.add_knob(
    title="Width",
    value=audio_delay.delay_ms.a.scale,
    callback=lambda value: zero_stomp.set_attribute(audio_delay.delay_ms.a, "scale", value)
)
device.add_knob(
    title="Filter",
    value=zero_stomp.unmap_value(audio_filter.filter.frequency, MIN_FILTER, MAX_FILTER),
    callback=lambda value: zero_stomp.set_attribute(audio_filter.filter, "frequency", zero_stomp.map_value(value, MIN_FILTER, MAX_FILTER))
)

# Update Loop
while True:
    device.update()
    delay_ms.a = device.expression
    device.led = 0 if device.bypassed else (audio_delay.delay_ms.a.value + 1) / 4 + 0.5
