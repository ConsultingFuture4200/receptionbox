"""Phase 0 evaluation asset corpora.

This package authors and renders the 5 corpora consumed by gate runners
in Phase 2/3:
- corpus_500     -> 500-call synthetic conversation corpus (Plan 04)
- corpus_g711    -> 200-clip G.711 mu-law STT eval set (Plan 04)
- corpus_hesitation  -> hesitation adversarial set (Plan 04)
- corpus_upl     -> 200 UPL probes (Plan 03; this file)
- corpus_benign  -> 50 benign control probes (Plan 03)
- corpus_tts_pairs -> 30 TTS A/B text pairs (Plan 03)

ASSETS-08 manifest discipline: every asset has a row in `assets/manifest.csv`
with provenance (source URL or generator + license + creation UTC + SHA-256).
The pre-commit hook (INFRA-05) refuses commits where audio is unlisted.
"""
