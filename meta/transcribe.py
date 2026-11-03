"""Muse Voice Transcribe 1.0 — turns a voice brief into text the agent can cite."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from .client import Transport


def _to_wav(path: Path) -> Path:
    if path.suffix.lower() == ".wav":
        return path
    out = Path(tempfile.mkdtemp()) / (path.stem + ".wav")
    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", str(out)]
    elif shutil.which("afconvert"):  # macOS built-in
        cmd = ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(path), str(out)]
    else:
        raise RuntimeError("need ffmpeg (or macOS afconvert) to convert audio to WAV")
    subprocess.run(cmd, check=True)
    return out


def _pick_text(d) -> str:
    """The TranscribeResponse field names are not in the public docs we read; search for text."""
    if isinstance(d, str):
        return d
    if isinstance(d, dict):
        for k in ("text", "transcript", "transcription"):
            if isinstance(d.get(k), str):
                return d[k]
        for v in d.values():
            s = _pick_text(v)
            if s:
                return s
    if isinstance(d, list):
        return " ".join(filter(None, (_pick_text(x) for x in d)))
    return ""


def transcribe(t: Transport, audio_path: Path, keywords: list[str] | None = None) -> str:
    model = t.cfg["models"]["transcribe"]
    wav = _to_wav(Path(audio_path))

    def live():
        req = {"model": model, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK",
               "languageBias": t.cfg.get("voice", {}).get("languages", ["English"])}
        if keywords:
            req["keywords"] = keywords[:20]
        files = {
            "request": (None, json.dumps(req), "application/json"),
            "audio": (wav.name, wav.read_bytes(), "audio/wav"),
        }
        r = httpx.post(
            f"{t.cfg['api']['base_url']}/asr/transcribe",
            headers={"Authorization": f"Bearer {t.api_key}", "Accept": "application/json"},
            files=files,
            timeout=t.cfg["api"]["timeout_s"],
        )
        r.raise_for_status()
        raw = r.json()
        return {"text": _pick_text(raw), "raw": raw}

    return t.call("transcribe", live, {"model": model, "file": wav.name})["text"]
