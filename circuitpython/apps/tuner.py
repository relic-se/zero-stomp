# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import array
import displayio
import math
import terminalio
import ulab.numpy as np
import ulab.utils
import vectorio

import adafruit_display_text.label

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
    height=zero_stomp.DISPLAY_HEIGHT//4,
    x=zero_stomp.DISPLAY_WIDTH//2,
    y=zero_stomp.DISPLAY_HEIGHT*3//8,
)
controls.append(cents_rect)

controls.hidden = True

# Create buffer for recording data
samples = 1024 if zero_stomp.is_rp2040() else 4096
buffer = array.array('h', [0] * samples * 2)

# Determine the minimum and maximum possible frequencies
min_freq = zero_stomp.SAMPLE_RATE / samples  # 2 bytes per sample and only using 1 channel
max_freq = zero_stomp.SAMPLE_RATE / 2  # nyquist

# Linear distribution of indexes used to calculate weighted mean
dist = np.arange(samples // 2, dtype=np.int16)

while True:
    device.update()
    
    # Grab a single buffer from the codec and convert it to an np.ndarray object
    device.i2s.record(buffer, len(buffer))
    data = np.array(buffer, dtype=np.int16)[0::2] # Only use left channel
    
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
