// SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
//
// SPDX-License-Identifier: GPLv3

#ifndef _CONFIG_H
#define _CONFIG_H

// Pin Configuration

#define UART_TX 0
#define UART_RX 1

#define I2S_BCLK 2
#define I2S_LRCLK 3
#define I2S_DOUT 4
#define I2S_DIN 5

#define I2C_SDA 6
#define I2C_SCL 7
#define I2C_WIRE Wire1

#define STOMP_LED 8
#define STOMP_SWITCH 9

#define DISPLAY_RESET 10
#define DISPLAY_DC 11
#define DISPLAY_CS 13
#define DISPLAY_SCK 14
#define DISPLAY_TX 15

#define ADC_0 26
#define ADC_1 27
#define ADC_2 28
#define ADC_EXPR 29
#define NUM_POTS 3

// Constants

#define DISPLAY_WIDTH 128
#define DISPLAY_HEIGHT 64

#define SAMPLE_RATE 48000
#define BITS_PER_SAMPLE 16
#define CHANNELS 2

#define SWITCH_SHORT_DURATION 400 // ms

#endif
