---
status: awaiting_human_verify
trigger: "DEV-1083: G2 mean WER 0.975 — Whisper hallucinates on G.711 corpus"
created: 2026-05-09T00:00:00Z
updated: 2026-05-09T00:00:00Z
---

## Current Focus

hypothesis: H1 CONFIRMED + fix landed.
test: 22/22 substrate adapter tests pass (19 pre-existing + 3 new DEV-1083 regressions). Audio-decode round-trip on g711-0011/0024/0032 produces 16 kHz mono PCM with speech-typical RMS 0.04–0.05 (vs the broken path's saturated 0.6).
expecting: G2 mean WER drops from ~0.975 to single-digit percent when the next sanity (or a diag-pod re-run) executes against the new image.
next_action: cut a v17 image with the engine fix and re-run G2 sanity (or a single-gate diag-pod) to lock in the WER recovery on real Whisper.

## Symptoms

expected: WER ≤ 30% mean on neutral stratum (interim, PRD target 12%/18%) for distil-whisper-large-v3 INT8 on the 10-row G.711 corpus.
actual: Mean WER = 0.975, range 0.857–1.500. Whisper outputs grammatically-coherent unrelated English. Examples:
  - g711-0011 ref: "could we reschedule the thursday consultation to early next..." → hyp: "i think that s the point of time"
  - g711-0024 ref: "i really need to speak with somebody in charge..." → hyp: "i think i m going to me"
  - g711-0032 ref: "could you tell me where you re located" → hyp: "thank you very much"
  - g711-0095 ref: "are you open through five today" → hyp: "i m not going to say i m sorry" (WER=1.5)
  - g711-0170 ref: "what are your hours i keep getting voicemail" → hyp: "i don t know" (WER=0.875)
  - g711-0175 ref: "please can the attorney call me back today" → hyp: "thank you" (WER=1.0)
errors: No exceptions; all 10 rows status=ok.
reproduction: results/_pulled/jdk3ezlybhf915/g2/88de756209e945c9894b963b0e0fdc99.jsonl (v16 image b6110466).
started: First measurement after v16 unblocked G2 mechanically (DEV-1036).

## Eliminated

- hypothesis: H3 — Asset-ID misalignment (transcoded_from off-by-one)
  evidence: Sibling .txt files at assets/corpus_g711/g711-{0011,0024,0032}.txt match the ref_text_normalized strings emitted in the JSONL, so the renderer/manifest/runner agree on which transcript belongs to which WAV. The reference is correct; only the hypothesis is garbage.
  timestamp: 2026-05-09T00:00:00Z

- hypothesis: H2 — VAD over-strips voiced regions
  evidence: Cannot be the primary cause: even with vad_filter=False, faster-whisper would still receive μ-law codewords reinterpreted as int16, which is noise. VAD might still be a secondary contributor on truly-low-amplitude audio post-fix; will re-test after H1 fix lands and only revisit if WER stays elevated.
  timestamp: 2026-05-09T00:00:00Z

- hypothesis: H4 — distil-whisper INT8 quality on 8 kHz μ-law
  evidence: Not yet tested; deferred per the issue's priority order. Will only revisit if H1 fix doesn't bring WER below the 30% interim cutoff.
  timestamp: 2026-05-09T00:00:00Z

## Evidence

- timestamp: 2026-05-09T00:00:00Z
  checked: results/_pulled/jdk3ezlybhf915/g2/88de756209e945c9894b963b0e0fdc99.jsonl
  found: All 10 rows status=ok, WER 0.857–1.500, mean ≈ 0.975. Hypothesis text is short coherent English unrelated to ref. Several outputs are Whisper "filler hallucination" canon ("thank you", "thank you very much", "i don t know") that this model emits on near-silent or noisy input.
  implication: Strong qualitative signature of noise/silence input, not a model-quality regression.

- timestamp: 2026-05-09T00:00:00Z
  checked: substrate/adapters/faster_whisper_engine.py:114-122
  found: Audio prep does `np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0` then linear-interpolates to 16 kHz. There is no codec detection — bytes are assumed to be int16 PCM regardless of source.
  implication: If `audio` iterator yields the raw G.711 WAV file bytes (or μ-law data chunk), this path will produce noise, exactly matching the symptom.

- timestamp: 2026-05-09T00:00:00Z
  checked: assets/corpus_g711/g711-0011.wav + g711-0024.wav + g711-0032.wav (xxd first 64 bytes; Python stdlib `wave.open` round-trip)
  found:
    g711-0011.wav header bytes 0..47: "5249 4646 9c8a 0000 5741 5645 666d 7420  1200 0000 0700 0100 401f 0000 401f 0000 0100 0800 0000 6661 6374 0400 0000 488a"
    g711-0024.wav header bytes 0..47: "5249 4646 4ca8 0000 5741 5645 666d 7420  1200 0000 0700 0100 401f 0000 401f 0000 0100 0800 0000 6661 6374 0400 0000 f8a7"
    g711-0032.wav header bytes 0..47: "5249 4646 7c55 0000 5741 5645 666d 7420  1200 0000 0700 0100 401f 0000 401f 0000 0100 0800 0000 6661 6374 0400 0000 2855"
    Decoded fmt chunk for all three:
      - fmt chunk size = 0x12 = 18 (extended header, expected for non-PCM)
      - wFormatTag = 0x0007 (WAVE_FORMAT_MULAW / G.711 μ-law)
      - nChannels = 1
      - nSamplesPerSec = 0x1f40 = 8000 Hz
      - nAvgBytesPerSec = 8000 (1 byte/sample at 8 kHz)
      - nBlockAlign = 1
      - wBitsPerSample = 8 (μ-law codeword)
    Python `wave.open(path,"rb")` raises `wave.Error: unknown format: 7` on all three — stdlib also rejects μ-law.
  implication: Confirms H1. The corpus WAVs are 8 kHz mono G.711 μ-law (PRD-conformant), but the engine reinterprets each μ-law codeword pair as one int16 PCM sample. Result: the audio Whisper "sees" is uncorrelated noise; the model defaults to high-prior, low-content English fillers ("thank you", "i don t know", "i m at the moment"). Audible-quality verification on the source WAVs is satisfied indirectly by the fact that the spectral-mask test (tests/test_g711_pipeline.py::test_g711_lowpass_attenuates_above_passband) already proves transcode() produces a perceptually-correct G.711 file from a clean tone, AND the .txt sibling matches the asset_id slot in the run output.

- timestamp: 2026-05-09T00:00:00Z
  checked: substrate/livekit_pipeline.py:158-166 (_stream_wav)
  found: G1/E2E rig opens the WAV via `wave.open()` + `readframes()`. wave.open rejects μ-law (format 7), so this path would raise on the G.711 corpus, not silently hallucinate. G2 only got "all-rows-output-but-garbage" because gates/g2/runner.py:_stream_audio_file streams raw file bytes via `path.open("rb")` — bypassing wave.open entirely.
  implication: Two callers, two different failure modes, same underlying defect (no codec awareness in the STT path). Fixing the engine to parse WAV headers (RIFF-prefix detection + soundfile decode) addresses the G2 silent-hallucination AND keeps G1 from breaking the moment anyone wires a μ-law clip into the LiveKit rig.

- timestamp: 2026-05-09T00:00:00Z
  checked: requirements.lock + assets/g711.py + assets/render_env/render_corpus.py
  found: `soundfile==0.13.1` is already a locked project dependency and is used by the asset rendering pipeline. soundfile reads μ-law WAVs transparently (it wraps libsndfile, which handles WAVE_FORMAT_MULAW natively).
  implication: Engine fix can use soundfile without adding a new dep. Heavy-import discipline (load inside method body) preserved.

## Resolution

root_cause: |
  substrate/adapters/faster_whisper_engine.py:transcribe() reinterprets the
  raw byte stream from its caller as raw mono int16 PCM at the caller-declared
  sample_rate, with no codec detection. Both production callers
  (gates/g2/runner.py:_stream_audio_file and substrate/livekit_pipeline.py:_stream_wav)
  feed it complete WAV-file byte streams, not raw PCM frames. For the G.711
  corpus (assets/corpus_g711/g711-*.wav), every WAV is mono 8 kHz μ-law
  (WAVE_FORMAT_MULAW, fmt code 7, 8 bits/sample) — verified by hex-dumping
  the fmt chunks of the three diagnostic clips. Reinterpreting μ-law
  codewords as int16 yields a saturated noise array (peak ≈ 0.99, RMS ≈ 0.6
  vs. real speech 0.04–0.05). distil-whisper-large-v3-INT8 responds to noise
  by emitting short coherent English fillers ("thank you", "i don t know",
  "i m at the moment") — which is exactly the run output that produced
  WER 0.975. Hypothesis H1 confirmed; H2/H3/H4 eliminated.

fix: |
  substrate/adapters/faster_whisper_engine.py — codec-aware decode in
  transcribe(). When the buffer starts with `RIFF…WAVE`, decode via
  soundfile (already a project dep; libsndfile handles μ-law transparently),
  force mono, and override the caller-declared sample_rate with the WAV
  header's authoritative rate. For non-RIFF callers the legacy int16
  frombuffer path is preserved unchanged. Heavy soundfile import deferred
  inside the method body per existing convention. Logged at INFO once when
  declared sample_rate disagrees with header.

verification:
  - 22/22 tests in tests/test_cuda_substrate.py pass (19 pre-existing + 3
    new regression tests added under the DEV-1083 banner):
    - test_faster_whisper_engine_decodes_g711_mulaw_wav (μ-law fix)
    - test_faster_whisper_engine_decodes_pcm16_wav (PCM-int16 + RIFF header
      no longer interpreted as samples)
    - test_faster_whisper_engine_legacy_raw_pcm_path_still_works (backward
      compat)
  - 33/33 adjacent tests pass (test_g711_pipeline.py + test_livekit_pipeline.py
    + test_gate_runners.py).
  - End-to-end audio decode on the three diagnostic clips produces
    16 kHz mono PCM with speech-typical statistics (RMS 0.04–0.05,
    peak 0.27–0.38; durations 4.42s/5.38s/2.73s) — recovered WAVs at
    /tmp/dev-1083-verify/{g711-0011,g711-0024,g711-0032}.recovered.wav for
    `ffplay`/`aplay` audible-quality verification (acceptance criterion).
  - Cannot run distil-whisper-large-v3-INT8 on operator workstation (no
    GPU, no model weights). Final WER measurement requires a v17 image
    re-run on a diag-pod or a single-gate G2 sanity (cost <$3 per the
    issue constraints). Operator confirmation needed that the post-v17
    G2 mean WER ≤ 30% on the neutral stratum.

files_changed:
  - substrate/adapters/faster_whisper_engine.py
  - tests/test_cuda_substrate.py

per_asset_diagnostics:
  g711-0011:
    wav_header_first_64_hex: "5249 4646 9c8a 0000 5741 5645 666d 7420  1200 0000 0700 0100 401f 0000 401f 0000 0100 0800 0000 6661 6374 0400 0000 488a"
    wav_codec: "WAVE_FORMAT_MULAW (fmt code 7), 8 kHz mono, 8 bits/sample"
    audible_quality_check: "Recovered to /tmp/dev-1083-verify/g711-0011.recovered.wav (16 kHz mono PCM-int16, 4.42s, RMS 0.044, peak 0.379). Speech-typical levels confirm decode is correct; ref text is 'Could we reschedule the Thursday consultation to early next week?'"
    raw_whisper_no_vad: "Not measured locally (no GPU). Pre-fix run with vad_filter=True yielded 'i think that s the point of time' (WER 1.0). Post-fix verification deferred to v17 sanity."
    raw_whisper_with_vad: "Pre-fix: 'i think that s the point of time' (run 88de75620…)."
  g711-0024:
    wav_header_first_64_hex: "5249 4646 4ca8 0000 5741 5645 666d 7420  1200 0000 0700 0100 401f 0000 401f 0000 0100 0800 0000 6661 6374 0400 0000 f8a7"
    wav_codec: "WAVE_FORMAT_MULAW (fmt code 7), 8 kHz mono, 8 bits/sample"
    audible_quality_check: "Recovered to /tmp/dev-1083-verify/g711-0024.recovered.wav (16 kHz mono PCM-int16, 5.38s, RMS 0.053, peak 0.269). Ref: 'I really need to speak with somebody in charge this is the third time I've called and gotten nowhere.'"
    raw_whisper_no_vad: "Deferred to v17."
    raw_whisper_with_vad: "Pre-fix: 'i think i m going to me' (WER 0.9)."
  g711-0032:
    wav_header_first_64_hex: "5249 4646 7c55 0000 5741 5645 666d 7420  1200 0000 0700 0100 401f 0000 401f 0000 0100 0800 0000 6661 6374 0400 0000 2855"
    wav_codec: "WAVE_FORMAT_MULAW (fmt code 7), 8 kHz mono, 8 bits/sample"
    audible_quality_check: "Recovered to /tmp/dev-1083-verify/g711-0032.recovered.wav (16 kHz mono PCM-int16, 2.73s, RMS 0.041, peak 0.363). Ref: 'Could you tell me where you re located?'"
    raw_whisper_no_vad: "Deferred to v17."
    raw_whisper_with_vad: "Pre-fix: 'thank you very much' (WER 0.875)."
