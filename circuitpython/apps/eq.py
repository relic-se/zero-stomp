# SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

from audiofilters import Filter
import synthio

import zero_stomp
zero_stomp.CURRENT = __file__

# Constants
BANDS = (100, 200, 400, 800, 1600, 3200)  # 6 band
#BANDS = (31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)  # 10 band

Q = 0.7071067811865475

MIN_A = -12.0
MAX_A = 12.0

# Device configuration
device = zero_stomp.ZeroStomp()
device.title = "Graphic EQ"
device.mix = 1.0

# Audio Objects
filter_effect = Filter(
    mix=1.0,

    buffer_size=zero_stomp.BUFFER_SIZE,
    sample_rate=zero_stomp.SAMPLE_RATE,
    bits_per_sample=zero_stomp.BITS_PER_SAMPLE,
    samples_signed=zero_stomp.SAMPLES_SIGNED,
    channel_count=zero_stomp.CHANNELS,
)

# Setup controls
device.assign_knob("Level", device, "level")

bands = []
for i, frequency in enumerate(BANDS):
    bands.append(synthio.Biquad(
        mode=synthio.FilterMode.PEAKING_EQ,  # NOTE: Filter Mode
        frequency=frequency,
        Q=Q,
        A=0.0,
    ))
    device.assign_knob("{:d}hz".format(frequency), bands[i], "A", MIN_A, MAX_A)
bands = tuple(bands)
filter_effect.filter = bands

# Audio Chain
device.audio_out.play(
    filter_effect.play(
        device.audio_in
    )
)

# Update Loop
while True:
    device.update()
