# I02 The voice runtime was not installed on the robot

**Opened:** 2026-11-19. **Status:** installed; mic signal fixed (see Recognition); waiting on the full-pipeline robot test.

## Symptom

`python3 -m dome_voice.runtime --config config/voice.yaml --trials 5` crashed with `ModuleNotFoundError: No module named 'openwakeword'`. dome2's TF05 had already recorded the same thing (E2b, TF05.2): `voice_input` crashed and `speech_output` couldn't find piper.

## Cause

**Provisioning never installed the voice runtime.** After the robot was reprovisioned (around 2026-11-17), none of it was present:

- `openwakeword` and `vosk` were in neither `provision_dome/manifest/pip.txt` nor `package.xml`.
- The Vosk model had no installer.
- `~/.bashrc` pointed piper at `dome_control/bin/` and `piper_model/`, which are gitignored and were gone.

**The `hey_marvin` model was never lost.** It is a pre-trained model bundled with openWakeWord 0.4.0 (`resources/models/hey_marvin_v0.1.onnx`).

## What was tested

- **Mic board.** A 2 s `arecord` from `hw:0,0` started with about 1 s of codec power-up swing (DC from −32768 back to about 0), then a quiet room at −60 to −67 dBFS. The board works. `wait_for_wake`'s 1.5 s initial drain covers the swing.
- **Models load.** `load_wake_model("hey_marvin")` returns key `hey_marvin_v0.1`; `load_stt_model("small")` builds a grammar recogniser. No code change was needed.
- **Piper.** It synthesised 1.8 s of speech in 0.9 s.

## What was done

- **Installed** with `pip3 install --break-system-packages vosk openwakeword`, into `~/.local`.
  - pip picked **openwakeword 0.4.0**, because 0.5+ needs `tflite-runtime`, which has no Python 3.12 wheel.
  - 0.4.0 is also the API `load_wake_model` uses (`wakeword_model_paths=`). **It is now pinned** in `pip.txt`.
- **Vosk model** is at `~/models/vosk-model-small-en-us-0.15`.
- **Piper and the lessac voice** were installed by `install-optional-deps.sh piper` under `$DOME_HOME/.local` (`~/.dome/.local` on this robot).
- **`provision_dome` changes:**
  - `pip.txt` lists `openwakeword==0.4.0` and `vosk`.
  - `install-optional-deps.sh` gained a `vosk` target, and its piper target now installs lessac (it used to install amy).
  - `manifest/bashrc` points `DOME_PIPER_*` at `${DOME_HOME:-$HOME}/.local`.
- **`~/.bashrc`** got the same `DOME_PIPER_*` change.
- **`package.xml`** has a comment pointing to `provision_dome`, since neither package has a rosdep key.

## Recognition: the mic signal was being cut out

**After install, wake worked but "stop" was recognised about 1 time in 4.** Three separate causes were found (2026-11-19), all measured on raw `arecord` captures and `mic_diag.wav`.

### 1. A tick every 80 ms (our code)

- `read_mono_chunk` subtracted each chunk's own mean, so the signal stepped at every chunk boundary.
- Median boundary jump was 1078 vs 53 mid-chunk; after the fix, 56 vs 63.
- **Fixed** in `runtime.py`, with regression tests (see `process/04-tasks/chores.md`).

### 2. The codec's ADC highpass was disabled

- The raw input's DC level swings rail to rail for seconds after the mic opens.
- **Fixed** with `amixer -c 0 sset 'ADC HPF Cut-off' 0.0045xFs,0.0045xFs`. The control is per channel; setting one value only fixes the left.

### 3. A slow, large wander at the mic input saturates the ADC

- At high gain the ADC hits its limit; the codec HPF then outputs exact zeros, so speech is muted for 30–1200 ms at a time.
- The muted fraction rises with gain:

| PGA | Gain | Muted |
|---|---|---|
| 104 | 52 dB | 25–37 % |
| 92 | 46 dB | 18 % |
| 80 | 40 dB | 7–9 % |
| 60 | 30 dB | 0 % |

- **The earlier PGA 80 setting muted about 8% of the time**, which explains part of the original misses.
- **Now PGA 60.** With it, "stop" was recognised 4 of 4 tries in `mic_diag.py`.
- **The source is unknown.** Suspects: lidar, motor board, power supply. Test by unplugging each and measuring the muted fraction at PGA 80.

### 4. Speech too quiet for Vosk, and the wake beep in the capture

- Found with F05 recordings: 7 turns, replayed offline through `capture_command`. The replay matched live exactly (3/7).
- Speech arrives at −30 to −40 dBFS, too quiet for Vosk's small model. The PGA can't add more without muting (3).
- The wake beep fills the first ~0.4 s of the capture and sets `command_started` before the user speaks.
- **Fixed:** `stt_gain_db` (Vosk's input only; 10 dB, then 20 dB after a quieter session: 4/9 → 7/9) and skipping `beep_wake_duration` plus 2 chunks after wake. Replay: 7/7.

### Mixer state

- Capture: `PGA` 60, `ADC HPF Cut-off` 0.0045xFs on both channels.
- Playback was nearly silent: raised to `PCM` 127, `HP DAC`/`Line DAC`/`HPCOM DAC` 118.
- **Saved** with `sudo alsactl store` (2026-11-19 20:08; PCM since lowered to 100). Provisioning is a chore.

## Left open

- **A live test:** a wake word plus a command on the mic, and a spoken announcement on the speaker.
- **Install location.** `install-optional-deps.sh` puts binaries under `$DOME_HOME`, which is the robot's data directory (maps, telemetry) on this robot. It works, but it's an odd place for them.
- **A stale export.** `provision_dome/manifest/bashrc` still exports `DOME_VOICE_CONFIG`, which dome2 F07 removed.
- **A spare voice.** The unused amy voice is at `~/.dome/.local/share/piper/en_US-amy-medium.onnx` (63 MB).
