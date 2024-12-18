# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import displayio
import math
import terminalio
import ulab.numpy as np
import ulab.utils
import vectorio

import adafruit_display_text.label
import pio_i2s

import zero_stomp

LEVEL_ATTACK = 0.01  # begins calculation when relative level is above this value
LEVEL_RELEASE = 0.002  # ends calculation when relative level is below this value
FREQ_CUTOFF = 0.25  # only measure frequencies above this relative threshold
FREQ_OFFSET = -11.5  # offset measured during calibration with A4 (440hz)

LOG2_A4 = math.log(440, 2)
NOTES = ["A", "A#/Bb", "B", "C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab"]

device = zero_stomp.ZeroStomp()
device.title = "Tuner"
device.mix = 1.0

controls = displayio.Group()
device.append(controls)

# Note name label
note_text = adafruit_display_text.label.Label(
    font=terminalio.FONT,
    text="",
    color=0xFFFFFF,
    anchor_point=(0.5, 0.5),
    anchored_position=(zero_stomp.DISPLAY_WIDTH // 2, zero_stomp.DISPLAY_HEIGHT // 4 * 3),
)
controls.append(note_text)

# Tuning bar graph
cents_rect = vectorio.Rectangle(
    pixel_shader=zero_stomp.palette_white,
    width=1,
    height=zero_stomp.DISPLAY_HEIGHT//2,
    x=zero_stomp.DISPLAY_WIDTH//2,
    y=zero_stomp.DISPLAY_HEIGHT//4,
)
controls.append(cents_rect)

controls.hidden = True

# Begin I2S bus interface with codec
i2s = pio_i2s.I2S(
    bit_clock=zero_stomp.I2S_BCLK,
    data_out=zero_stomp.I2S_DAC,
    data_in=zero_stomp.I2S_ADC,
    channel_count=1,
    sample_rate=zero_stomp.SAMPLE_RATE,
    bits_per_sample=16,  # ulab.numpy only works with integers up to 16-bits
    samples_signed=True,
    buffer_size=4096,  # increase this value to improve the resolution of the spectrogram
)

# Determine the minimum and maximum possible frequencies
min_freq = i2s.sample_rate / i2s.buffer_size
max_freq = i2s.sample_rate / 2  # nyquist

# Linear distribution of indexes used to calculate weighted mean
dist = np.arange(i2s.buffer_size // 2, dtype=np.int16)

while True:
    device.update()
    
    # Grab a single buffer from the codec and convert it to an np.ndarray object
    data = np.array(i2s.read(block=True), dtype=np.int16)
    
    # Calculate maximum level
    mean = np.mean(data)
    level = min(max((np.max(data) - mean) / 32768, 0.0), 1.0)
    
    # Decide whether or not to perform calculations using basic noise gate
    # Use the display hidden state as the toggle for the gate
    if controls.hidden and level > LEVEL_ATTACK:
        controls.hidden = False
    elif not controls.hidden and level < LEVEL_RELEASE:
        controls.hidden = True
        
    if controls.hidden:
        continue
    
    # Perform Fourier Fast Transform (FFT) algorithm on audio signal
    data = ulab.utils.spectrogram(data)
    
    # Remove upper half of spectrogram
    data = data[:len(data)//2]
    
    # Replace elements below upper threshold with 0
    threshold = (np.max(data) - np.min(data)) * FREQ_CUTOFF + np.min(data)
    data = np.where(data > threshold, data, 0.0)
    
    # Only keep largest area of values
    areas = []
    area = None
    for i in range(len(data)):
        if data[i] > 0.0:
            if area is None:
                area = [i, i, 0]
            area[1] += 1
            area[2] += data[i]
        elif area is not None:
            areas.append(area)
            area = None
    if area is not None:
        areas.append(area)
    
    # Sort areas by size
    areas = sorted(areas, key=lambda x: x[1])
    
    # Clear all areas besides the largest
    for i in range(1, len(areas)):
        for j in range(areas[i][0], areas[i][1]):
            data[j] = 0.0
    
    # Get the center index using weighted mean
    index = np.sum(data * dist) / np.sum(data)
    
    # Calculate frequency from index
    frequency = (max_freq - min_freq) * (index / (len(data) - 1)) + min_freq + FREQ_OFFSET
    
    # Determine MIDI note value and note name
    notenum = round(12 * (math.log(frequency, 2) - LOG2_A4) + 69)
    notename = "{:s}{:d}".format(NOTES[(notenum - 21) % 12], (notenum - 12) // 12)
    
    # Determine desired frequency
    target_frequency = math.pow(2, (notenum - 69) / 12) * 440
    
    # Calculate cents
    cents = 1200 * math.log(frequency / target_frequency)
    
    # Update display
    note_text.text = notename
    cents_rect.width = int(min(max(abs(cents) / 25 * zero_stomp.DISPLAY_WIDTH / 2, 1), zero_stomp.DISPLAY_WIDTH // 2))
    if cents >= 0:
        cents_rect.x = zero_stomp.DISPLAY_WIDTH // 2
    else:
        cents_rect.x = zero_stomp.DISPLAY_WIDTH // 2 - cents_rect.width
