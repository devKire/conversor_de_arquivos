"""
gui.py - Interface gráfica principal (CustomTkinter, tema dark)
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit("CustomTkinter não instalado. Execute: pip install customtkinter")

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from converter import FFmpegConverter, ConversionTask, ConversionResult
from utils import (
    find_ffmpeg, human_size, format_percent,
    SUPPORTED_OUTPUT_FORMATS, IMAGE_FILETYPES,
    load_config, save_config, add_history_entry,
    output_filename, export_log,
)


# ──────────────────────────────────────────────────────────
# Paleta de cores
# ──────────────────────────────────────────────────────────

C = {
    "bg":        "#0f0f13",
    "surface":   "#1a1a24",
    "card":      "#22222e",
    "border":    "#2e2e40",
    "accent":    "#6c63ff",
    "accent2":   "#00d4aa",
    "danger":    "#ff4d6d",
    "success":   "#00d4aa",
    "warning":   "#ffd166",
    "text":      "#e8e8f0",
    "text_dim":  "#7878a0",
    "text_muted":"#4a4a6a",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ──────────────────────────────────────────────────────────
# Widget auxiliar: painel de log
# ──────────────────────────────────────────────────────────

class LogPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=C["card"], corner_radius=10, **kwargs)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(header, text="▸ LOG FFMPEG", font=("Consolas", 11, "bold"),
                     text_color=C["accent"]).pack(side="left")

        self._btn_export = ctk.CTkButton(
            header, text="Exportar", width=80, height=24,
            font=("Segoe UI", 11), fg_color=C["border"],
            hover_color=C["accent"], corner_radius=6,
            command=self._export
        )
        self._btn_export.pack(side="right")

        self._btn_clear = ctk.CTkButton(
            header, text="Limpar", width=70, height=24,
            font=("Segoe UI", 11), fg_color=C["border"],
            hover_color=C["danger"], corner_radius=6,
            command=self.clear
        )
        self._btn_clear.pack(side="right", padx=(0, 6))

        self._text = tk.Text(
            self, bg=C["bg"], fg=C["text"], insertbackground=C["accent"],
            font=("Consolas", 10), relief="flat", wrap="word",
            selectbackground=C["accent"], padx=8, pady=6,
            state="disabled"
        )
        self._text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # tags de cor
        self._text.tag_config("ok",   foreground=C["success"])
        self._text.tag_config("err",  foreground=C["danger"])
        self._text.tag_config("info", foreground=C["accent"])
        self._text.tag_config("dim",  foreground=C["text_dim"])

    def append(self, line: str, tag: str = ""):
        self._text.configure(state="normal")
        tag_val = tag or self._detect_tag(line)
        self._text.insert("end", line + "\n", tag_val)
        self._text.see("end")
        self._text.configure(state="disabled")

    def _detect_tag(self, line: str) -> str:
        ll = line.lower()
        if "error" in ll or "failed" in ll:
            return "err"
        if "warning" in ll:
            return "err"
        if line.startswith("ffmpeg version") or "built with" in ll:
            return "dim"
        if "✔" in line or "concluído" in ll or "sucesso" in ll:
            return "ok"
        return ""

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def get_text(self) -> str:
        return self._text.get("1.0", "end")

    def _export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
            title="Exportar log",
        )
        if path:
            try:
                export_log(self.get_text(), path)
                messagebox.showinfo("Log exportado", f"Salvo em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", str(e))


# ──────────────────────────────────────────────────────────
# Widget: barra de progresso com rótulo
# ──────────────────────────────────────────────────────────

class ProgressBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._label = ctk.CTkLabel(self, text="", font=("Segoe UI", 11),
                                   text_color=C["text_dim"])
        self._label.pack(anchor="w")
        self._bar = ctk.CTkProgressBar(self, height=8,
                                        progress_color=C["accent"],
                                        fg_color=C["border"])
        self._bar.pack(fill="x")
        self._bar.set(0)

    def update(self, done: int, total: int, label: str = ""):
        frac = done / total if total > 0 else 0
        self._bar.set(frac)
        text = label or (f"{done} / {total}  ({frac*100:.0f}%)" if total else "")
        self._label.configure(text=text)

    def reset(self):
        self._bar.set(0)
        self._label.configure(text="")


# ──────────────────────────────────────────────────────────
# Aba: Conversão Única
# ──────────────────────────────────────────────────────────

class SingleTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self._input_path = ""
        self._preview_img = None
        self._build()

    def _build(self):
        # ── Lado esquerdo: seleção e opções ──
        left = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=0)

        ctk.CTkLabel(left, text="IMAGEM DE ENTRADA",
                     font=("Segoe UI", 11, "bold"), text_color=C["accent"]).pack(anchor="w", padx=14, pady=(14, 4))

        # área de drag-and-drop / seleção
        self._drop_area = ctk.CTkFrame(left, fg_color=C["bg"], corner_radius=8, height=160)
        self._drop_area.pack(fill="x", padx=14, pady=4)
        self._drop_area.pack_propagate(False)

        self._preview_lbl = ctk.CTkLabel(self._drop_area, text="Arraste uma imagem aqui\nou clique para selecionar",
                                          font=("Segoe UI", 12), text_color=C["text_dim"])
        self._preview_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self._drop_area.bind("<Button-1>", lambda e: self._pick_file())
        self._preview_lbl.bind("<Button-1>", lambda e: self._pick_file())
        self._setup_dnd(self._drop_area)

        # caminho selecionado
        self._path_var = tk.StringVar(value="Nenhum arquivo selecionado")
        ctk.CTkLabel(left, textvariable=self._path_var, font=("Segoe UI", 10),
                     text_color=C["text_dim"], wraplength=320).pack(anchor="w", padx=14, pady=(2, 8))

        # ── Opções de conversão ──
        opt = ctk.CTkFrame(left, fg_color="transparent")
        opt.pack(fill="x", padx=14)

        ctk.CTkLabel(opt, text="Formato de saída:", font=("Segoe UI", 12),
                     text_color=C["text"]).grid(row=0, column=0, sticky="w", pady=4)
        self._fmt_var = tk.StringVar(value="WEBP")
        fmt_menu = ctk.CTkOptionMenu(opt, values=SUPPORTED_OUTPUT_FORMATS,
                                     variable=self._fmt_var,
                                     fg_color=C["border"], button_color=C["accent"],
                                     dropdown_fg_color=C["surface"],
                                     font=("Segoe UI", 12), width=120)
        fmt_menu.grid(row=0, column=1, sticky="e", padx=(8, 0), pady=4)

        ctk.CTkLabel(opt, text="Qualidade (qscale):", font=("Segoe UI", 12),
                     text_color=C["text"]).grid(row=1, column=0, sticky="w", pady=4)
        self._quality_var = tk.IntVar(value=60)
        q_frame = ctk.CTkFrame(opt, fg_color="transparent")
        q_frame.grid(row=1, column=1, sticky="e", padx=(8, 0))
        self._q_slider = ctk.CTkSlider(q_frame, from_=1, to=100,
                                        variable=self._quality_var,
                                        progress_color=C["accent"],
                                        button_color=C["accent"], width=90)
        self._q_slider.pack(side="left")
        ctk.CTkLabel(q_frame, textvariable=self._quality_var,
                     font=("Consolas", 12, "bold"), text_color=C["accent2"], width=32).pack(side="left", padx=4)

        ctk.CTkLabel(opt, text="CRF (AVIF):", font=("Segoe UI", 12),
                     text_color=C["text"]).grid(row=2, column=0, sticky="w", pady=4)
        self._crf_var = tk.IntVar(value=30)
        crf_frame = ctk.CTkFrame(opt, fg_color="transparent")
        crf_frame.grid(row=2, column=1, sticky="e", padx=(8, 0))
        ctk.CTkSlider(crf_frame, from_=0, to=63, variable=self._crf_var,
                       progress_color=C["warning"], button_color=C["warning"], width=90).pack(side="left")
        ctk.CTkLabel(crf_frame, textvariable=self._crf_var,
                     font=("Consolas", 12, "bold"), text_color=C["warning"], width=32).pack(side="left", padx=4)

        opt.columnconfigure(1, weight=1)

        # ── Pasta de saída ──
        out_frame = ctk.CTkFrame(left, fg_color="transparent")
        out_frame.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(out_frame, text="Pasta de saída:", font=("Segoe UI", 12),
                     text_color=C["text"]).pack(side="left")
        self._outdir_var = tk.StringVar(value="(mesma pasta do arquivo)")
        ctk.CTkEntry(out_frame, textvariable=self._outdir_var,
                     fg_color=C["bg"], border_color=C["border"],
                     font=("Segoe UI", 11), width=160).pack(side="left", padx=6, expand=True, fill="x")
        ctk.CTkButton(out_frame, text="…", width=32, height=28,
                       fg_color=C["border"], hover_color=C["accent"],
                       command=self._pick_outdir, font=("Segoe UI", 13)).pack(side="left")

        # ── Botão converter ──
        self._btn_convert = ctk.CTkButton(
            left, text="⚡  CONVERTER", height=44,
            font=("Segoe UI", 14, "bold"),
            fg_color=C["accent"], hover_color="#5550dd",
            corner_radius=10, command=self._start_conversion
        )
        self._btn_convert.pack(fill="x", padx=14, pady=(14, 8))

        # ── Resultado ──
        self._result_lbl = ctk.CTkLabel(left, text="", font=("Segoe UI", 11),
                                         text_color=C["success"])
        self._result_lbl.pack(padx=14, pady=(0, 14))

        # ── Lado direito: log ──
        self._log = LogPanel(self)
        self._log.pack(side="left", fill="both", expand=True, padx=(6, 0))

    def _setup_dnd(self, widget):
        """Tenta ativar drag-and-drop via tkinterdnd2 (opcional)."""
        try:
            import tkinterdnd2 as dnd
            widget.drop_target_register(dnd.DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass  # DnD desativado sem a lib

    def _on_drop(self, event):
        path = event.data.strip().strip("{}")
        if os.path.isfile(path):
            self._load_file(path)

    def _pick_file(self):
        path = filedialog.askopenfilename(filetypes=IMAGE_FILETYPES, title="Selecionar imagem")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._input_path = path
        name = Path(path).name
        size = human_size(os.path.getsize(path))
        self._path_var.set(f"{name}  ({size})")

        # atualizar pasta de saída se estiver vazia
        if self._outdir_var.get() == "(mesma pasta do arquivo)":
            pass  # deixa como está (usará mesma pasta)

        # preview
        if PIL_AVAILABLE:
            try:
                img = Image.open(path)
                img.thumbnail((280, 140), Image.LANCZOS)
                self._preview_img = ImageTk.PhotoImage(img)
                self._preview_lbl.configure(image=self._preview_img, text="")
            except Exception:
                self._preview_lbl.configure(image=None, text=name)
        else:
            self._preview_lbl.configure(text=name)

    def _pick_outdir(self):
        d = filedialog.askdirectory(title="Escolher pasta de saída")
        if d:
            self._outdir_var.set(d)

    def _start_conversion(self):
        if not self._input_path:
            messagebox.showwarning("Atenção", "Selecione uma imagem primeiro.")
            return

        outdir = self._outdir_var.get()
        if outdir == "(mesma pasta do arquivo)":
            outdir = str(Path(self._input_path).parent)

        fmt = self._fmt_var.get()
        out_path = output_filename(self._input_path, outdir, fmt)

        task = ConversionTask(
            input_path=self._input_path,
            output_path=out_path,
            format=fmt,
            quality=self._quality_var.get(),
            crf=self._crf_var.get(),
        )

        self._btn_convert.configure(state="disabled", text="⏳  Convertendo…")
        self._result_lbl.configure(text="")
        self._log.clear()
        self._log.append(f"→ Convertendo: {Path(self._input_path).name}", "info")

        def run():
            result = self.app.converter.convert_single(task, log_callback=lambda l: self._log.after(0, self._log.append, l))
            self.after(0, self._on_done, result)

        threading.Thread(target=run, daemon=True).start()

    def _on_done(self, result: ConversionResult):
        self._btn_convert.configure(state="normal", text="⚡  CONVERTER")
        if result.success:
            saved = result.size_saved_percent
            self._result_lbl.configure(
                text=f"✔ Concluído!  {human_size(result.original_size)} → {human_size(result.output_size)}  (economia: {format_percent(saved)})",
                text_color=C["success"],
            )
            self._log.append(f"✔ Sucesso! Salvo em: {result.task.output_path}", "ok")
            add_history_entry(self.app.config, {
                "type": "single",
                "input": result.task.input_path,
                "output": result.task.output_path,
                "format": result.task.format,
                "original_size": result.original_size,
                "output_size": result.output_size,
            })
        else:
            self._result_lbl.configure(text=f"✗ Erro: {result.error_message}", text_color=C["danger"])
            self._log.append(f"✗ Falha: {result.error_message}", "err")


# ──────────────────────────────────────────────────────────
# Aba: Conversão em Lote
# ──────────────────────────────────────────────────────────

class BatchTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self._files: list[str] = []
        self._running = False
        self._build()

    def _build(self):
        # ── Painel esquerdo: lista + opções ──
        left = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # cabeçalho da lista
        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(14, 4))
        ctk.CTkLabel(hdr, text="ARQUIVOS SELECIONADOS",
                     font=("Segoe UI", 11, "bold"), text_color=C["accent"]).pack(side="left")
        ctk.CTkButton(hdr, text="+ Adicionar", width=90, height=28,
                       font=("Segoe UI", 11), fg_color=C["border"], hover_color=C["accent"],
                       corner_radius=6, command=self._add_files).pack(side="right")
        ctk.CTkButton(hdr, text="✕ Limpar", width=80, height=28,
                       font=("Segoe UI", 11), fg_color=C["border"], hover_color=C["danger"],
                       corner_radius=6, command=self._clear_files).pack(side="right", padx=(0, 6))

        # lista de arquivos
        list_frame = ctk.CTkFrame(left, fg_color=C["bg"], corner_radius=8)
        list_frame.pack(fill="both", expand=True, padx=14, pady=4)

        self._listbox = tk.Listbox(
            list_frame, bg=C["bg"], fg=C["text"], selectbackground=C["accent"],
            font=("Consolas", 10), relief="flat", activestyle="none",
            selectmode="extended", bd=0, highlightthickness=0
        )
        sb = ctk.CTkScrollbar(list_frame, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True, padx=6, pady=6)

        self._count_lbl = ctk.CTkLabel(left, text="0 arquivos", font=("Segoe UI", 10),
                                        text_color=C["text_dim"])
        self._count_lbl.pack(anchor="w", padx=14, pady=(0, 6))

        # ── Opções ──
        opt = ctk.CTkFrame(left, fg_color=C["surface"], corner_radius=8)
        opt.pack(fill="x", padx=14, pady=4)

        def row(parent, label, widget_factory, r):
            ctk.CTkLabel(parent, text=label, font=("Segoe UI", 12),
                          text_color=C["text"]).grid(row=r, column=0, sticky="w", padx=12, pady=5)
            w = widget_factory(parent)
            w.grid(row=r, column=1, sticky="e", padx=12, pady=5)
            return w

        self._fmt_var = tk.StringVar(value="WEBP")
        row(opt, "Formato:", lambda p: ctk.CTkOptionMenu(
            p, values=SUPPORTED_OUTPUT_FORMATS, variable=self._fmt_var,
            fg_color=C["border"], button_color=C["accent"],
            dropdown_fg_color=C["surface"], font=("Segoe UI", 12), width=120
        ), 0)

        self._quality_var = tk.IntVar(value=60)
        def quality_widget(p):
            f = ctk.CTkFrame(p, fg_color="transparent")
            ctk.CTkSlider(f, from_=1, to=100, variable=self._quality_var,
                           progress_color=C["accent"], button_color=C["accent"], width=90).pack(side="left")
            ctk.CTkLabel(f, textvariable=self._quality_var,
                          font=("Consolas", 12, "bold"), text_color=C["accent2"], width=32).pack(side="left", padx=4)
            return f
        row(opt, "Qualidade:", quality_widget, 1)

        self._workers_var = tk.IntVar(value=2)
        row(opt, "Núcleos paralelos:", lambda p: ctk.CTkOptionMenu(
            p, values=["1", "2", "4", "8"], variable=self._workers_var,
            fg_color=C["border"], button_color=C["accent"],
            dropdown_fg_color=C["surface"], font=("Segoe UI", 12), width=80,
            command=lambda v: self._workers_var.set(int(v))
        ), 2)

        self._rename_var = tk.BooleanVar(value=False)
        row(opt, "Renomear (001, 002…):", lambda p: ctk.CTkSwitch(
            p, text="", variable=self._rename_var,
            progress_color=C["accent"], button_color=C["accent2"]
        ), 3)

        opt.columnconfigure(1, weight=1)

        # pasta de saída
        out_frame = ctk.CTkFrame(left, fg_color="transparent")
        out_frame.pack(fill="x", padx=14, pady=(6, 4))
        ctk.CTkLabel(out_frame, text="Pasta de saída:", font=("Segoe UI", 12),
                     text_color=C["text"]).pack(side="left")
        self._outdir_var = tk.StringVar(value="")
        ctk.CTkEntry(out_frame, textvariable=self._outdir_var,
                     fg_color=C["bg"], border_color=C["border"],
                     font=("Segoe UI", 11), width=150).pack(side="left", padx=6, expand=True, fill="x")
        ctk.CTkButton(out_frame, text="…", width=32, height=28,
                       fg_color=C["border"], hover_color=C["accent"],
                       command=self._pick_outdir, font=("Segoe UI", 13)).pack(side="left")

        # barra de progresso
        self._progress = ProgressBar(left)
        self._progress.pack(fill="x", padx=14, pady=(8, 4))

        # botões
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(4, 14))

        self._btn_start = ctk.CTkButton(
            btn_row, text="▶  CONVERTER LOTE", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color=C["accent"], hover_color="#5550dd",
            corner_radius=10, command=self._start_batch
        )
        self._btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._btn_cancel = ctk.CTkButton(
            btn_row, text="■ Cancelar", height=42, width=110,
            font=("Segoe UI", 13, "bold"),
            fg_color=C["border"], hover_color=C["danger"],
            corner_radius=10, command=self._cancel,
            state="disabled"
        )
        self._btn_cancel.pack(side="left")

        # ── Direito: log ──
        self._log = LogPanel(self)
        self._log.pack(side="left", fill="both", expand=True, padx=(6, 0))

    # ── callbacks ──────────────────────────────────────────

    def _add_files(self):
        paths = filedialog.askopenfilenames(filetypes=IMAGE_FILETYPES, title="Selecionar imagens")
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                self._listbox.insert("end", Path(p).name)
        self._count_lbl.configure(text=f"{len(self._files)} arquivo(s)")

    def _clear_files(self):
        self._files.clear()
        self._listbox.delete(0, "end")
        self._count_lbl.configure(text="0 arquivos")
        self._progress.reset()

    def _pick_outdir(self):
        d = filedialog.askdirectory(title="Pasta de saída")
        if d:
            self._outdir_var.set(d)

    def _start_batch(self):
        if not self._files:
            messagebox.showwarning("Atenção", "Adicione arquivos primeiro.")
            return

        outdir = self._outdir_var.get().strip()
        if not outdir:
            # usa pasta do primeiro arquivo como padrão
            outdir = str(Path(self._files[0]).parent)
            self._outdir_var.set(outdir)

        os.makedirs(outdir, exist_ok=True)
        fmt = self._fmt_var.get()
        quality = self._quality_var.get()
        rename = self._rename_var.get()

        tasks = [
            ConversionTask(
                input_path=f,
                output_path=output_filename(f, outdir, fmt, i + 1 if rename else None),
                format=fmt,
                quality=quality,
            )
            for i, f in enumerate(self._files)
        ]

        self._running = True
        self._btn_start.configure(state="disabled")
        self._btn_cancel.configure(state="normal")
        self._log.clear()
        self._progress.update(0, len(tasks), "Iniciando…")
        self._log.append(f"→ Iniciando lote: {len(tasks)} arquivo(s)", "info")

        def run():
            def on_progress(done, total, result):
                self.after(0, self._on_item_done, done, total, result)

            self.app.converter.convert_batch(tasks, progress_callback=on_progress,
                                              max_workers=self._workers_var.get())
            self.after(0, self._on_batch_done)

        threading.Thread(target=run, daemon=True).start()

    def _on_item_done(self, done: int, total: int, result: ConversionResult):
        name = Path(result.task.input_path).name
        if result.success:
            pct = format_percent(result.size_saved_percent)
            self._log.append(f"✔ {name}  ({human_size(result.original_size)} → {human_size(result.output_size)}, -{pct})", "ok")
        else:
            self._log.append(f"✗ {name}: {result.error_message}", "err")
        self._progress.update(done, total, f"Convertendo… {done}/{total}")

    def _on_batch_done(self):
        self._running = False
        self._btn_start.configure(state="normal")
        self._btn_cancel.configure(state="disabled")
        self._log.append("✔ Lote concluído!", "ok")
        messagebox.showinfo("Concluído", "Conversão em lote finalizada!")

    def _cancel(self):
        self.app.converter.cancel()
        self._log.append("⚠ Cancelamento solicitado…", "err")
        self._btn_cancel.configure(state="disabled")


# ──────────────────────────────────────────────────────────
# Aba: Configurações
# ──────────────────────────────────────────────────────────

class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10)
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="CONFIGURAÇÕES", font=("Segoe UI", 13, "bold"),
                     text_color=C["accent"]).pack(anchor="w", padx=20, pady=(18, 12))

        # FFmpeg path
        ff_frame = ctk.CTkFrame(card, fg_color=C["surface"], corner_radius=8)
        ff_frame.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(ff_frame, text="Caminho do FFmpeg", font=("Segoe UI", 12, "bold"),
                     text_color=C["text"]).pack(anchor="w", padx=14, pady=(12, 4))

        row = ctk.CTkFrame(ff_frame, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))
        self._ff_var = tk.StringVar(value=self.app.config.get("ffmpeg_path", ""))
        ctk.CTkEntry(row, textvariable=self._ff_var, fg_color=C["bg"],
                     border_color=C["border"], font=("Segoe UI", 11)).pack(side="left", expand=True, fill="x")
        ctk.CTkButton(row, text="…", width=36, height=30, fg_color=C["border"],
                       hover_color=C["accent"], command=self._pick_ffmpeg).pack(side="left", padx=(6, 0))

        ctk.CTkButton(card, text="✔  Verificar e Salvar", height=40,
                       font=("Segoe UI", 13, "bold"),
                       fg_color=C["accent"], hover_color="#5550dd", corner_radius=8,
                       command=self._save).pack(padx=20, pady=10, anchor="w")

        self._status_lbl = ctk.CTkLabel(card, text="", font=("Segoe UI", 11),
                                         text_color=C["success"])
        self._status_lbl.pack(anchor="w", padx=20)

        # Detector automático
        ctk.CTkButton(card, text="🔍  Detectar FFmpeg automaticamente", height=36,
                       font=("Segoe UI", 12), fg_color=C["border"], hover_color=C["accent"],
                       corner_radius=8, command=self._auto_detect).pack(padx=20, pady=(6, 0), anchor="w")

        # Histórico
        ctk.CTkLabel(card, text="HISTÓRICO", font=("Segoe UI", 13, "bold"),
                     text_color=C["accent"]).pack(anchor="w", padx=20, pady=(24, 8))

        hist_frame = ctk.CTkScrollableFrame(card, fg_color=C["bg"], corner_radius=8, height=200)
        hist_frame.pack(fill="x", padx=20, pady=(0, 14))
        self._hist_frame = hist_frame
        self._refresh_history()

        ctk.CTkButton(card, text="🗑  Limpar histórico", height=32,
                       font=("Segoe UI", 11), fg_color=C["border"], hover_color=C["danger"],
                       corner_radius=6, command=self._clear_history).pack(padx=20, anchor="w")

    def _pick_ffmpeg(self):
        path = filedialog.askopenfilename(
            filetypes=[("Executável", "*.exe"), ("Todos", "*.*")],
            title="Localizar ffmpeg.exe"
        )
        if path:
            self._ff_var.set(path)

    def _auto_detect(self):
        found = find_ffmpeg()
        if found:
            self._ff_var.set(found)
            self._status_lbl.configure(text=f"✔ Encontrado: {found}", text_color=C["success"])
        else:
            self._status_lbl.configure(text="✗ FFmpeg não encontrado automaticamente.", text_color=C["danger"])

    def _save(self):
        path = self._ff_var.get().strip()
        self.app.converter.ffmpeg_path = path or "ffmpeg"
        self.app.config["ffmpeg_path"] = path
        save_config(self.app.config)

        ok, msg = self.app.converter.check_ffmpeg()
        if ok:
            self._status_lbl.configure(text=f"✔ {msg}", text_color=C["success"])
            self.app.update_ffmpeg_status(ok, msg)
        else:
            self._status_lbl.configure(text=f"✗ {msg}", text_color=C["danger"])
            self.app.update_ffmpeg_status(ok, msg)

    def _refresh_history(self):
        for w in self._hist_frame.winfo_children():
            w.destroy()
        history = self.app.config.get("conversion_history", [])
        if not history:
            ctk.CTkLabel(self._hist_frame, text="Nenhuma conversão registrada.",
                          font=("Segoe UI", 11), text_color=C["text_dim"]).pack(padx=10, pady=10)
            return
        for entry in reversed(history[-50:]):
            ts = entry.get("timestamp", "")
            inp = Path(entry.get("input", "")).name
            fmt = entry.get("format", "")
            orig = human_size(entry.get("original_size", 0))
            out = human_size(entry.get("output_size", 0))
            ctk.CTkLabel(self._hist_frame,
                          text=f"{ts[:16]}  {inp} → {fmt}  ({orig} → {out})",
                          font=("Consolas", 10), text_color=C["text_dim"],
                          anchor="w").pack(fill="x", padx=8, pady=1)

    def _clear_history(self):
        if messagebox.askyesno("Limpar histórico", "Deseja apagar todo o histórico?"):
            self.app.config["conversion_history"] = []
            save_config(self.app.config)
            self._refresh_history()


# ──────────────────────────────────────────────────────────
# Janela principal
# ──────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FFImg Converter")
        self.geometry("1060x720")
        self.minsize(900, 640)
        self.configure(fg_color=C["bg"])

        self.config = load_config()
        ffmpeg_path = self.config.get("ffmpeg_path") or find_ffmpeg() or "ffmpeg"
        self.converter = FFmpegConverter(ffmpeg_path)

        self._build()
        self.after(300, self._check_ffmpeg_on_start)

    # ── Layout ─────────────────────────────────────────────

    def _build(self):
        # ── Barra de título ──
        title_bar = ctk.CTkFrame(self, fg_color=C["surface"], height=56, corner_radius=0)
        title_bar.pack(fill="x", side="top")
        title_bar.pack_propagate(False)

        ctk.CTkLabel(title_bar, text="⚡ FFImg Converter",
                     font=("Segoe UI", 18, "bold"), text_color=C["accent"]).pack(side="left", padx=20)

        self._ff_status_lbl = ctk.CTkLabel(title_bar, text="",
                                            font=("Segoe UI", 11), text_color=C["text_dim"])
        self._ff_status_lbl.pack(side="right", padx=20)

        # ── Tabs ──
        self._tabs = ctk.CTkTabview(self, fg_color=C["surface"],
                                     segmented_button_fg_color=C["card"],
                                     segmented_button_selected_color=C["accent"],
                                     segmented_button_selected_hover_color="#5550dd",
                                     segmented_button_unselected_color=C["card"],
                                     segmented_button_unselected_hover_color=C["border"],
                                     text_color=C["text"],
                                     corner_radius=10)
        self._tabs.pack(fill="both", expand=True, padx=14, pady=(8, 14))

        for name in ("Imagem Única", "Lote", "Configurações"):
            self._tabs.add(name)

        SingleTab(self._tabs.tab("Imagem Única"), self).pack(fill="both", expand=True)
        BatchTab(self._tabs.tab("Lote"), self).pack(fill="both", expand=True)
        SettingsTab(self._tabs.tab("Configurações"), self).pack(fill="both", expand=True)

    # ── Status bar ─────────────────────────────────────────

    def update_ffmpeg_status(self, ok: bool, msg: str):
        short = msg[:60] + "…" if len(msg) > 60 else msg
        color = C["success"] if ok else C["danger"]
        icon = "✔" if ok else "✗"
        self._ff_status_lbl.configure(text=f"{icon} {short}", text_color=color)

    def _check_ffmpeg_on_start(self):
        ok, msg = self.converter.check_ffmpeg()
        self.update_ffmpeg_status(ok, msg)
        if not ok:
            messagebox.showwarning(
                "FFmpeg não encontrado",
                "O FFmpeg não foi localizado.\n\n"
                "Vá em Configurações para indicar o caminho correto,\n"
                "ou instale o FFmpeg e adicione-o ao PATH do sistema.\n\n"
                "Download: https://ffmpeg.org/download.html"
            )
