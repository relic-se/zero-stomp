// SPDX-FileCopyrightText: Copyright (c) 2025 Cooper Dalrymple
//
// SPDX-License-Identifier: GPLv3

#include "AudioTools.h"
#include "AudioTools/AudioLibs/WM8960Stream.h"

#include "config.h"

SineWaveGenerator<int16_t> sineWave(32000);
GeneratedSoundStream<int16_t> sound(sineWave);
WM8960Stream codec;
StreamCopy copier(codec, sound);

void setup(void) {
  // Open Serial
  Serial.begin(115200);
  while (!Serial);
  AudioLogger::instance().begin(Serial, AudioLogger::Warning);
  
  Serial.println("Zero Stomp");

  // Setup UART
  Serial.println("Starting UART...");
  Serial1.setRX(UART_RX);
  Serial1.setTX(UART_TX);
  Serial1.begin(31250);
  
  // Setup I2C
  Serial.println("Starting I2C...");
  I2C_WIRE.setSDA(I2C_SDA);
  I2C_WIRE.setSCL(I2C_SCL);
  I2C_WIRE.setClock(1000000); // fast mode plus
  I2C_WIRE.begin();
    
  // Setup I2S
  Serial.println("Starting I2S...");
  auto config = codec.defaultConfig(TX_MODE); // NOTE: RXTX_MODE currently unsupported
  config.sample_rate = SAMPLE_RATE; 
  config.channels = CHANNELS;
  config.bits_per_sample = BITS_PER_SAMPLE;
  config.wire = &I2C_WIRE;
  config.pin_bck = I2S_BCLK;
  config.pin_ws = I2S_LRCLK;
  config.pin_data = I2S_DOUT;
  config.pin_data_rx = I2S_DIN;
  
  if (!codec.begin(config)) {
    Serial.println("Failed to initiate codec");
    stop();
  }
  
  // Setup sine wave
  Serial.println("Starting test output...");
  sineWave.begin(CHANNELS, SAMPLE_RATE, N_B4);
}

void loop() {
  // Copy sound to out
  copier.copy();
}
