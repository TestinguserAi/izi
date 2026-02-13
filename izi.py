"""
izi — Transcritor de Vídeo Local usando Whisper
Aplicação minimalista com interface gráfica para transcrever vídeos em texto.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import queue
import shutil
import os
import sys
import time

# ─── Verificar dependências ─────────────────────────────────────

WHISPER_AVAILABLE = False
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    pass

SUPPORTED_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv')
MODELS = ['tiny', 'base', 'small', 'medium', 'large']


def check_dependencies():
    """Verifica se whisper e ffmpeg estão instalados."""
    errors = []
    if not WHISPER_AVAILABLE:
        errors.append("openai-whisper não está instalado.\n  → Rode: pip install openai-whisper")
    if not shutil.which("ffmpeg"):
        errors.append("ffmpeg não encontrado no sistema.\n  → Linux: sudo apt install ffmpeg\n  → Mac: brew install ffmpeg\n  → Windows: https://ffmpeg.org/download.html")
    return errors


# ─── Cores ───────────────────────────────────────────────────────

BG = '#1a1b2e'
BG_CARD = '#232540'
BG_INPUT = '#2a2d4a'
ACCENT = '#6c63ff'
ACCENT_HOVER = '#5a52e0'
SUCCESS = '#4ade80'
WARNING = '#fbbf24'
ERROR = '#f87171'
TEXT = '#e2e8f0'
TEXT_DIM = '#94a3b8'
TEXT_BRIGHT = '#ffffff'
BORDER = '#3d4066'


# ─── Aplicação ───────────────────────────────────────────────────

class TranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("izi — Transcritor de Vídeo")
        self.root.configure(bg=BG)
        self.root.minsize(560, 520)

        # Centralizar janela
        w, h = 560, 520
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Estado
        self.files = []
        self.is_processing = False
        self.loaded_model = None
        self.loaded_model_name = None
        self.msg_queue = queue.Queue()

        self._build_ui()
        self._poll_messages()

    def _build_ui(self):
        container = tk.Frame(self.root, bg=BG, padx=24, pady=16)
        container.pack(fill="both", expand=True)

        # ── Título ──
        tk.Label(
            container, text="izi", font=("Segoe UI", 20, "bold"),
            fg=TEXT_BRIGHT, bg=BG,
        ).pack(anchor="w")
        tk.Label(
            container, text="Transcrição de vídeo com Whisper",
            font=("Segoe UI", 10), fg=TEXT_DIM, bg=BG,
        ).pack(anchor="w", pady=(0, 12))

        # ── Caixa de Arquivos ──
        file_frame = tk.Frame(container, bg=BG_CARD, padx=16, pady=12,
                              highlightbackground=BORDER, highlightthickness=1)
        file_frame.pack(fill="x", pady=(0, 10))

        header = tk.Frame(file_frame, bg=BG_CARD)
        header.pack(fill="x", pady=(0, 8))
        tk.Label(header, text="Vídeos", font=("Segoe UI", 11, "bold"),
                 fg=TEXT, bg=BG_CARD).pack(side="left")
        self.lbl_count = tk.Label(header, text="0 arquivos", font=("Segoe UI", 9),
                                  fg=TEXT_DIM, bg=BG_CARD)
        self.lbl_count.pack(side="right")

        list_frame = tk.Frame(file_frame, bg=BG_INPUT,
                              highlightbackground=BORDER, highlightthickness=1)
        list_frame.pack(fill="x", pady=(0, 8))
        self.file_listbox = tk.Listbox(
            list_frame, height=6, bg=BG_INPUT, fg=TEXT, font=("Consolas", 9),
            selectbackground=ACCENT, selectforeground=TEXT_BRIGHT,
            borderwidth=0, highlightthickness=0, activestyle="none",
        )
        self.file_listbox.pack(fill="x", padx=4, pady=4)

        btn_row = tk.Frame(file_frame, bg=BG_CARD)
        btn_row.pack(fill="x")
        self._make_btn(btn_row, "Adicionar Vídeos", self._add_files).pack(side="left", padx=(0, 6))
        self._make_btn(btn_row, "Limpar", self._clear_files).pack(side="left")

        # ── Configurações (linha compacta) ──
        config_frame = tk.Frame(container, bg=BG_CARD, padx=16, pady=12,
                                highlightbackground=BORDER, highlightthickness=1)
        config_frame.pack(fill="x", pady=(0, 10))

        row = tk.Frame(config_frame, bg=BG_CARD)
        row.pack(fill="x")

        # Modelo
        tk.Label(row, text="Modelo:", font=("Segoe UI", 9), fg=TEXT_DIM,
                 bg=BG_CARD).pack(side="left")
        self.model_var = tk.StringVar(value="base")
        model_menu = ttk.Combobox(row, textvariable=self.model_var, values=MODELS,
                                  state="readonly", font=("Segoe UI", 10), width=8)
        model_menu.pack(side="left", padx=(4, 16))

        # Pasta de saída
        tk.Label(row, text="Saída:", font=("Segoe UI", 9), fg=TEXT_DIM,
                 bg=BG_CARD).pack(side="left")
        self.output_dir = os.path.join(os.path.expanduser("~"), "Transcricoes")
        self.lbl_output = tk.Label(row, text=self._short_path(self.output_dir),
                                   font=("Consolas", 9), fg=TEXT, bg=BG_CARD)
        self.lbl_output.pack(side="left", padx=(4, 8))
        self._make_btn(row, "Alterar", self._pick_output_dir).pack(side="left")

        # ── Progresso ──
        prog_frame = tk.Frame(container, bg=BG_CARD, padx=16, pady=12,
                              highlightbackground=BORDER, highlightthickness=1)
        prog_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.lbl_status = tk.Label(prog_frame, text="Pronto", font=("Segoe UI", 10),
                                   fg=TEXT_DIM, bg=BG_CARD)
        self.lbl_status.pack(anchor="w", pady=(0, 4))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("izi.Horizontal.TProgressbar", troughcolor=BG_INPUT,
                        background=ACCENT, borderwidth=0)
        self.progress = ttk.Progressbar(prog_frame, style="izi.Horizontal.TProgressbar",
                                        mode="determinate")
        self.progress.pack(fill="x", pady=(0, 6))

        log_frame = tk.Frame(prog_frame, bg=BG_INPUT,
                             highlightbackground=BORDER, highlightthickness=1)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            log_frame, height=5, bg=BG_INPUT, fg=TEXT, font=("Consolas", 9),
            borderwidth=0, highlightthickness=0, wrap="word", state="disabled",
        )
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # ── Botão Iniciar ──
        self.btn_start = tk.Button(
            container, text="INICIAR TRANSCRIÇÃO", font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg=TEXT_BRIGHT, activebackground=ACCENT_HOVER,
            activeforeground=TEXT_BRIGHT, borderwidth=0, cursor="hand2",
            command=self._start_transcription,
        )
        self.btn_start.pack(fill="x", ipady=10)

    # ─── Helpers de UI ───────────────────────────────────────────

    def _make_btn(self, parent, text, command):
        return tk.Button(
            parent, text=text, font=("Segoe UI", 9), bg=BG_INPUT, fg=TEXT,
            activebackground=BORDER, activeforeground=TEXT_BRIGHT,
            borderwidth=0, cursor="hand2", padx=12, pady=4, command=command,
        )

    def _short_path(self, path):
        home = os.path.expanduser("~")
        if path.startswith(home):
            return "~" + path[len(home):]
        return path

    def _log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_count(self):
        n = len(self.files)
        self.lbl_count.configure(text=f"{n} arquivo(s)" if n else "0 arquivos")

    # ─── Ações de arquivo ────────────────────────────────────────

    def _add_files(self):
        filetypes = [
            ("Vídeos", " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)),
            ("Todos os arquivos", "*.*"),
        ]
        selected = filedialog.askopenfilenames(title="Selecionar vídeos", filetypes=filetypes)
        if selected:
            added = 0
            for f in selected:
                if f not in self.files:
                    self.files.append(f)
                    self.file_listbox.insert("end", f"  {os.path.basename(f)}")
                    added += 1
            self._update_count()
            if added:
                self._log(f"+ {added} vídeo(s) adicionado(s)")

    def _clear_files(self):
        self.files.clear()
        self.file_listbox.delete(0, "end")
        self._update_count()

    def _pick_output_dir(self):
        folder = filedialog.askdirectory(title="Pasta de saída")
        if folder:
            self.output_dir = folder
            self.lbl_output.configure(text=self._short_path(folder))

    # ─── Thread-safe message polling ─────────────────────────────

    def _poll_messages(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self._handle_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_messages)

    def _handle_message(self, msg):
        action = msg.get("action")
        if action == "log":
            self._log(msg["text"])
        elif action == "status":
            self.lbl_status.configure(text=msg["text"], fg=msg.get("color", TEXT_DIM))
        elif action == "progress":
            self.progress["value"] = msg["value"]
        elif action == "done":
            self.is_processing = False
            self.btn_start.configure(state="normal")
            output = msg.get("output_dir", self.output_dir)
            self._ask_open_folder(output)

    def _ask_open_folder(self, folder):
        resp = messagebox.askyesno(
            "Transcrição Concluída",
            f"Transcrições salvas em:\n{folder}\n\nDeseja abrir a pasta?",
        )
        if resp:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}"')

    # ─── Transcrição ─────────────────────────────────────────────

    def _start_transcription(self):
        if self.is_processing:
            return
        if not self.files:
            messagebox.showwarning("Aviso", "Adicione pelo menos um vídeo.")
            return

        errors = check_dependencies()
        if errors:
            messagebox.showerror("Dependências", "\n\n".join(errors))
            return

        self.is_processing = True
        self.btn_start.configure(state="disabled")

        # Snapshot de estado para a thread
        files = list(self.files)
        model_name = self.model_var.get()
        output_dir = self.output_dir

        thread = threading.Thread(
            target=self._transcribe_worker,
            args=(files, model_name, output_dir),
            daemon=True,
        )
        thread.start()

    def _transcribe_worker(self, files, model_name, output_dir):
        """Executa em thread separada. Processa vídeos um a um."""
        q = self.msg_queue
        os.makedirs(output_dir, exist_ok=True)

        # Carregar modelo
        if self.loaded_model is None or self.loaded_model_name != model_name:
            q.put({"action": "status", "text": f"Carregando modelo '{model_name}'...", "color": WARNING})
            q.put({"action": "log", "text": f"Carregando modelo '{model_name}'..."})
            try:
                self.loaded_model = whisper.load_model(model_name)
                self.loaded_model_name = model_name
                q.put({"action": "log", "text": f"Modelo '{model_name}' pronto."})
            except Exception as e:
                q.put({"action": "log", "text": f"Erro ao carregar modelo: {e}"})
                q.put({"action": "status", "text": "Erro ao carregar modelo", "color": ERROR})
                q.put({"action": "done", "output_dir": output_dir})
                return

        model = self.loaded_model
        total = len(files)
        self.progress["maximum"] = total
        successes = 0
        t_start = time.time()

        for i, filepath in enumerate(files, 1):
            name = os.path.basename(filepath)
            q.put({"action": "status", "text": f"[{i}/{total}] {name}", "color": ACCENT})
            q.put({"action": "log", "text": f"[{i}/{total}] {name}"})

            try:
                result = model.transcribe(filepath)
                text = result["text"].strip()

                out_name = os.path.splitext(name)[0] + ".txt"
                out_path = os.path.join(output_dir, out_name)

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)

                elapsed = time.time() - t_start
                q.put({"action": "log", "text": f"  -> {out_name}"})
                successes += 1
            except Exception as e:
                q.put({"action": "log", "text": f"  ERRO: {e}"})

            q.put({"action": "progress", "value": i})

        # Resumo
        elapsed = time.time() - t_start
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        q.put({"action": "log", "text": f"\nConcluído: {successes}/{total} em {mins}min {secs}s"})
        q.put({"action": "log", "text": f"Pasta: {output_dir}"})
        q.put({"action": "status", "text": f"Concluído! {successes}/{total}", "color": SUCCESS})
        q.put({"action": "done", "output_dir": output_dir})


# ─── Main ────────────────────────────────────────────────────────

def main():
    errors = check_dependencies()
    if errors:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Dependências Faltando", "\n\n".join(errors))
        root.destroy()
        return

    root = tk.Tk()
    TranscriberApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
