"""G.711 transcoder + spectral validation tests (ASSETS-07).

Generates a synthetic 1-second 16 kHz tone, runs transcode(), and asserts:
- output WAV exists, is mono, is 8 kHz, is pcm_mulaw
- validate_spectral_mask returns 'no_reference' when no reference is provided
- spectral validation on a transcoded 1 kHz tone shows attenuation above 3 kHz
  (G.711 nominal passband is 300-3400 Hz; any signal above ~3.4 kHz must be
  significantly attenuated by the 8 kHz Nyquist + soxr lowpass)
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from assets.g711 import transcode, validate_spectral_mask


def _have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


@pytest.mark.skipif(not _have_ffmpeg(), reason="ffmpeg not on PATH")
def test_transcode_produces_8khz_mulaw(tmp_path: pathlib.Path) -> None:
    # Synthetic 1-second 1 kHz tone @ 16 kHz mono
    sr = 16000
    t = np.linspace(0.0, 1.0, sr, endpoint=False, dtype=np.float32)
    tone = 0.5 * np.sin(2 * np.pi * 1000 * t)
    in_wav = tmp_path / "in.wav"
    out_wav = tmp_path / "out.wav"
    sf.write(in_wav, tone, sr)
    transcode(in_wav, out_wav)
    assert out_wav.exists()
    # Probe with ffprobe to verify codec
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,sample_rate,channels",
            "-of",
            "default=nw=1",
            str(out_wav),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "codec_name=pcm_mulaw" in probe.stdout
    assert "sample_rate=8000" in probe.stdout
    assert "channels=1" in probe.stdout


@pytest.mark.skipif(not _have_ffmpeg(), reason="ffmpeg not on PATH")
def test_validate_spectral_mask_no_reference_returns_skipped(tmp_path: pathlib.Path) -> None:
    sr = 16000
    t = np.linspace(0.0, 1.0, sr, endpoint=False, dtype=np.float32)
    tone = 0.5 * np.sin(2 * np.pi * 1000 * t)
    in_wav = tmp_path / "tone.wav"
    sf.write(in_wav, tone, sr)
    out_wav = tmp_path / "tone.mulaw.wav"
    transcode(in_wav, out_wav)
    report = validate_spectral_mask(out_wav, reference_wav=None)
    assert report["status"] == "no_reference"
    assert report["psd_reference"] is None
    assert "no Twilio reference" in report["notes"]


@pytest.mark.skipif(not _have_ffmpeg(), reason="ffmpeg not on PATH")
def test_g711_lowpass_attenuates_above_passband(tmp_path: pathlib.Path) -> None:
    """In-band tone (1 kHz) must dominate above-passband tone (5 kHz) post-G.711.

    G.711 is sampled at 8 kHz so the Nyquist limit is 4 kHz; soxr's anti-alias
    lowpass at the 16->8 downsample step kills any energy above ~3.7 kHz
    before sampling. A 5 kHz input tone is fully out-of-band and must show
    substantially less energy than a 1 kHz in-band tone after transcoding.
    """
    sr = 16000
    duration = 1.0
    t = np.linspace(0.0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    tone_in_band = 0.5 * np.sin(2 * np.pi * 1000 * t)
    tone_out_band = 0.5 * np.sin(2 * np.pi * 5000 * t)

    in_band_wav = tmp_path / "in_band.wav"
    out_band_wav = tmp_path / "out_band.wav"
    sf.write(in_band_wav, tone_in_band, sr)
    sf.write(out_band_wav, tone_out_band, sr)

    in_band_mulaw = tmp_path / "in_band.mulaw.wav"
    out_band_mulaw = tmp_path / "out_band.mulaw.wav"
    transcode(in_band_wav, in_band_mulaw)
    transcode(out_band_wav, out_band_mulaw)

    rep_in = validate_spectral_mask(in_band_mulaw)
    rep_out = validate_spectral_mask(out_band_mulaw)
    # Peak energy of the 1 kHz tone (in-band) must dominate peak of the 5 kHz
    # out-of-band tone by a clear margin after G.711 transcoding.
    peak_in = max(rep_in["psd_subject"])
    peak_out = max(rep_out["psd_subject"])
    assert peak_in > 10 * peak_out, (
        f"G.711 must attenuate above-passband: in-band peak={peak_in:.4g}, "
        f"out-band peak={peak_out:.4g}"
    )


def test_g711_module_imports() -> None:
    """Module must import even when ffmpeg is unavailable (deps only)."""
    import assets.g711 as m

    assert callable(m.transcode)
    assert callable(m.validate_spectral_mask)
