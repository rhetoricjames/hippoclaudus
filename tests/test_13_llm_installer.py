# tests/test_13_llm_installer.py
"""Tests for LLM backend installer."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestHardwareDetection:
    """Detect GPU/hardware for LLM backend selection."""

    def test_detect_hardware_returns_dict(self):
        from hippoclaudus.llm_installer import detect_hardware
        result = detect_hardware()
        assert "backend" in result
        assert result["backend"] in ("mlx", "cuda", "cpu")

    @patch("hippoclaudus.llm_installer.detect_platform", return_value="darwin")
    @patch("hippoclaudus.llm_installer._is_apple_silicon", return_value=True)
    def test_detect_apple_silicon(self, mock_silicon, mock_plat):
        from hippoclaudus.llm_installer import detect_hardware
        result = detect_hardware()
        assert result["backend"] == "mlx"

    @patch("hippoclaudus.llm_installer.detect_platform", return_value="linux")
    @patch("hippoclaudus.llm_installer._has_nvidia_gpu", return_value=True)
    def test_detect_nvidia(self, mock_gpu, mock_plat):
        from hippoclaudus.llm_installer import detect_hardware
        result = detect_hardware()
        assert result["backend"] == "cuda"

    @patch("hippoclaudus.llm_installer.detect_platform", return_value="linux")
    @patch("hippoclaudus.llm_installer._has_nvidia_gpu", return_value=False)
    @patch("hippoclaudus.llm_installer._is_apple_silicon", return_value=False)
    def test_detect_cpu_fallback(self, mock_silicon, mock_gpu, mock_plat):
        from hippoclaudus.llm_installer import detect_hardware
        result = detect_hardware()
        assert result["backend"] == "cpu"


class TestPackageList:
    """Correct packages for each backend."""

    def test_mlx_packages(self):
        from hippoclaudus.llm_installer import get_packages_for_backend
        pkgs = get_packages_for_backend("mlx")
        assert "mlx" in pkgs
        assert "mlx-lm" in pkgs

    def test_cuda_packages(self):
        from hippoclaudus.llm_installer import get_packages_for_backend
        pkgs = get_packages_for_backend("cuda")
        assert "llama-cpp-python" in pkgs

    def test_cpu_packages(self):
        from hippoclaudus.llm_installer import get_packages_for_backend
        pkgs = get_packages_for_backend("cpu")
        assert "llama-cpp-python" in pkgs


class TestModelInfo:
    """Model selection for each backend."""

    def test_mlx_model_name(self):
        from hippoclaudus.llm_installer import get_default_model
        model = get_default_model("mlx")
        assert "mlx-community" in model

    def test_cpu_model_name(self):
        from hippoclaudus.llm_installer import get_default_model
        model = get_default_model("cpu")
        assert isinstance(model, str)
        assert len(model) > 0
