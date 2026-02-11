"""LLM wrapper for Hippoclaudus — multi-backend local inference.

Supports two backends:
  - MLX (Apple Silicon, fastest on M-series chips)
  - llama-cpp-python (cross-platform: Windows/CUDA, macOS/Metal, Linux/CUDA+CPU)

Backend is auto-detected at first use. MLX is preferred on Apple Silicon;
llama-cpp-python is the fallback everywhere else.

Model format differs by backend:
  - MLX: HuggingFace safetensors (or MLX-converted weights)
  - llama.cpp: GGUF quantized models
"""

import json
import os
import platform
import re
from typing import Optional


# ============================================================
# Backend Detection
# ============================================================

_backend: Optional[str] = None
_backend_cache: dict = {}


def detect_backend() -> str:
    """Auto-detect the best available inference backend."""
    global _backend
    if _backend is not None:
        return _backend

    system = platform.system()
    machine = platform.machine()

    # Apple Silicon fast path: prefer MLX
    if system == "Darwin" and machine == "arm64":
        try:
            import mlx.core  # noqa: F401
            from mlx_lm import load  # noqa: F401
            _backend = "mlx"
            return _backend
        except ImportError:
            pass

    # Cross-platform: llama-cpp-python
    try:
        from llama_cpp import Llama  # noqa: F401
        _backend = "llama_cpp"
        return _backend
    except ImportError:
        pass

    raise RuntimeError(
        "No inference backend available.\n"
        "Install one of:\n"
        "  Apple Silicon: pip install mlx mlx-lm\n"
        "  Cross-platform: pip install llama-cpp-python\n"
        "  Windows CUDA:   CMAKE_ARGS=\"-DGGML_CUDA=on\" pip install llama-cpp-python"
    )


def get_backend() -> str:
    """Return the active backend name ('mlx' or 'llama_cpp')."""
    return detect_backend()


# ============================================================
# MLX Backend
# ============================================================

def _load_mlx(model_name: str):
    """Load an MLX model. Returns (model, tokenizer)."""
    from mlx_lm import load
    if model_name not in _backend_cache:
        model, tokenizer = load(model_name)
        _backend_cache[model_name] = (model, tokenizer)
    return _backend_cache[model_name]


def _run_mlx(model_name: str, prompt: str, max_tokens: int, temp: float) -> str:
    """Run inference via MLX."""
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = _load_mlx(model_name)

    messages = [{"role": "user", "content": prompt}]
    if hasattr(tokenizer, "apply_chat_template"):
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        formatted = prompt

    sampler = make_sampler(temp=temp)
    response = generate(
        model, tokenizer,
        prompt=formatted,
        max_tokens=max_tokens,
        sampler=sampler,
        verbose=False,
    )
    return response


# ============================================================
# llama.cpp Backend
# ============================================================

def _load_llama_cpp(model_name: str):
    """Load a GGUF model via llama-cpp-python. Returns a Llama instance."""
    from llama_cpp import Llama

    if model_name not in _backend_cache:
        if not os.path.isfile(model_name):
            raise FileNotFoundError(
                f"GGUF model not found: {model_name}\n"
                f"Download a GGUF model and pass the file path as model_name."
            )
        llm = Llama(
            model_path=model_name,
            n_ctx=4096,
            n_gpu_layers=-1,  # offload all layers to GPU
            verbose=False,
        )
        _backend_cache[model_name] = llm
    return _backend_cache[model_name]


def _run_llama_cpp(model_name: str, prompt: str, max_tokens: int, temp: float) -> str:
    """Run inference via llama-cpp-python."""
    llm = _load_llama_cpp(model_name)

    response = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temp,
    )
    return response["choices"][0]["message"]["content"]


# ============================================================
# Unified Interface
# ============================================================

def run_prompt(model_name: str, prompt: str, max_tokens: int = 1024, temp: float = 0.3) -> str:
    """Run a prompt through the local LLM. Backend is auto-detected."""
    backend = detect_backend()
    if backend == "mlx":
        return _run_mlx(model_name, prompt, max_tokens, temp)
    elif backend == "llama_cpp":
        return _run_llama_cpp(model_name, prompt, max_tokens, temp)
    else:
        raise RuntimeError(f"Unknown backend: {backend}")


def extract_json(text: str) -> Optional[dict]:
    """Extract JSON object from LLM output, handling markdown code fences."""
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ============================================================
# Prompt Templates
# ============================================================

CONSOLIDATION_PROMPT = """You are a memory consolidation system. Given the following session log, extract a structured summary.

SESSION LOG:
{session_text}

Return a JSON object with exactly these fields:
{{
  "state_delta": "A 50-100 word dense summary of what changed, what was decided, what's unresolved",
  "entities": {{
    "people": ["list of people mentioned"],
    "projects": ["projects or products affected"],
    "tools": ["tech, tools, or services referenced"]
  }},
  "security_context": "Any MNPI, regulated data, or permission boundaries discussed (or 'none')",
  "emotional_signals": "Detected frustration, excitement, urgency, or other emotional tone (or 'neutral')",
  "open_threads": ["unresolved items or follow-ups"]
}}

Return ONLY the JSON object, no other text."""


ENTITY_TAG_PROMPT = """Given this memory content, extract entity tags.

MEMORY:
{content}

Return a JSON object with exactly these fields:
{{
  "people": ["people mentioned by name"],
  "projects": ["projects, products, or companies"],
  "tools": ["technologies, tools, services"],
  "topics": ["abstract topics or themes"],
  "suggested_tags": ["comma-separated list of all tags combined"]
}}

Return ONLY the JSON object, no other text."""


COMM_PROFILE_PROMPT = """Analyze these conversation excerpts involving {person} and describe their communication patterns.

EXCERPTS:
{excerpts}

Return a JSON object with exactly these fields:
{{
  "tone": "general communication tone",
  "priorities": ["what they tend to focus on"],
  "decision_style": "how they make decisions",
  "response_patterns": "typical response time and engagement level",
  "key_phrases": ["characteristic phrases or expressions"],
  "working_relationship": "description of the working dynamic"
}}

Return ONLY the JSON object, no other text."""


# ============================================================
# High-Level Task Functions
# ============================================================

def consolidate_session(model_name: str, session_text: str) -> Optional[dict]:
    """Run the consolidation prompt and return structured output."""
    prompt = CONSOLIDATION_PROMPT.format(session_text=session_text)
    response = run_prompt(model_name, prompt, max_tokens=512)
    return extract_json(response)


def tag_memory(model_name: str, content: str) -> Optional[dict]:
    """Run the entity tagging prompt and return structured tags."""
    prompt = ENTITY_TAG_PROMPT.format(content=content)
    response = run_prompt(model_name, prompt, max_tokens=256)
    return extract_json(response)


def analyze_comm_profile(model_name: str, person: str, excerpts: str) -> Optional[dict]:
    """Run the communication profile prompt and return analysis."""
    prompt = COMM_PROFILE_PROMPT.format(person=person, excerpts=excerpts)
    response = run_prompt(model_name, prompt, max_tokens=512)
    return extract_json(response)
