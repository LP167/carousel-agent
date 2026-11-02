"""One door to the Meta Model API.

Every model call goes through `Transport.call(kind, fn, payload)`. That gives us:
  * retries with backoff on 429/5xx
  * a usage log per run (runs/<id>/usage.jsonl)
  * record / replay: a live run can be saved and replayed later without an API key
    (judges and tests can run the whole agent from replay/<name>/).
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class ReplayMiss(RuntimeError):
    pass


class Transport:
    """mode = live | record | replay"""

    def __init__(self, mode: str = "live", replay_dir: Path | None = None, usage_path: Path | None = None):
        self.mode = mode
        self.replay_dir = Path(replay_dir) if replay_dir else None
        self.usage_path = Path(usage_path) if usage_path else None
        self.n = 0
        self.cfg = load_config()
        self._client = None
        if mode in ("record", "replay") and not self.replay_dir:
            raise ValueError("record/replay needs replay_dir")
        if mode == "record":
            (self.replay_dir / "calls").mkdir(parents=True, exist_ok=True)

    # -- raw clients -------------------------------------------------------
    @property
    def openai(self):
        if self._client is None:
            from openai import OpenAI

            load_env()
            key = os.environ.get("MODEL_API_KEY")
            if not key:
                raise RuntimeError("MODEL_API_KEY is not set (put it in .env)")
            self._client = OpenAI(
                base_url=self.cfg["api"]["base_url"],
                api_key=key,
                timeout=self.cfg["api"]["timeout_s"],
                max_retries=0,
            )
        return self._client

    @property
    def api_key(self) -> str:
        load_env()
        return os.environ["MODEL_API_KEY"]

    # -- the single entry point -------------------------------------------
    def call(self, kind: str, fn, payload_summary: dict | None = None):
        """fn() performs the live call and returns a JSON-serialisable dict."""
        self.n += 1
        tag = f"{self.n:04d}_{kind}"
        if self.mode == "replay":
            path = self.replay_dir / "calls" / f"{tag}.json"
            if not path.exists():
                raise ReplayMiss(f"no recorded response {path.name}")
            return json.loads(path.read_text())["response"]

        tries = self.cfg["api"]["max_retries"]
        delay = 2.0
        for attempt in range(tries + 1):
            t0 = time.time()
            try:
                resp = fn()
                break
            except Exception as e:  # noqa: BLE001
                status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
                retryable = status in (429, 500, 502, 503, 504) or status is None and "timeout" in str(e).lower()
                if attempt < tries and retryable:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        self._log_usage(kind, resp, time.time() - t0)
        if self.mode == "record":
            (self.replay_dir / "calls" / f"{tag}.json").write_text(
                json.dumps({"kind": kind, "request": payload_summary or {}, "response": resp}, ensure_ascii=False, indent=1)
            )
        return resp

    def _log_usage(self, kind, resp, secs):
        if not self.usage_path:
            return
        usage = resp.get("usage") if isinstance(resp, dict) else None
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.usage_path.open("a") as f:
            f.write(json.dumps({"kind": kind, "secs": round(secs, 2), "usage": usage}) + "\n")


def image_data_url(path: Path | str, max_side: int | None = None) -> str:
    """Base64 data URL for Spark/SAM image input, optionally downscaled."""
    path = Path(path)
    data = path.read_bytes()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    if max_side:
        from io import BytesIO

        from PIL import Image

        im = Image.open(BytesIO(data))
        im.thumbnail((max_side, max_side))
        buf = BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        data, mime = buf.getvalue(), "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
