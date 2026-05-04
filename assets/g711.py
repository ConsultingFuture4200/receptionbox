"""G.711 mu-law transcoding (ASSETS-07).

Pipeline (locked from D-02 + RESEARCH.md G.711 Transcoding):
- 16 kHz WAV input
- ffmpeg with `-af aresample=resampler=soxr:precision=28` (Pitfall 4
  mitigation: wrong defaults produce artifacts that contaminate WER)
- 8 kHz mono `pcm_mulaw` output WAV
- Spectral validation via scipy.signal.welch PSD compared against a
  Twilio->Twilio reference clip (D-02; gracefully skipped when reference
  is absent -- A4 in Assumptions Log)

The 200-clip stratified G.711 set is rendered by Plan 04, which calls
`transcode()` here.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
from typing import TypedDict

import numpy as np
import soundfile as sf
from scipy.signal import welch


def transcode(
    input_wav: pathlib.Path,
    output_wav: pathlib.Path,
    *,
    target_rate: int = 8000,
) -> None:
    """16 kHz WAV -> 8 kHz pcm_mulaw WAV via ffmpeg + soxr resampler."""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_wav),
        "-ac",
        "1",
        "-ar",
        str(target_rate),
        "-af",
        "aresample=resampler=soxr:precision=28",
        "-c:a",
        "pcm_mulaw",
        str(output_wav),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


class SpectralReport(TypedDict):
    status: str  # "ok" | "no_reference" | "fail"
    psd_freqs: list[float]
    psd_subject: list[float]
    psd_reference: list[float] | None
    notes: str


def validate_spectral_mask(
    subject_wav: pathlib.Path,
    reference_wav: pathlib.Path | None = None,
    *,
    nperseg: int = 1024,
) -> SpectralReport:
    """Compute Welch PSD on the transcoded clip; compare to reference mask if given.

    Phase 1 returns "no_reference" when reference is absent (per A4 in
    Assumptions Log: operator pre-flight may not have Twilio reference yet).
    The full mask comparison logic ships when the reference clip lands.
    """
    samples, sr = sf.read(subject_wav)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    f, pxx = welch(samples, fs=sr, nperseg=min(nperseg, len(samples)))
    subject_psd = pxx.tolist()
    if reference_wav is None or not reference_wav.exists():
        return {
            "status": "no_reference",
            "psd_freqs": f.tolist(),
            "psd_subject": subject_psd,
            "psd_reference": None,
            "notes": (
                "ASSETS-07 spectral mask comparison skipped: no Twilio reference "
                "clip available in Phase 1 (A4 in Assumptions Log). Plan 04 "
                "documents this gap; refresh once a real-PSTN reference lands."
            ),
        }
    ref_samples, ref_sr = sf.read(reference_wav)
    if ref_samples.ndim > 1:
        ref_samples = ref_samples.mean(axis=1)
    if ref_sr != sr:
        # Trim to the lower freq grid by re-running welch on resampled length
        # to keep the comparison on a common axis. Cheap approximation for now.
        ref_samples = np.interp(
            np.linspace(0, 1, int(len(ref_samples) * sr / ref_sr)),
            np.linspace(0, 1, len(ref_samples)),
            ref_samples,
        )
    _rf, ref_pxx = welch(ref_samples, fs=sr, nperseg=min(nperseg, len(ref_samples)))
    return {
        "status": "ok",
        "psd_freqs": f.tolist(),
        "psd_subject": subject_psd,
        "psd_reference": ref_pxx.tolist(),
        "notes": "Reference comparison computed; downstream caller asserts mask thresholds.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="G.711 transcode + spectral validate")
    parser.add_argument("--validate", action="store_true", help="run spectral validation only")
    parser.add_argument("--input", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--reference", type=pathlib.Path, default=None)
    args = parser.parse_args()
    if args.validate and args.input:
        report = validate_spectral_mask(args.input, args.reference)
        print(report["status"], "--", report["notes"])
        return 0
    if args.input and args.output:
        transcode(args.input, args.output)
        print(f"OK transcoded -> {args.output}")
        return 0
    print("nothing to do; provide --input/--output or --validate --input")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
