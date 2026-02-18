# hippoclaudus/llm_installer.py
"""Optional LLM backend installer.

Detects hardware (Apple Silicon / NVIDIA / CPU), installs the
appropriate inference backend, and downloads the default model.
"""

import platform as stdlib_platform
import subprocess
from pathlib import Path
from typing import Optional

import click

from hippoclaudus.platform import detect_platform, get_venv_pip, update_dotfile, get_dotfile_path


def _is_apple_silicon() -> bool:
    """Check if running on Apple Silicon."""
    if detect_platform() != "darwin":
        return False
    try:
        machine = stdlib_platform.machine()
        return machine in ("arm64", "aarch64")
    except Exception:
        return False


def _has_nvidia_gpu() -> bool:
    """Check if an NVIDIA GPU is available."""
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_hardware() -> dict:
    """Detect the best LLM backend for this machine."""
    plat = detect_platform()

    if plat == "darwin" and _is_apple_silicon():
        return {"backend": "mlx", "description": "Apple Silicon (MLX)"}
    elif _has_nvidia_gpu():
        return {"backend": "cuda", "description": "NVIDIA GPU (llama-cpp CUDA)"}
    else:
        return {"backend": "cpu", "description": "CPU (llama-cpp)"}


def get_packages_for_backend(backend: str) -> list:
    """Return pip packages needed for the given backend."""
    if backend == "mlx":
        return ["mlx", "mlx-lm"]
    elif backend == "cuda":
        return ["llama-cpp-python"]
    else:  # cpu
        return ["llama-cpp-python"]


def get_default_model(backend: str) -> str:
    """Return the default model identifier for the backend."""
    if backend == "mlx":
        return "mlx-community/Mistral-7B-Instruct-v0.3-4bit"
    else:
        return "TheBloke/Mistral-7B-Instruct-v0.3-GGUF"


def install_backend_packages(venv_path: Path, backend: str) -> None:
    """Install the LLM backend packages into the venv."""
    pip = get_venv_pip(venv_path)
    packages = get_packages_for_backend(backend)

    click.echo(f"  Installing: {', '.join(packages)}")

    cmd = [str(pip), "install", "--quiet"] + packages
    if backend == "cuda":
        # llama-cpp-python needs CMAKE_ARGS for CUDA
        import os
        env = os.environ.copy()
        env["CMAKE_ARGS"] = "-DLLAMA_CUBLAS=on"
        subprocess.run(cmd, check=True, capture_output=True, env=env)
    else:
        subprocess.run(cmd, check=True, capture_output=True)


def download_model(backend: str, models_dir: Path) -> str:
    """Download the default model. Returns the model path/identifier."""
    model_name = get_default_model(backend)
    models_dir.mkdir(parents=True, exist_ok=True)

    if backend == "mlx":
        # MLX models are cached by huggingface_hub automatically
        # We just need to trigger the download
        click.echo(f"  Downloading: {model_name}")
        click.echo("  (This may take several minutes for a ~4GB model)")
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(model_name)
            click.echo("  Model downloaded and cached")
        except ImportError:
            # Fall back to mlx_lm which will download on first use
            click.echo("  Model will be downloaded on first use by MLX-LM.")
    else:
        # GGUF models -- download specific file
        click.echo(f"  Downloading: {model_name}")
        click.echo("  (This may take several minutes for a ~4GB model)")
        try:
            from huggingface_hub import hf_hub_download
            hf_hub_download(
                repo_id=model_name,
                filename="mistral-7b-instruct-v0.3.Q4_K_M.gguf",
                local_dir=str(models_dir),
            )
            click.echo("  Model downloaded")
        except ImportError:
            click.echo("  Install huggingface_hub for automatic download:")
            click.echo("  pip install huggingface_hub")

    return model_name


def run_install_llm(venv_path: Path, models_dir: Path) -> dict:
    """Full LLM backend installation flow."""
    click.echo("\n  Hippoclaudus LLM Backend Setup\n")

    # Detect hardware
    hw = detect_hardware()
    click.echo(f"  Detected: {hw['description']}")
    click.echo(f"  Backend:  {hw['backend']}\n")

    # Install packages
    click.echo("  Installing inference backend...")
    install_backend_packages(venv_path, hw["backend"])
    click.echo("  Backend installed\n")

    # Download model
    click.echo("  Downloading model...")
    model = download_model(hw["backend"], models_dir)
    click.echo()

    # Update dotfile
    dotfile = get_dotfile_path()
    update_dotfile(dotfile, llm_installed=True)

    click.echo("  LLM backend ready")
    click.echo(f"    Backend: {hw['backend']}")
    click.echo(f"    Model:   {model}\n")

    return {
        "backend": hw["backend"],
        "model": model,
    }
