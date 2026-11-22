# F15 — Speech starts sooner after an announcement

**Priority**: Medium

**Date Created:** 2026-11-22

**Done:** no

**Tasks File Created:** yes

**Tests Written:** no

**Test Passing:** no

**Description**: Cut the time from an `/announcement` to the first sound
out of the speaker. Today it's about **2 s**, which makes quick replies,
like dome_pad's Status key, feel slow.

## What was measured (2026-11-22, through rosbridge from the Mac)

- dome_pad Status press → `/joy` → `/intent` → `/announcement`: **8-12 ms**.
  Everything before `speech_output` is fast.
- `/announcement` → first sound: **about 2 s** (by ear, the user).
- `/voice/speaking` true → false for "linear speed 0.2, angular speed 0.7":
  **about 5.9 s**, three times in a row.

So the delay is inside `speech_output` on the Pi, but it hasn't been split
into its parts yet.

## Where the time could go

`speak_text` starts two new processes for every announcement: `piper`
(the rhasspy C++ binary, release 2023.11.14-2, installed by
`provision_dome`) and `aplay`. Candidates:

1. **Piper loading the voice model** on every call.
2. **Piper waiting for the whole sentence:** with `--output_raw` it writes
   audio a sentence at a time, so nothing plays until the first sentence
   is fully synthesised. Status replies are one sentence.
3. **`aplay` opening the card**, and the Seeed board's codec and amplifier
   powering up from idle. I02 saw about 1 s of power-up swing on the same
   codec's microphone side.

I02 measured Piper at "1.8 s of speech in 0.9 s" including the model load,
which suggests 1 alone isn't the 2 s.

## Scope

- **Measure first** (TF15.0): split the 2 s between the causes above, on
  the Pi.
- **Then fix the largest causes**, from these, chosen by the measurement:
  - A **long-lived Piper process**, fed one announcement per line, so the
    model loads once. The binary's `--json-input` mode reports when each
    utterance is done.
  - A **long-lived audio output** (keep `aplay` or the ALSA device open),
    so the codec doesn't power down between announcements.
  - **Shorter first sentences** where the text allows, so playback starts
    sooner.
- `/voice/speaking`, `speech.gain` and announcement priorities keep working
  as now.

## Out of scope

- Switching TTS engine or voice.
- The VM side (`llm_node`) and the LLM's own latency.

## How to Demo

**Setup**: robot running `d c vo p`; VM running `vo p`; dome_pad flashed.

**Steps**:
1. Press Status on the pad five times, a few seconds apart.
2. Time press → first sound (by ear or with a phone's audio recording).

**Expected output**: first sound well under 1 s each time, and
`/voice/speaking` still true for exactly the length of each utterance.

## Process Gate

After creating this feature file and the corresponding task file, **stop and present the plan to the user**. Do not write any code or content until the user gives explicit approval to proceed.
