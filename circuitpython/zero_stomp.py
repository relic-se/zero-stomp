# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import analogio
import audiobusio
import board
import busio
import digitalio
import displayio
import json
import math
import microcontroller
import os
import pwmio
import supervisor
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
BITS_PER_SAMPLE = 16
CHANNELS = 2
SAMPLES_SIGNED = True
BUFFER_SIZE = 1024

SWITCH_SHORT_DURATION = 0.4

SCRIPTS = "/apps"
SETTINGS = "/settings.json"

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

def constrain(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return min(max(value, min_value), max_value)

def map_value(value: float, min_value: float, max_value: float) -> float:
    return constrain(value) * (max_value - min_value) + min_value

def unmap_value(value: float, min_value: float, max_value: float) -> float:
    return constrain((value - min_value) / (max_value - min_value))

def is_rp2040() -> bool:
    return microcontroller.cpu.uid == b'EGAP\\\x0b\xc4J'

# Global Methods

_settings = None
def get_settings() -> dict:
    global _settings
    if _settings is None:
        try:
            with open(SETTINGS) as file:
                _settings = json.load(file)
        except (OSError, ValueError):
            _settings = {}
    return _settings

def save_settings() -> None:
    settings = get_settings()
    with open(SETTINGS, "w") as file:
        json.dump(settings, file)

def get_setting(*path) -> any:
    settings = get_settings()
    for name in path:
        if name in settings:
            settings = settings[name]
        else:
            return None
    return settings

def update_setting(value: any, *path) -> None:
    settings = get_settings()
    for i, name in enumerate(path):
        if i == len(path) - 1:
            settings[name] = value
        else:
            if not name in settings:
                settings[name] = {}
            settings = settings[name]

_programs = None
def get_programs() -> tuple:
    global _programs
    if _programs is None:
        _programs = tuple(filter(lambda filename: filename.endswith(".py"), os.listdir(SCRIPTS)))
    return _programs

def get_default_program() -> str:
    programs = get_programs()
    return programs[0] if programs else None

def get_current_program() -> str:
    program = get_setting("global", "program")
    if not program or not program in get_programs():
        program = get_default_program()
    return program

def get_next_program() -> str:
    program = get_current_program()
    if program is None:
        return None
    programs = get_programs()
    return programs[(programs.index(program) + 1) % len(programs)]

def load_program(program: str = None, save: bool = True) -> None:
    if program is None:
        program = get_current_program()
    if program is None or not program:
        raise OSError("Unable to load program")
    if save:
        update_setting(program, "global", "program")
    supervisor.set_next_code_file(
        filename=SCRIPTS + "/" + program,
        reload_on_success=True,
        reload_on_error=False,
        sticky_on_success=True,
        sticky_on_error=False,
        sticky_on_reload=False,
    )
    supervisor.reload()

def load_next_program(save: bool = True) -> None:
    load_program(get_next_program(), save)

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
        radius:int=9,
        knob_radius:int=2,
        threshold:float=0.01,
    ):
        super().__init__(x=x, y=y)

        self.callback = callback
        self._radius = radius
        self._knob_radius = knob_radius
        self._threshold = threshold

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
            anchored_position=(0, radius + 6)
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
        if self._previous is None:
            self._previous = value
        elif self._previous == self._value:  # Actively updating
            if abs(value - self._value) >= self._threshold:
                self._set_value(value)
                self._previous = value
        else:
            if self._previous < self._value and value >= self._value:  # Moved right
                self._set_value(value)
            if self._previous > self._value and value <= self._value:  # Moved left
                self._set_value(value)
            self._previous = value
    
    def reset(self, value:float = None) -> None:
        self._previous = None
        if value is not None:
            self._set_value(value)
    
    def _set_value(self, value: float) -> None:
        self._value = value
        self._do_callback()
        value = math.pi * (-value * 1.5 - 0.25)
        self._knob.x = int((self._radius - self._knob_radius) * math.sin(value))
        self._knob.y = int((self._radius - self._knob_radius) * math.cos(value))

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

        self.pixel = (0, 255, 255)

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

        # Stomp Switch
        self._stomp_led = pwmio.PWMOut(STOMP_LED, frequency=100000)  # frequency is out of hearing range to prevent audible noise
        self._stomp_led_control = True
        self._stomp_switch_pin = digitalio.DigitalInOut(STOMP_SWITCH)
        self._stomp_switch_pin.direction = digitalio.Direction.INPUT
        self._stomp_switch_pin.pull = digitalio.Pull.UP
        self._stomp_switch = adafruit_debouncer.Debouncer(self._stomp_switch_pin)
        self._stomp_count = 0

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

        self.pixel = (255, 255, 0)

        # Audio Codec
        self._i2c = busio.I2C(
            scl=I2C_SCL,
            sda=I2C_SDA,
            frequency=1000000,  # fast mode plus
        )
        self._codec = adafruit_wm8960.advanced.WM8960_Advanced(self._i2c)

        ## Digital Interface
        self._codec.sample_rate = SAMPLE_RATE
        self._codec.bit_depth = BITS_PER_SAMPLE
        self._codec.adc = True
        self._codec.dac = True
        self._codec.dac_output = True

        # We aren't using ADCLRCLK, so set it as GPIO
        self._codec.gpio_output = True
        self._codec.gpio_output_mode = 4 # sysclk output

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

        self.mix = 0.0
        self.level = 1.0

        self.pixel = (255, 0, 0)

        ## Begin digital audio bus
        self.i2s = audiobusio.I2S(
            bit_clock=I2S_BCLK,
            word_select=I2S_LRCLK,
            data_out=I2S_DOUT,
            data_in=I2S_DIN,
            channel_count=CHANNELS,
            sample_rate=SAMPLE_RATE,
            samples_signed=SAMPLES_SIGNED,
            buffer_size=BUFFER_SIZE,
        )

        self.pixel = (32, 0, 32)

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

    def assign_knob(self, title: str, o: object, name: str, min_value: float = 0.0, max_value: float = 1.0) -> None:
        self.add_knob(
            title=title,
            value=unmap_value(getattr(o, name), min_value, max_value),
            callback=lambda value, min_value=min_value, max_value=max_value: set_attribute(o, name, map_value(value, min_value, max_value)),
        )
        
    def knob_value(self, index: int) -> float:
        return self._knob_pins[index % len(self._knob_pins)].value / 65535

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
        self._mix = constrain(value)
        self._update_mix()
    
    def _update_mix(self) -> None:
        if self._codec.dac_mute != self.bypassed:
            self._codec.dac_mute = self.bypassed
        self._codec.mic_output_volume = 0.0 if self.bypassed else map_value(1.0 - self._mix, adafruit_wm8960.advanced.OUTPUT_VOLUME_MIN, 0.0)
        self._codec.dac_volume = map_value(self._mix, adafruit_wm8960.advanced.DAC_VOLUME_MIN, 0.0)

        if not self.bypassed and self._mix >= 1.0:
            self._codec.mic_output = False
        else:
            self._codec.mic_output = True

    @property
    def level(self) -> float:
        return self._level

    @level.setter
    def level(self, value:float) -> None:
        self._level = constrain(value)
        self._codec.headphone_volume = map_value(self._level, adafruit_wm8960.advanced.AMP_VOLUME_MIN, 0.0)

    def update(self) -> None:
        # Switch
        self._stomp_switch.update()
        if self._stomp_led_control:
            self._stomp_led.duty_cycle = 0 if self.bypassed else 65535
        if self._stomp_switch.rose or self._stomp_switch.fell:
            self._update_mix()
            if self._stomp_switch.last_duration < SWITCH_SHORT_DURATION:
                self._stomp_count += 1
                if self._stomp_count > 1 and len(get_programs()) > 1:
                    load_next_program()
                else:
                    self.next_page()
            else:
                self._stomp_count = 0

        # Knobs
        for i in range(self.page_knob_count):
            self._knobs[i + self._page * NUM_POTS].value = self.knob_value(i)

    @property
    def expression(self) -> float:
        return self._expression_pin.value / 65535
    
    @property
    def pixel(self) -> tuple:
        return self._pixel_color
    
    @pixel.setter
    def pixel(self, value: tuple) -> None:
        self._pixel_color = value
        self._pixel.fill(value)

    @property
    def led(self) -> float:
        return self._stomp_led.duty_cycle / 65535
    
    @led.setter
    def led(self, value: float) -> None:
        self._stomp_led_control = False
        self._stomp_led.duty_cycle = int(map_value(value, 0, 65535))
