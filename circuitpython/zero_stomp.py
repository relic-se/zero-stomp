# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import analogio
import board
import busio
import digitalio
import displayio
import math
import pwmio
import terminalio
import usb_midi
import vectorio

import adafruit_debouncer
import adafruit_displayio_ssd1306
import adafruit_display_text.label
import adafruit_midi
import adafruit_simplemath
import adafruit_wm8960.advanced
import neopixel

displayio.release_displays()

# Pin Configuration

UART_TX = board.GP0
UART_RX = board.GP1

I2S_BCLK = board.GP2
I2S_LRCLK = board.GP3
I2S_DAC = board.GP4
I2S_ADC = board.GP5

I2C_SDA = board.GP6
I2C_SCL = board.GP7

STOMP_LED = board.GP8
STOMP_SWITCH = board.GP9

DISPLAY_RESET = board.GP10
DISPLAY_DC = board.GP11
DISPLAY_CS = board.GP13
DISPLAY_SCK = board.GP14
DISPLAY_TX = board.GP15

ADC_0 = board.GP26
ADC_1 = board.GP27
ADC_2 = board.GP28
ADC_EXPR = board.GP29
ADC_PINS = (ADC_0, ADC_1, ADC_2, ADC_EXPR)
NUM_POTS = 3

# Constants

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

SAMPLE_RATE = 48000

# Displayio Controls

palette_white = displayio.Palette(1)
palette_white[0] = 0xFFFFFF

palette_black = displayio.Palette(1)
palette_black[0] = 0x000000

class WheelControl(displayio.Group):

    def __init__(self, x:int, y:int, radius:int=16, knob_radius:int=4):
        super().__init__(x=x, y=y)
        self._radius = radius
        self._knob_radius = knob_radius

        # Outer circle
        self.append(vectorio.Circle(
            pixel_shader=palette_white,
            radius=radius,
            x=0,
            y=0,
        ))
        self.append(vectorio.Circle(
            pixel_shader=palette_black,
            radius=radius-1,
            x=0,
            y=0,
        ))

        # Knob
        self._knob = displayio.Group()
        self._knob.append(vectorio.Circle(
            pixel_shader=palette_white,
            radius=knob_radius,
            x=0,
            y=0,
        ))
        self._knob.append(vectorio.Circle(
            pixel_shader=palette_black,
            radius=knob_radius-1,
            x=0,
            y=0,
        ))
        self.append(self._knob)
        self.position = 0.5

        # Text
        self._label = adafruit_display_text.label.Label(
            font=terminalio.FONT,
            text="",
            color=0xFFFFFF,
            anchor_point=(0.5, 0.5),
            anchored_position=(0, radius + 4)
        )
        self.append(self._label)

    @property
    def position(self) -> float:
        return self._position
    
    @position.setter
    def position(self, value:float) -> None:
        self._position = value
        self._knob.x = int((self._radius - self._knob_radius) * math.sin(value * math.pi * 2))
        self._knob.y = int((self._radius - self._knob_radius) * math.cos(value * math.pi * 2))

    @property
    def label(self) -> str:
        return self._label.text
    
    @label.setter
    def label(self, value:str) -> None:
        self._label.text = value

class ZeroStomp(displayio.Group):

    def __init__(self):
        super().__init__()

        # NeoPixel
        self.pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
        self.pixel.fill((0, 0, 255))

        # Displayio
        self._display_bus = displayio.FourWire(
            busio.SPI(
                clock=DISPLAY_SCK,
                MOSI=DISPLAY_TX,
            ),
            command=DISPLAY_DC,
            chip_select=DISPLAY_CS,
            reset=DISPLAY_RESET,
        )
        self._display = adafruit_displayio_ssd1306.SSD1306(
            self._display_bus,
            width=DISPLAY_WIDTH,
            height=DISPLAY_HEIGHT,
        )
        self._display.root_group = self

        # Title Text
        self._title = adafruit_display_text.label.Label(
            font=terminalio.FONT,
            text="Zero Stomp",
            color=0xFFFFFF,
            anchor_point=(0.5, 0.5),
            anchored_position=(DISPLAY_WIDTH//2, DISPLAY_HEIGHT//4)
        )
        self.append(self._title)

        # Wheel controls
        self.wheels = displayio.Group()
        self.append(self.wheels)
        for i in range(NUM_POTS):
            self.wheels.append(WheelControl(DISPLAY_WIDTH // (NUM_POTS + 1) * (i + 1), DISPLAY_HEIGHT//2))
        self.wheels.hidden = True

        self.pixel.fill((0, 255, 0))

        # ADC Controls
        self._adc_pins = tuple([analogio.AnalogIn(pin) for pin in ADC_PINS])

        # MIDI
        self._midi_uart_bus = busio.UART(
            UART_TX,
            UART_RX,
            baudrate=31250,
            timeout=0.001,
        )
        self._midi_uart = adafruit_midi.MIDI(
            midi_in=self._midi_uart_bus,
            midi_out=self._midi_uart_bus,
        )
        self._midi_usb = adafruit_midi.MIDI(
            midi_in=usb_midi.ports[0],
            midi_out=usb_midi.ports[1],
        )

        # Audio Codec
        self._codec = adafruit_wm8960.advanced.WM8960_Advanced(busio.I2C(I2C_SCL, I2C_SDA))

        ## Digital Interface
        self._codec.sample_rate = SAMPLE_RATE
        self._codec.bit_depth = 16
        self._codec.adc = True
        self._codec.dac = True

        ## Enable single-ended mic (INPUT1) input and pass through mic and boost amplifier
        self._codec.mic = True
        self._codec.mic_inverting_input = True
        self._codec.mic_input = adafruit_wm8960.advanced.Mic_Input.VMID
        self._codec.mic_mute = False
        self._codec.mic_zero_cross = True
        self._codec.mic_volume = 0.0
        self._codec.mic_boost_gain = 0.0
        self._codec.mic_boost = True
        self._codec.input = True

        ## Bypass ADC/DAC and connect mic boost to output mixer
        self._codec.mic_output = True

        ## Turn on the output mixer and headphone output
        self._codec.output = True
        self._codec.headphone = True
        self._codec.mono_output = False
        self._codec.headphone_zero_cross = True
        self._codec.headphone_volume = 0.0

        self.mix = 0.0

        # TODO: I2S, PIO or native?

        # Stomp Switch
        self._stomp_led = pwmio.PWMOut(STOMP_LED)
        self._stomp_switch_pin = digitalio.DigitalInOut(STOMP_SWITCH)
        self._stomp_switch_pin.direction = digitalio.Direction.INPUT
        self._stomp_switch_pin.pull = digitalio.Pull.UP
        self._stomp_switch = adafruit_debouncer.Debouncer(self._stomp_switch_pin)

        self.pixel.fill((255, 0, 0))

    @property
    def title(self) -> str:
        return self._title.text
    
    @title.setter
    def title(self, value:str) -> None:
        self._title.text = value

    @property
    def values(self) -> tuple[float]:
        values = tuple([pin.value / 65535 for pin in self._adc_pins])
        for i in range(NUM_POTS):
            self.wheels[i].position = values[i]
        return values
    
    @property
    def is_bypassed(self) -> bool:
        return self._stomp_switch.value
    
    @property
    def mix(self) -> float:
        return self._mix
    
    @mix.setter
    def mix(self, value:float) -> None:
        self._mix = value
        self._update_mix()
    
    def _update_mix(self) -> None:
        self._codec.dac_mute = self.is_bypassed
        self._codec.mic_output_volume = 0.0 if self.is_bypassed else adafruit_simplemath.map_range(self._mix, adafruit_wm8960.advanced.OUTPUT_VOLUME_MIN, 0.0)
        self._codec.dac_volume = adafruit_simplemath.map_range(self._mix, adafruit_wm8960.advanced.DAC_VOLUME_MIN, 0.0)
        if not self.is_bypassed and self._mix >= 1.0:
            self._codec.mic_output = False
        else:
            self._codec.mic_output = True

    def update(self) -> None:
        self._stomp_switch.update()
        self._stomp_led.duty_cycle = 0 if self.is_bypassed else 2 ** 16
        if self._stomp_switch.rose or self._stomp_switch.fell:
            self._update_mix()
