"""
main.py - Ponto de entrada do FFImg Converter
"""

import sys
import os

# Garante que o diretório do script esteja no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # Tenta usar tkinterdnd2 como base para suporte a DnD
    try:
        import tkinterdnd2 as dnd
        # Substitui o CTk._windows_set_titlebar_icon para evitar erro no DnD
        root_class = dnd.TkinterDnD.Tk
    except ImportError:
        root_class = None

    from gui import App

    if root_class is not None:
        # Patch: injeta DnD no CustomTkinter
        try:
            import customtkinter as ctk
            _original_init = ctk.CTk.__init__

            def _patched_init(self_ctk, *args, **kwargs):
                _original_init(self_ctk, *args, **kwargs)
                try:
                    dnd.TkinterDnD._require(self_ctk)
                except Exception:
                    pass

            ctk.CTk.__init__ = _patched_init
        except Exception:
            pass

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
