---
version: "1.0"
generated: "2026-11-22"
---

# 07 — `piper_server.py`: One Piper, Kept Running

## Introduction

`piper_server` is the ROS-free half of speech output (chapter 04). It has three small pieces:

- **`PiperServer`** keeps one Piper process alive and turns text into audio on request.
- **`SpeechCache`** remembers the audio of recent sentences.
- **`split_sentences`** cuts text into the units the other two work on.

It exists because **loading the voice model cost about 0.6 s on every announcement** (F15, TF15.0). A process that stays up pays that once.

## Talking to a running Piper

The Piper binary installed on the robot (rhasspy's C++ release) has a **`--json-input`** mode. It reads one JSON object per line, writes a WAV for each, and prints the WAV's path when it's done:

```python
def piper_command(piper_bin, model_path, length_scale):
    return [piper_bin, "--model", model_path, "--json-input",
            "--length_scale", str(length_scale), "--quiet"]
```

That printed path is **the only "done" signal Piper gives**. Raw streaming (`--output_raw`) has no marker between utterances, so a long-lived process in that mode can't say where one reply ends and the next begins. A file per request, announced by its path, is the simplest protocol that has a boundary.

It was checked on the robot before any code was written: two requests 3 s apart produced one process start, and the second WAV arrived about 1 s after its request, with no second model load.

## One request

```python
def synthesize(self, text: str) -> bytes:
    out_path = self.out_dir / f"dome_speech_{self.proc.pid}_{next(self.file_numbers)}.wav"
    request = {"text": text, "output_file": str(out_path)}
    ...
    done_path = self.proc.stdout.readline().decode().strip()
    ...
    try:
        return self.read_pcm(out_path)
    finally:
        out_path.unlink(missing_ok=True)
```

- **Requests are strictly one at a time.** Write a line, read a line. With one caller (the node's single-threaded callback) there is nothing to interleave.
- **Files live in `/dev/shm`**, which is RAM, so there's no SD-card write per sentence, and each one is deleted as soon as it's read.
- **Names include Piper's PID and a counter**, so two nodes, or a restart, can never read each other's files.

### Checking what came back

```python
shape = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
if shape != (1, 2, self.sample_rate):
    raise RuntimeError(...)
```

The node plays audio as raw PCM at a rate it read from the model's JSON. **A WAV in any other shape would play as noise or at the wrong speed**, so it's rejected here, at the boundary, with a message that says what arrived.

### When Piper dies

```python
def raise_exited(self) -> None:
    code = self.proc.wait()
    err = self.proc.stderr.read().decode(errors="replace").strip()
    raise RuntimeError(f"piper exited ({code}): {err}")
```

Piper exiting shows up in one of two ways: **a broken pipe on write**, or **an empty line on read** (end of file). Both lead here, so the error always carries Piper's own message, such as a bad model path, instead of a bare `BrokenPipeError`.

**stdin is unbuffered** (`bufsize=0`). With a buffer, a failed write would leave bytes behind that Python tries to flush into the dead pipe later, at garbage collection, raising an error far from its cause.

### Closing

`close` ends Piper's input, which makes Piper exit on its own, and kills it only if that takes more than 2 s. Closing twice, or after Piper died, is harmless.

## The cache

```python
class SpeechCache:
    def get(self, text):
        pcm = self.audio_by_text.get(text)
        if pcm is not None:
            self.audio_by_text.move_to_end(text)
        return pcm

    def put(self, text, pcm):
        self.audio_by_text[text] = pcm
        self.audio_by_text.move_to_end(text)
        if len(self.audio_by_text) > self.size:
            self.audio_by_text.popitem(last=False)
```

This is a classic **LRU cache on an `OrderedDict`**. The dict keeps insertion order, `move_to_end` marks an entry as just used, and `popitem(last=False)` drops the oldest. Both operations are O(1).

32 entries of a few seconds each is about 6 MB at most. **The key is the text alone**, which is correct because the voice and length scale are fixed for the node's life; volume is applied after the cache, by the node.

## Splitting sentences

```python
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
```

A **lookbehind** splits on the whitespace *after* `.`, `!` or `?`, so the punctuation stays with its sentence (Piper needs it for intonation) and a decimal like `0.2`, with no space after its dot, stays whole.

## Observations

1. **No timeout on Piper.** If Piper hung without exiting, `readline` would block the node forever. It hasn't happened; a watchdog would be the fix if it does.
2. **No restart.** A dead Piper makes every later request fail (chapter 04, observation 1).
3. **The cache is keyed by exact text.** "Linear speed 0.2" and "linear speed 0.2" are different entries. Normalising case and spacing would raise the hit rate slightly.
4. **Abbreviations split early** ("e.g. this"). A list of exceptions would fix it if robot speech ever needs it.
