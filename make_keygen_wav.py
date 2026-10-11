import wave
import math
import struct

SAMPLE_RATE = 44100
DURATION = 8.0
BPM = 160
BEAT = 60.0 / BPM
STEPS_PER_BEAT = 4
STEP_TIME = BEAT / STEPS_PER_BEAT

def note_to_freq(note):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = int(note[-1])
    n = notes.index(note[:-1])
    return 440.0 * (2.0 ** ((n - 9 + (octave - 4) * 12) / 12.0))

chords = [['C4', 'E4', 'G4', 'C5'], ['A3', 'C4', 'E4', 'A4'], ['F3', 'A3', 'C4', 'F4'], ['G3', 'B3', 'D4', 'G4']]
bass_prog = ['C3', 'C3', 'A2', 'A2', 'F2', 'F2', 'G2', 'G2']

def generate_square_wave(freq, duration, volume=0.2):
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    period = SAMPLE_RATE / freq if freq > 0 else 0
    for i in range(num_samples):
        if freq == 0:
            samples.append(0)
        else:
            val = volume if (i % period) < (period / 2) else -volume
            env = math.exp(-3.0 * i / num_samples)
            samples.append(val * env)
    return samples

audio = []
step_samples = int(SAMPLE_RATE * STEP_TIME)
for step in range(int(DURATION / STEP_TIME)):
    chord_idx = (step // 16) % len(chords)
    chord = chords[chord_idx]
    arp_note = chord[step % 4]
    if (step % 2) != 0: arp_note = chord[(step % 4 + 2) % 4]
    bass_note = bass_prog[(step // 8) % len(bass_prog)]
    lead_wave = generate_square_wave(note_to_freq(arp_note), STEP_TIME, 0.15)
    bass_wave = generate_square_wave(note_to_freq(bass_note), STEP_TIME, 0.2)
    for i in range(step_samples):
        audio.append(max(-1.0, min(1.0, lead_wave[i] + bass_wave[i])))

with wave.open('keygen.wav', 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(SAMPLE_RATE)
    data = b''.join(struct.pack('<h', int(s * 32767)) for s in audio)
    f.writeframes(data)
print("Keygen wav created successfully.")
