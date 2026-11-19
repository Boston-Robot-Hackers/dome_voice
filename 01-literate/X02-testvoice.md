---
version: "1.0"
generated: "2026-11-19"
---

# X02 — `testvoice.py`: One-Turn Diagnostic

## What it is for

When the robot "doesn't hear" a command, there are several places it can go wrong: the wake word, the silence cutoff, Vosk, or the mapper. `testvoice.py` runs **one turn with no ROS** and prints what happened at each step, then *says which step failed*.

```
python3 testvoice.py         # one wake + command, with a diagnosis
python3 testvoice.py beep    # play two beeps, to test the speaker
```

## What it prints

1. **The resolved config**: its source path, wake word, threshold, hits, grammar and silence settings. This is the first thing to check: it shows which YAML was loaded, and the values after defaults and overrides (chapter 01).
2. **At the wake**: the score, the time it took, the highest score seen, and the measured noise floor and silence cutoff.
3. **The turn**: the cleaned and raw text, whether speech started, the floor and cutoff, and how long it took.
4. **A diagnosis**, if the turn was empty:
   - `command_started=False`: the speech never rose above the cutoff. Speak louder, or the cutoff is too high.
   - started, but no raw text: Vosk heard audio but matched nothing. The word is probably not in the grammar.
   - raw text, but empty after cleaning: the wake-word stripping removed everything.
5. **Otherwise, the intent** the mapper would publish.

## Why it's useful

It reuses the real `VoiceRuntime` and the real config loader, and it only adds printing. What it shows is exactly what the node would do, minus ROS.

## Observations

1. **Its prompt is out of date.** It says "say 'alexa help'", but the robot's wake word is `hey_marvin`. Printing `config.wake_word` instead would keep it right.
2. **It is a script at the repo root**, not a package entry point, so it is run from the source tree with the package on the path.
