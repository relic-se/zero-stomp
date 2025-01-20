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
TAPE_LENGTH = 100
FILTER = False

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
delay_ms = synthio.Math(
    synthio.MathOperation.SCALE_OFFSET,
    0.0, # Expression Amount
    MAX_EXPRESSION,
    250 # Delay Value
)
delay = audiodelays.Echo(
    max_delay_ms=TAPE_LENGTH,
    delay_ms=100,
    mix=1.0,
    sample_rate=zero_stomp.SAMPLE_RATE,
    channel_count=zero_stomp.CHANNELS,
)

# Assign controls
device.assign_knob("Mix", device, "mix")
device.assign_knob("Regen", delay, "decay")
device.assign_knob("Delay", delay_ms, "c", MIN_DELAY, MAX_DELAY)

device.assign_knob("Speed", delay.delay_ms.a, "rate", MIN_SPEED, MAX_SPEED)
device.assign_knob("Width", delay.delay_ms.a, "scale")

if FILTER:
    filter = audiofilters.Filter(
        filter=synthio.BlockBiquad(synthio.FilterMode.LOW_PASS, MAX_FILTER),
        sample_rate=zero_stomp.SAMPLE_RATE,
        channel_count=zero_stomp.CHANNELS,
    )

    device.assign_knob("Filter", filter.filter, "frequency", MIN_FILTER, MAX_FILTER)

    # Audio Chain
    delay.play(device.i2s)
    filter.play(delay)
    device.i2s.play(filter)

else:
    # Audio Chain
    delay.play(device.i2s)
    device.i2s.play(delay)

# Update Loop
while True:
    device.update()
    delay_ms.a = device.expression
    device.led = 0 if device.bypassed else (delay.delay_ms.a.value + 1) / 4 + 0.5
