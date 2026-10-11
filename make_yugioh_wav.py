import wave
import math
import struct

SAMPLE_RATE = 44100
BPM = 140
BEAT = 60.0 / BPM
STEPS_PER_BEAT = 4
STEP_TIME = BEAT / STEPS_PER_BEAT

def note_to_freq(note):
    if note == "REST": return 0.0
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = int(note[-1])
    n = notes.index(note[:-1])
    return 440.0 * (2.0 ** ((n - 9 + (octave - 4) * 12) / 12.0))

# Yu-Gi-Oh Theme inspired riff
lead_seq = [
    "E4", "E4", "REST", "B3", "REST", "REST", "REST", "REST",
    "E4", "E4", "REST", "G4", "REST", "REST", "REST", "REST",
    "E4", "E4", "REST", "B3", "REST", "REST", "REST", "REST",
    "A4", "REST", "G4", "REST", "F#4", "REST", "D4", "REST",
]

# Galloping bass
bass_seq = [
    "E2", "E2", "E3", "E2", "E2", "E3", "E2", "E2",
    "C2", "C2", "C3", "C2", "C2", "C3", "C2", "C2",
    "D2", "D2", "D3", "D2", "D2", "D3", "D2", "D2",
    "B1", "B1", "B2", "B1", "B1", "B2", "B1", "B1",
]

def generate_square_wave(freq, duration, volume=0.2, duty=0.5):
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    period = SAMPLE_RATE / freq if freq > 0 else 0
    for i in range(num_samples):
        if freq == 0:
            samples.append(0)
        else:
            val = volume if (i % period) < (period * duty) else -volume
            env = math.exp(-3.0 * i / num_samples) # decay
            samples.append(val * env)
    return samples

audio = []
step_samples = int(SAMPLE_RATE * STEP_TIME)

for _ in range(4): # 4 repetitions
    for step in range(32):
        lead_note = lead_seq[step]
        bass_note = bass_seq[step]
        
        lead_wave = generate_square_wave(note_to_freq(lead_note), STEP_TIME, 0.20, 0.25)
        bass_wave = generate_square_wave(note_to_freq(bass_note), STEP_TIME, 0.25, 0.5)
        
        for i in range(step_samples):
            mixed = lead_wave[i] + bass_wave[i]
            audio.append(max(-1.0, min(1.0, mixed)))

with wave.open('keygen.wav', 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(SAMPLE_RATE)
    data = b''.join(struct.pack('<h', int(s * 32767)) for s in audio)
    f.writeframes(data)

print("Yu-Gi-Oh! inspired keygen loop generated.")
