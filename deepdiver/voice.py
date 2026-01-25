"""Voice capture and local transcription helpers (whisper.cpp CLI)."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

from .config import COLORS, console
from .ui import toast

DEFAULT_MODEL = "ggml-base.bin"

MODEL_CATALOG = {
    "ggml-tiny.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    "ggml-base.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "ggml-small.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "ggml-medium.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    "ggml-large-v3.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
    "ggml-large-v3-turbo.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
}


def _get_model_dir() -> Path:
    env_dir = os.environ.get("DEEPDIVER_WHISPER_MODEL_DIR", "").strip()
    model_dir = Path(env_dir).expanduser() if env_dir else Path("~/.deepdiver/models/whisper").expanduser()
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def _resolve_model_path() -> Path:
    model_name = os.environ.get("DEEPDIVER_WHISPER_MODEL", DEFAULT_MODEL).strip()
    model_dir = _get_model_dir()
    model_path = (model_dir / model_name).expanduser()

    if model_path.exists():
        return model_path

    url = os.environ.get("DEEPDIVER_WHISPER_MODEL_URL", "").strip() or MODEL_CATALOG.get(model_name)
    if not url:
        raise FileNotFoundError(
            f"Whisper model not found: {model_path}. Set DEEPDIVER_WHISPER_MODEL_URL to download it."
        )

    console.print(f"[dim]Downloading model: {model_name}[/dim]")
    _download_file(url, model_path)
    return model_path


def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or "0")
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = int(downloaded * 100 / total)
                    console.print(f"[dim]  {pct}% ({downloaded // (1024*1024)}MB/{total // (1024*1024)}MB)[/dim]")
    console.print(f"[green]Model downloaded: {dest}[/green]")


def _resolve_whisper_binary() -> str:
    env_bin = os.environ.get("DEEPDIVER_WHISPER_BIN", "").strip() or os.environ.get(
        "DEEPDIVER_WHISPER_CPP", ""
    ).strip()
    if env_bin:
        return env_bin

    for name in ("whisper-cli", "whisper.cpp", "main"):
        path = shutil.which(name)
        if path:
            return path

    raise FileNotFoundError(
        "Whisper CLI binary not found. Set DEEPDIVER_WHISPER_BIN to your whisper.cpp binary."
    )


def _pick_recorder() -> str:
    env = os.environ.get("DEEPDIVER_VOICE_RECORDER", "").strip()
    if env:
        return env
    if shutil.which("arecord"):
        return "arecord"
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    raise FileNotFoundError("No recorder found. Install arecord (ALSA) or ffmpeg.")


def _record_audio(seconds: int, output_path: Path) -> None:
    recorder = _pick_recorder()
    if recorder == "arecord":
        cmd = [
            "arecord",
            "-q",
            "-r",
            "16000",
            "-f",
            "S16_LE",
            "-c",
            "1",
            "-d",
            str(seconds),
            str(output_path),
        ]
    elif recorder == "ffmpeg":
        silence_seconds = float(os.environ.get("DEEPDIVER_VOICE_SILENCE_SECONDS", "0") or "0")
        noise_level = os.environ.get("DEEPDIVER_VOICE_SILENCE_NOISE", "-40dB").strip() or "-40dB"
        if silence_seconds > 0:
            _record_audio_ffmpeg_silence(
                seconds=seconds,
                output_path=output_path,
                silence_seconds=silence_seconds,
                noise_level=noise_level,
            )
            return

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "alsa",
            "-i",
            "default",
            "-t",
            str(seconds),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_path),
        ]
    else:
        raise RuntimeError(f"Unknown recorder: {recorder}")

    console.print(f"[dim]Recording {seconds}s via {recorder}...[/dim]")
    subprocess.run(cmd, check=True)


def _record_audio_ffmpeg_silence(
    *, seconds: int, output_path: Path, silence_seconds: float, noise_level: str
) -> None:
    # Stop recording when silence lasts for the configured duration (after speech starts).
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "info",
        "-f",
        "alsa",
        "-i",
        "default",
        "-t",
        str(seconds),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        f"silencedetect=noise={noise_level}:d={silence_seconds}",
        str(output_path),
    ]

    console.print(
        f"[dim]Recording up to {seconds}s (auto-stop after {silence_seconds}s silence)...[/dim]"
    )
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    heard_audio = False
    silence_start_re = re.compile(r"silence_start:\s*(\d+(\.\d+)?)")
    silence_end_re = re.compile(r"silence_end:\s*(\d+(\.\d+)?)")

    try:
        assert process.stderr is not None
        for line in process.stderr:
            line = line.strip()
            if not line:
                continue

            match_end = silence_end_re.search(line)
            if match_end:
                heard_audio = True
                continue

            match_start = silence_start_re.search(line)
            if match_start:
                try:
                    start_time = float(match_start.group(1))
                except ValueError:
                    start_time = 0.0

                if start_time > 0:
                    heard_audio = True

                if heard_audio:
                    process.terminate()
                    break
    finally:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _run_whisper(binary: str, model_path: Path, audio_path: Path) -> str:
    env_cmd = os.environ.get("DEEPDIVER_WHISPER_CMD", "").strip()
    extra_args = os.environ.get("DEEPDIVER_WHISPER_ARGS", "").strip()

    with tempfile.TemporaryDirectory() as tempdir:
        output_base = Path(tempdir) / "transcript"

        if env_cmd:
            cmd_str = env_cmd.format(
                bin=binary,
                model=str(model_path),
                audio=str(audio_path),
                out=str(output_base),
            )
            cmd = shlex.split(cmd_str)
        else:
            cmd = [
                binary,
                "-m",
                str(model_path),
                "-f",
                str(audio_path),
                "-otxt",
                "-of",
                str(output_base),
            ]
            if extra_args:
                cmd.extend(shlex.split(extra_args))

        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Whisper CLI failed")

        txt_path = Path(f"{output_base}.txt")
        if txt_path.exists():
            return txt_path.read_text().strip()

        return _extract_text_from_stdout(result.stdout)


def _extract_text_from_stdout(stdout: str) -> str:
    lines = []
    for line in stdout.splitlines():
        m = re.match(r"^\s*\[\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}\.\d{3}\]\s*(.*)$", line)
        if m:
            lines.append(m.group(1).strip())
    if lines:
        return " ".join([l for l in lines if l])
    return stdout.strip()


def transcribe_from_mic(seconds: int) -> str:
    if seconds <= 0:
        raise ValueError("Seconds must be a positive integer")

    binary = _resolve_whisper_binary()
    model_path = _resolve_model_path()

    with tempfile.TemporaryDirectory() as tempdir:
        audio_path = Path(tempdir) / "voice.wav"
        _record_audio(seconds, audio_path)

        console.print("[dim]Transcribing...[/dim]")
        text = _run_whisper(binary, model_path, audio_path).strip()

    if not text:
        toast("No speech detected", kind="warning")
    return text
