"""
converter.py - Lógica de conversão usando FFmpeg via subprocess
"""

import subprocess
import os
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional


# ──────────────────────────────────────────────────────────
# Modelos de dados
# ──────────────────────────────────────────────────────────

@dataclass
class ConversionTask:
    input_path: str
    output_path: str
    format: str
    quality: int = 60
    crf: int = 30


@dataclass
class ConversionResult:
    task: ConversionTask
    success: bool
    original_size: int = 0
    output_size: int = 0
    error_message: str = ""
    ffmpeg_log: str = ""

    @property
    def size_saved_bytes(self) -> int:
        return max(0, self.original_size - self.output_size)

    @property
    def size_saved_percent(self) -> float:
        if self.original_size == 0:
            return 0.0
        return (self.size_saved_bytes / self.original_size) * 100


# ──────────────────────────────────────────────────────────
# Comandos FFmpeg por formato
# ──────────────────────────────────────────────────────────

def build_ffmpeg_command(ffmpeg_path: str, task: ConversionTask) -> list[str]:
    """Monta o comando FFmpeg adequado para cada formato de saída."""
    fmt = task.format.lower()
    cmd = [ffmpeg_path, "-y", "-i", task.input_path]

    if fmt == "webp":
        cmd += ["-qscale", str(task.quality)]
    elif fmt in ("jpg", "jpeg"):
        cmd += ["-q:v", str(max(1, min(31, task.quality // 3)))]
    elif fmt == "png":
        # PNG é lossless; -compression_level 0-9
        level = min(9, max(0, 9 - task.quality // 11))
        cmd += ["-compression_level", str(level)]
    elif fmt == "avif":
        cmd += ["-crf", str(task.crf), "-b:v", "0"]
    elif fmt == "bmp":
        pass  # sem parâmetros extras necessários
    else:
        cmd += ["-qscale", str(task.quality)]

    cmd.append(task.output_path)
    return cmd


# ──────────────────────────────────────────────────────────
# Executor principal
# ──────────────────────────────────────────────────────────

class FFmpegConverter:
    """Gerencia conversões únicas e em lote com callbacks de progresso."""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._cancel_event = threading.Event()

    # ── Verificação de disponibilidade ──────────────────────

    def check_ffmpeg(self) -> tuple[bool, str]:
        """Retorna (ok, versão_ou_mensagem_de_erro)."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True, text=True, timeout=10
            )
            first_line = result.stdout.splitlines()[0] if result.stdout else "FFmpeg encontrado"
            return True, first_line
        except FileNotFoundError:
            return False, f"FFmpeg não encontrado em: {self.ffmpeg_path}"
        except Exception as e:
            return False, str(e)

    # ── Conversão única ──────────────────────────────────────

    def convert_single(
        self,
        task: ConversionTask,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> ConversionResult:
        """Converte um único arquivo e retorna o resultado."""
        original_size = os.path.getsize(task.input_path) if os.path.exists(task.input_path) else 0
        cmd = build_ffmpeg_command(self.ffmpeg_path, task)
        log_lines: list[str] = [" ".join(cmd)]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in process.stdout:
                line = line.rstrip()
                log_lines.append(line)
                if log_callback:
                    log_callback(line)

            process.wait()
            success = process.returncode == 0
            output_size = os.path.getsize(task.output_path) if success and os.path.exists(task.output_path) else 0

            return ConversionResult(
                task=task,
                success=success,
                original_size=original_size,
                output_size=output_size,
                error_message="" if success else f"FFmpeg retornou código {process.returncode}",
                ffmpeg_log="\n".join(log_lines),
            )
        except Exception as e:
            return ConversionResult(
                task=task,
                success=False,
                original_size=original_size,
                error_message=str(e),
                ffmpeg_log="\n".join(log_lines),
            )

    # ── Conversão em lote ────────────────────────────────────

    def cancel(self):
        """Sinaliza cancelamento da fila de lote."""
        self._cancel_event.set()

    def reset_cancel(self):
        self._cancel_event.clear()

    def convert_batch(
        self,
        tasks: list[ConversionTask],
        progress_callback: Optional[Callable[[int, int, ConversionResult], None]] = None,
        max_workers: int = 2,
    ) -> list[ConversionResult]:
        """
        Converte uma lista de tarefas em paralelo.
        progress_callback(concluidos, total, resultado_mais_recente)
        """
        self.reset_cancel()
        results: list[ConversionResult] = []
        total = len(tasks)
        completed = 0
        lock = threading.Lock()

        def run_task(task: ConversionTask) -> ConversionResult:
            if self._cancel_event.is_set():
                return ConversionResult(task=task, success=False, error_message="Cancelado pelo usuário")
            return self.convert_single(task)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_task, t): t for t in tasks}
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    results.append(result)
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total, result)

        return results
