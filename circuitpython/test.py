import array
import ulab.numpy as np

import zero_stomp

TYPE_EFFECT = "effect"
TYPE_MIXER = "mixer"
TYPE_LOOPBACK = "loopback"
TYPE = TYPE_LOOPBACK

TEST = False

device = zero_stomp.ZeroStomp()
device.mix = 0.5

if TYPE == TYPE_EFFECT:
    import audiodelays
    effect = audiodelays.Echo(
        max_delay_ms=100,
        delay_ms=200,
        mix=1.0,
        freq_shift=True,
        
        sample_rate=zero_stomp.SAMPLE_RATE,
        channel_count=zero_stomp.CHANNELS,
        bits_per_sample=zero_stomp.BITS_PER_SAMPLE,
        samples_signed=zero_stomp.SAMPLES_SIGNED,
        buffer_size=zero_stomp.BUFFER_SIZE,
    )
    
    effect.play(device.i2s, loop=True)
    device.i2s.play(effect, loop=True)
    
elif TYPE == TYPE_MIXER:
    import audiomixer
    mixer = audiomixer.Mixer(
        voice_count=1,

        sample_rate=zero_stomp.SAMPLE_RATE,
        channel_count=zero_stomp.CHANNELS,
        bits_per_sample=zero_stomp.BITS_PER_SAMPLE,
        samples_signed=zero_stomp.SAMPLES_SIGNED,
        buffer_size=zero_stomp.BUFFER_SIZE,
    )
    device.i2s.play(mixer)
    mixer.voice[0].play(device.i2s, loop=True)
    
else:
    device.i2s.play(device.i2s)

if TEST:
    b = array.array("h", [0] * 256)
    while True:
        device.i2s.record(b, len(b))
        print(np.max(np.array(b, dtype=np.int16)))
