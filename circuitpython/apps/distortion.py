# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

from audiofilters import Distortion, Filter, DistortionMode
import synthio

import zero_stomp
zero_stomp.CURRENT = __file__

# Constants
MIN_PRE_GAIN = -60
MAX_PRE_GAIN = 60

MIN_POST_GAIN = -80
MAX_POST_GAIN = 24

FILTER = False
MIN_FILTER = 50
MAX_FILTER = 20000

if zero_stomp.is_rp2040():
    MODES = (
        DistortionMode.LOFI,
        DistortionMode.CLIP,
    )
else:
    MODES = (
        DistortionMode.LOFI,
        DistortionMode.CLIP,
        DistortionMode.OVERDRIVE,
        DistortionMode.WAVESHAPE,
    )

# Device configuration
device = zero_stomp.ZeroStomp()
device.title = "Distortion"
device.mix = 1.0

# Audio Objects
distortion_effect = Distortion(
    drive=synthio.Math(
        synthio.MathOperation.SUM,
        0.0, # Knob
        0.0, # Expression
        0.0 # 1.0 by default
    ),
    mix=1.0,
    sample_rate=zero_stomp.SAMPLE_RATE,
    channel_count=zero_stomp.CHANNELS,
    soft_clip=not zero_stomp.is_rp2040(),
)

if FILTER:
    filter_effect = Filter(
        filter=(
            # TODO: Swap with shelf when available
            synthio.Biquad(synthio.FilterMode.HIGH_PASS, MIN_FILTER),
            synthio.Biquad(synthio.FilterMode.LOW_PASS, MAX_FILTER),
        ),
        sample_rate=zero_stomp.SAMPLE_RATE,
        channel_count=zero_stomp.CHANNELS,
    )

# Audio Chain
if FILTER:
    device.audio_out.play(
        filter_effect.play(
            distortion_effect
        )
    )
else:
    device.audio_out.play(
        distortion_effect
    )
distortion_effect.play(
    device.audio_in
)

# Assign controls
# TODO: Simplify with single "Level" knob
device.assign_knob("Pre", distortion_effect, "pre_gain", MIN_PRE_GAIN, MAX_PRE_GAIN)
device.assign_knob("Post", distortion_effect, "post_gain", MIN_POST_GAIN, MAX_POST_GAIN)
device.assign_knob("Drive", distortion_effect.drive, "a")

device.assign_knob("Mix", device, "mix")

if FILTER:
    device.assign_knob("Low", filter_effect.filter[0], "frequency", MAX_FILTER, MIN_FILTER)
    device.assign_knob("High", filter_effect.filter[1], "frequency", MIN_FILTER, MAX_FILTER)

device.add_knob(
    title="Mode",
    value=MODES.index(distortion_effect.mode) / (len(MODES) - 1),
    callback=lambda value: zero_stomp.set_attribute(distortion_effect, "mode", MODES[int(zero_stomp.map_value(value, 0, len(MODES) - 1))]),
)

# Update Loop
while True:
    device.update()
    distortion_effect.drive.b = device.expression
