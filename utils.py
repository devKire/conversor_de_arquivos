"""
utils.py - Utilitários: detecção de FFmpeg, formatação, presets, histórico
"""

import os
import sys
import json
import shutil
import datetime
from pathlib import Path


# ──────────────────────────────────────────────────────────
# Caminhos comuns do FFmpeg no Windows
# ──────────────────────────────────────────────────────────

COMMON_FFMPEG_PATHS = [
    "ffmpeg",                                  # PATH do sistema
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    str(Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe"),
    # pasta local ao executável (para embutir ffmpeg)
    str(Path(sys.executable).parent / "ffmpeg" / "ffmpeg.exe"),
    str(Path(__file__).parent / "ffmpeg" / "ffmpeg.exe"),
]


def find_ffmpeg() -> str | None:
    """Procura o FFmpeg em locais comuns e no PATH; retorna o caminho ou None."""
    # shutil.which respeita o PATH do sistema
    found = shutil.which("ffmpeg")
    if found:
        return found

    for path in COMMON_FFMPEG_PATHS:
        if os.path.isfile(path):
            return path

    return None


# ──────────────────────────────────────────────────────────
# Formatação humana
# ──────────────────────────────────────────────────────────

def human_size(n_bytes: int) -> str:
    """Formata bytes para exibição (KB, MB, etc.)."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n_bytes) < 1024:
            return f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.1f} TB"


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


# ──────────────────────────────────────────────────────────
# Extensões suportadas
# ──────────────────────────────────────────────────────────

SUPPORTED_INPUT_FORMATS = [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif", ".gif"]
SUPPORTED_OUTPUT_FORMATS = ["WEBP", "JPG", "PNG", "AVIF", "BMP"]

IMAGE_FILETYPES = [
    ("Imagens", "*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.tif *.gif"),
    ("PNG", "*.png"),
    ("JPEG", "*.jpg *.jpeg"),
    ("WebP", "*.webp"),
    ("BMP", "*.bmp"),
    ("Todos", "*.*"),
]


# ──────────────────────────────────────────────────────────
# Geração de nome de saída
# ──────────────────────────────────────────────────────────

def output_filename(
    input_path: str,
    output_dir: str,
    output_format: str,
    sequential_index: int | None = None,
    zero_pad: int = 3,
) -> str:
    """
    Gera o caminho de saída.
    - sequential_index=None → mantém o nome original
    - sequential_index=N    → usa '001', '002', etc.
    """
    ext = output_format.lower()
    if ext == "jpg":
        ext = "jpg"

    if sequential_index is not None:
        stem = str(sequential_index).zfill(zero_pad)
    else:
        stem = Path(input_path).stem

    return str(Path(output_dir) / f"{stem}.{ext}")


# ──────────────────────────────────────────────────────────
# Configurações / Presets  (JSON em AppData ou pasta local)
# ──────────────────────────────────────────────────────────

CONFIG_FILE = Path.home() / ".ffimg_converter" / "config.json"

DEFAULT_CONFIG = {
    "ffmpeg_path": "",
    "last_output_dir": "",
    "presets": {
        "WebP Alta Qualidade": {"format": "WEBP", "quality": 80},
        "WebP Comprimido":     {"format": "WEBP", "quality": 50},
        "JPEG Otimizado":      {"format": "JPG",  "quality": 60},
        "AVIF Eficiente":      {"format": "AVIF", "quality": 60, "crf": 25},
    },
    "conversion_history": [],
}


def load_config() -> dict:
    """Carrega configurações do disco (ou retorna padrões)."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                # Garante que todas as chaves existam
                for k, v in DEFAULT_CONFIG.items():
                    cfg.setdefault(k, v)
                return cfg
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """Salva configurações no disco."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Limita histórico a 200 entradas
        if "conversion_history" in config:
            config["conversion_history"] = config["conversion_history"][-200:]
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[config] Erro ao salvar: {e}")


def add_history_entry(config: dict, entry: dict):
    """Adiciona uma entrada ao histórico e salva."""
    entry["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
    config.setdefault("conversion_history", []).append(entry)
    save_config(config)


# ──────────────────────────────────────────────────────────
# Export de log
# ──────────────────────────────────────────────────────────

def export_log(log_text: str, dest_path: str):
    """Salva o conteúdo do log em um arquivo .txt."""
    with open(dest_path, "w", encoding="utf-8") as f:
        header = f"=== FFImg Converter — Log exportado em {datetime.datetime.now()} ===\n\n"
        f.write(header + log_text)
