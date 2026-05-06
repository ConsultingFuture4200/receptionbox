"""Backend adapters composed by CUDASubstrate (D-14).

Adapters MUST NOT raise into the substrate. The Phase 1 cost-watch lock-in
applies here: log WARNING + return / yield-nothing on every error path.
T-02-01-03 disposition is `mitigate`; this contract is the mitigation.

Each adapter is HTTP-based (vLLM / Chatterbox / Kokoro speak OpenAI-style
or REST endpoints) except `FasterWhisperEngine`, which is in-process and
defers heavy imports inside method bodies so the workstation can import
this package with no CUDA / torch / faster_whisper installed.
"""

from .chatterbox_client import ChatterboxClient
from .faster_whisper_engine import FasterWhisperEngine
from .kokoro_client import KokoroClient
from .vllm_client import VLLMClient

__all__ = [
    "ChatterboxClient",
    "FasterWhisperEngine",
    "KokoroClient",
    "VLLMClient",
]
