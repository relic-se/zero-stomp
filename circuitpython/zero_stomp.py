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
import adafruit_wm8960.advanced
import neopixel

try:
    from typing import Callable
except ImportError:
    pass

displayio.release_displays()

# Pin Configuration

UART_TX = board.GP0
UART_RX = board.GP1

I2S_BCLK = board.GP2
I2S_LRCLK = board.GP3
I2S_DOUT = board.GP4
I2S_DIN = board.GP5

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
NUM_POTS = 3

# Constants

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

SAMPLE_RATE = 48000
CHANNELS = 2

SWITCH_SHORT_DURATION = 0.4

# Helper Methods

def set_attribute(items:list|tuple|object, name:str, value:any, offset:float = 0.0) -> None:
    if type(items) is not list and type(items) is not tuple:
        items = [items]
    for i, item in enumerate(items):
        if hasattr(item, name):
            if type(value) is float and offset > 0.0:
                setattr(item, name, value + offset * (i - (len(items) - 1) / 2))
            else:
                setattr(item, name, value)

def map_value(value: float, min_value: float, max_value: float) -> float:
    return min(max(value, 0.0), 1.0) * (max_value - min_value) + min_value

def unmap_value(value: float, min_value: float, max_value: float) -> float:
    return min(max((value - min_value) / (max_value - min_value), 0.0), 1.0)

# Displayio Controls

palette_white = displayio.Palette(1)
palette_white[0] = 0xFFFFFF

palette_black = displayio.Palette(1)
palette_black[0] = 0x000000

class Knob(displayio.Group):

    def __init__(self,
        title:str = "",
        value:float = 0.5,
        callback:Callable = None,
        x:int = 0,
        y:int = 0,
        radius:int=16,
        knob_radius:int=4
    ):
        super().__init__(x=x, y=y)

        self.callback = callback
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

        # Title
        self._title = adafruit_display_text.label.Label(
            font=terminalio.FONT,
            text=title,
            color=0xFFFFFF,
            anchor_point=(0.5, 0.5),
            anchored_position=(0, radius + 4)
        )
        self.append(self._title)

        # Value
        self.reset(value)

    @property
    def title(self) -> str:
        return self._title.text
    
    @title.setter
    def title(self, value:str) -> None:
        self._title.text = value

    @property
    def value(self) -> float:
        return self._value
    
    @value.setter
    def value(self, value:float) -> None:
        if (self._previous == self._value # Actively updating
            or (self._previous < value and value > self._value) # Moved right
            or (self._previous > value and value < self._value)): # Moved left
            self._set_value(value)
        self._previous = value
    
    def reset(self, value:float = None) -> None:
        self._previous = None
        if value is not None:
            self._set_value(value)
    
    def _set_value(self, value: float) -> None:
        self._value = value
        self._do_callback()
        self._knob.x = int((self._radius - self._knob_radius) * math.sin(self._value * math.pi * 2))
        self._knob.y = int((self._radius - self._knob_radius) * math.cos(self._value * math.pi * 2))

    @property
    def callback(self) -> Callable:
        return self._callback
    
    @callback.setter
    def callback(self, value:Callable) -> None:
        self._callback = value if callable(value) else None

    def _do_callback(self) -> None:
        if self._callback is not None:
            self._callback(self._value)

class ZeroStomp(displayio.Group):

    def __init__(self):
        super().__init__()

        # NeoPixel
        self._pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
        self.pixel = (0, 0, 255)

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

        # Knobs
        self._knobs = displayio.Group()
        self.append(self._knobs)
        self._page = 0
        self._knob_pins = (
            analogio.AnalogIn(ADC_0),
            analogio.AnalogIn(ADC_1),
            analogio.AnalogIn(ADC_2)
        )
        self._expression_pin = analogio.AnalogIn(ADC_EXPR)

        self.pixel = (0, 255, 0)

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
        self._stomp_led_control = True
        self._stomp_switch_pin = digitalio.DigitalInOut(STOMP_SWITCH)
        self._stomp_switch_pin.direction = digitalio.Direction.INPUT
        self._stomp_switch_pin.pull = digitalio.Pull.UP
        self._stomp_switch = adafruit_debouncer.Debouncer(self._stomp_switch_pin)

        self.pixel = (255, 0, 0)

    @property
    def title(self) -> str:
        return self._title.text
    
    @title.setter
    def title(self, value:str) -> None:
        self._title.text = value

    @property
    def knobs(self) -> displayio.Group:
        return self._knobs
    
    def add_knob(self, title: str, value: float = 0.0, callback: Callable = None) -> None:
        self._knobs.append(knob := Knob(
            title=title,
            value=value,
            callback=callback,
            x=DISPLAY_WIDTH // (NUM_POTS + 1) * (len(self._knobs) % NUM_POTS + 1),
            y=DISPLAY_HEIGHT // 2,
        ))
        knob.hidden = self.page_count - 1 != self._page

    @property
    def page(self) -> int:
        return self._page
    
    @property
    def page_count(self) -> int:
        return max(len(self._knobs) - 1, 0) // NUM_POTS + 1
    
    @property
    def page_knob_count(self) -> int:
        return min(max(len(self._knobs) - self._page * NUM_POTS, 0), NUM_POTS)
    
    def next_page(self) -> None:
        self._page = (self._page + 1) % self.page_count
        for i, knob in enumerate(self._knobs):
            knob.hidden = i // NUM_POTS != self._page
            knob.reset()

    @property
    def bypassed(self) -> bool:
        return self._stomp_switch.value
    
    @property
    def mix(self) -> float:
        return self._mix
    
    @mix.setter
    def mix(self, value:float) -> None:
        self._mix = value
        self._update_mix()
    
    def _update_mix(self) -> None:
        self._codec.dac_mute = self.bypassed
        self._codec.mic_output_volume = 0.0 if self.bypassed else map_value(self._mix, adafruit_wm8960.advanced.OUTPUT_VOLUME_MIN, 0.0)
        self._codec.dac_volume = map_value(self._mix, adafruit_wm8960.advanced.DAC_VOLUME_MIN, 0.0)
        if not self.bypassed and self._mix >= 1.0:
            self._codec.mic_output = False
        else:
            self._codec.mic_output = True

    def update(self) -> None:
        # Switch
        self._stomp_switch.update()
        if self._stomp_led_control:
            self._stomp_led.duty_cycle = 0 if self.bypassed else 65536
        if self._stomp_switch.rose or self._stomp_switch.fell:
            self._update_mix()
            if self._stomp_switch.last_duration < SWITCH_SHORT_DURATION:
                self.next_page()

        # Knobs
        for i in range(self.page_knob_count):
            self._knobs[i + self._page * NUM_POTS].value = self._knob_pins[i].value / 65536

    @property
    def expression(self) -> float:
        return self._expression_pin.value / 65536
    
    @property
    def pixel(self) -> tuple:
        return self._pixel_color
    
    @pixel.setter
    def pixel(self, value: tuple) -> None:
        self._pixel_color = value
        self._pixel.fill(value)

    @property
    def led(self) -> float:
        return self._stomp_led.duty_cycle / 65536
    
    @led.setter
    def led(self, value: float) -> None:
        self._stomp_led_control = False
        self._stomp_led.duty_cycle = map_value(value, 0, 65536)
