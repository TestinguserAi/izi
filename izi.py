"""
izi — Transcritor de Vídeo Local usando Whisper
Interface web minimalista. Rode: python izi.py → abre no navegador.
"""

import os
import sys
import shutil
import threading
import time
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, request, jsonify, send_file, Response

# ─── Verificar dependências ─────────────────────────────────────

WHISPER_AVAILABLE = False
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    pass

SUPPORTED_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv'}
MODELS = ['tiny', 'base', 'small', 'medium', 'large']

UPLOAD_DIR = os.path.join(os.path.expanduser("~"), ".izi_uploads")
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Transcricoes")


def check_dependencies():
    errors = []
    if not WHISPER_AVAILABLE:
        errors.append("openai-whisper não está instalado. Rode: pip install openai-whisper")
    return errors


# ─── Estado global da transcrição ────────────────────────────────

state = {
    "files": [],           # lista de {"id": str, "name": str, "path": str}
    "is_processing": False,
    "progress": [],        # log de mensagens
    "current": 0,
    "total": 0,
    "status": "idle",      # idle | processing | done | error
    "results": [],         # lista de {"name": str, "filename": str}
}
state_lock = threading.Lock()

loaded_model = None
loaded_model_name = None


def add_log(msg):
    with state_lock:
        state["progress"].append(msg)


# ─── Flask app ───────────────────────────────────────────────────

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024  # 4GB


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/upload", methods=["POST"])
def upload():
    if "files" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    uploaded = []

    for f in request.files.getlist("files"):
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        file_id = uuid.uuid4().hex[:8]
        safe_name = f.filename
        save_path = os.path.join(UPLOAD_DIR, f"{file_id}_{safe_name}")
        f.save(save_path)
        entry = {"id": file_id, "name": safe_name, "path": save_path}
        uploaded.append(entry)

    with state_lock:
        state["files"].extend(uploaded)

    return jsonify({"uploaded": [{"id": e["id"], "name": e["name"]} for e in uploaded]})


@app.route("/remove/<file_id>", methods=["DELETE"])
def remove_file(file_id):
    with state_lock:
        found = None
        for f in state["files"]:
            if f["id"] == file_id:
                found = f
                break
        if found:
            state["files"].remove(found)
            try:
                os.remove(found["path"])
            except OSError:
                pass
    return jsonify({"ok": True})


@app.route("/clear", methods=["POST"])
def clear_files():
    with state_lock:
        for f in state["files"]:
            try:
                os.remove(f["path"])
            except OSError:
                pass
        state["files"].clear()
    return jsonify({"ok": True})


@app.route("/transcribe", methods=["POST"])
def transcribe():
    with state_lock:
        if state["is_processing"]:
            return jsonify({"error": "Já em processamento"}), 409
        if not state["files"]:
            return jsonify({"error": "Nenhum arquivo adicionado"}), 400

    data = request.get_json(silent=True) or {}
    model_name = data.get("model", "base")
    if model_name not in MODELS:
        model_name = "base"

    errors = check_dependencies()
    if errors:
        return jsonify({"error": "\n".join(errors)}), 500

    with state_lock:
        state["is_processing"] = True
        state["status"] = "processing"
        state["progress"] = []
        state["results"] = []
        state["current"] = 0
        state["total"] = len(state["files"])
        files_snapshot = list(state["files"])

    thread = threading.Thread(
        target=transcribe_worker,
        args=(files_snapshot, model_name),
        daemon=True,
    )
    thread.start()
    return jsonify({"started": True, "total": len(files_snapshot)})


@app.route("/status")
def get_status():
    with state_lock:
        return jsonify({
            "status": state["status"],
            "current": state["current"],
            "total": state["total"],
            "progress": list(state["progress"]),
            "results": list(state["results"]),
            "files": [{"id": f["id"], "name": f["name"]} for f in state["files"]],
        })


@app.route("/download/<filename>")
def download(filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(filepath):
        return jsonify({"error": "Arquivo não encontrado"}), 404
    return send_file(filepath, as_attachment=True)


# ─── Worker de transcrição ───────────────────────────────────────

def transcribe_worker(files, model_name):
    global loaded_model, loaded_model_name

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Carregar modelo
    if loaded_model is None or loaded_model_name != model_name:
        add_log(f"⏳ Carregando modelo '{model_name}'...")
        try:
            loaded_model = whisper.load_model(model_name)
            loaded_model_name = model_name
            add_log(f"✅ Modelo '{model_name}' pronto.")
        except Exception as e:
            add_log(f"❌ Erro ao carregar modelo: {e}")
            with state_lock:
                state["is_processing"] = False
                state["status"] = "error"
            return

    model = loaded_model
    total = len(files)
    successes = 0
    t_start = time.time()

    for i, file_info in enumerate(files, 1):
        name = file_info["name"]
        filepath = file_info["path"]

        with state_lock:
            state["current"] = i

        add_log(f"🎬 [{i}/{total}] Transcrevendo: {name}")

        try:
            result = model.transcribe(filepath)
            text = result["text"].strip()

            out_name = os.path.splitext(name)[0] + ".txt"
            out_path = os.path.join(OUTPUT_DIR, out_name)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)

            add_log(f"   ✅ Salvo: {out_name}")
            with state_lock:
                state["results"].append({"name": name, "filename": out_name})
            successes += 1
        except Exception as e:
            add_log(f"   ❌ Erro: {e}")

    # Limpar uploads
    for file_info in files:
        try:
            os.remove(file_info["path"])
        except OSError:
            pass

    elapsed = time.time() - t_start
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    add_log(f"\n🏁 Concluído: {successes}/{total} em {mins}min {secs}s")
    add_log(f"📁 Pasta: {OUTPUT_DIR}")

    with state_lock:
        state["is_processing"] = False
        state["status"] = "done"
        state["files"].clear()


# ─── HTML da interface ───────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>izi</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #1a1b2e;
    color: #e2e8f0;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    padding: 40px 20px;
  }
  .container { width: 100%; max-width: 640px; }

  h1 { font-size: 2rem; color: #fff; margin-bottom: 2px; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }

  .card {
    background: #232540;
    border: 1px solid #3d4066;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
  }
  .card-title {
    font-size: 0.85rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 12px;
  }

  .dropzone {
    border: 2px dashed #3d4066;
    border-radius: 10px;
    padding: 40px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
  }
  .dropzone:hover, .dropzone.dragover {
    border-color: #6c63ff;
    background: rgba(108,99,255,0.08);
  }
  .dropzone-icon { font-size: 2.5rem; margin-bottom: 8px; }
  .dropzone-text { color: #94a3b8; font-size: 0.9rem; }
  .dropzone-text strong { color: #6c63ff; }

  .file-list { margin-top: 12px; }
  .file-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: #2a2d4a;
    border-radius: 8px;
    margin-bottom: 6px;
    font-size: 0.85rem;
  }
  .file-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file-item .remove {
    background: none; border: none; color: #f87171; cursor: pointer;
    font-size: 1.1rem; padding: 0 4px; margin-left: 8px;
  }
  .file-item .remove:hover { color: #ff4444; }

  .config-row {
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  .config-row label { color: #94a3b8; font-size: 0.85rem; }
  .config-row select {
    background: #2a2d4a; color: #e2e8f0; border: 1px solid #3d4066;
    border-radius: 6px; padding: 6px 12px; font-size: 0.9rem; cursor: pointer;
  }
  .output-path { font-family: 'Consolas', monospace; font-size: 0.8rem; color: #94a3b8; }

  .btn-start {
    width: 100%; padding: 14px; background: #6c63ff; color: #fff;
    border: none; border-radius: 10px; font-size: 1rem; font-weight: 700;
    cursor: pointer; transition: background 0.2s; letter-spacing: 0.02em;
  }
  .btn-start:hover { background: #5a52e0; }
  .btn-start:disabled { background: #3d4066; cursor: not-allowed; }

  .btn-clear {
    background: none; border: 1px solid #3d4066; color: #94a3b8;
    padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.8rem;
  }
  .btn-clear:hover { border-color: #f87171; color: #f87171; }

  .progress-bar-bg {
    width: 100%; height: 8px; background: #2a2d4a;
    border-radius: 4px; overflow: hidden; margin-bottom: 12px;
  }
  .progress-bar-fill {
    height: 100%; background: #6c63ff; border-radius: 4px;
    transition: width 0.3s; width: 0%;
  }
  .status-text { font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px; }

  .log {
    background: #1a1b2e; border: 1px solid #3d4066; border-radius: 8px;
    padding: 12px; font-family: 'Consolas', monospace; font-size: 0.8rem;
    max-height: 240px; overflow-y: auto; white-space: pre-wrap;
    line-height: 1.5; color: #94a3b8;
  }

  .results { margin-top: 12px; }
  .result-item {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 12px; background: #2a2d4a; border-radius: 8px; margin-bottom: 6px;
  }
  .result-item .name { font-size: 0.85rem; }
  .result-item a {
    color: #6c63ff; text-decoration: none; font-size: 0.85rem; font-weight: 600;
  }
  .result-item a:hover { color: #5a52e0; }

  .hidden { display: none; }
</style>
</head>
<body>
<div class="container">
  <h1>izi</h1>
  <p class="subtitle">Transcricao de video local com Whisper</p>

  <div class="card">
    <div class="card-title">Videos</div>
    <div class="dropzone" id="dropzone">
      <div class="dropzone-icon">&#128194;</div>
      <div class="dropzone-text">Arraste videos aqui ou <strong>clique para selecionar</strong></div>
    </div>
    <input type="file" id="fileInput" multiple accept=".mp4,.mkv,.avi,.mov,.webm,.m4v,.mpg,.mpeg,.wmv,.flv" style="display:none">
    <div class="file-list" id="fileList"></div>
    <div style="margin-top:8px; text-align:right;">
      <button class="btn-clear hidden" id="btnClear">Limpar tudo</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Configuracoes</div>
    <div class="config-row">
      <label>Modelo Whisper:</label>
      <select id="modelSelect">
        <option value="tiny">tiny (rapido, menos preciso)</option>
        <option value="base" selected>base (equilibrado)</option>
        <option value="small">small (boa qualidade)</option>
        <option value="medium">medium (alta qualidade)</option>
        <option value="large">large (maxima qualidade)</option>
      </select>
    </div>
    <div style="margin-top:8px;">
      <span class="output-path">&#128193; Saida: ~/Transcricoes</span>
    </div>
  </div>

  <button class="btn-start" id="btnStart">INICIAR TRANSCRICAO</button>

  <div class="card hidden" id="progressCard" style="margin-top:16px;">
    <div class="card-title">Progresso</div>
    <div class="status-text" id="statusText">Aguardando...</div>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" id="progressBar"></div>
    </div>
    <div class="log" id="logArea"></div>
    <div class="results" id="resultsArea"></div>
  </div>
</div>

<script>
(function() {
  "use strict";

  var fileInput = document.getElementById("fileInput");
  var dropzone = document.getElementById("dropzone");
  var fileList = document.getElementById("fileList");
  var btnClear = document.getElementById("btnClear");
  var btnStart = document.getElementById("btnStart");
  var progressCard = document.getElementById("progressCard");
  var progressBar = document.getElementById("progressBar");
  var statusText = document.getElementById("statusText");
  var logArea = document.getElementById("logArea");
  var resultsArea = document.getElementById("resultsArea");
  var modelSelect = document.getElementById("modelSelect");

  var pollInterval = null;
  var lastLogLen = 0;

  // ── Clique na dropzone abre seletor de arquivo ──
  dropzone.addEventListener("click", function() {
    fileInput.click();
  });

  // ── Drag and drop ──
  dropzone.addEventListener("dragover", function(e) {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", function() {
    dropzone.classList.remove("dragover");
  });
  dropzone.addEventListener("drop", function(e) {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  });

  // ── Seletor de arquivo ──
  fileInput.addEventListener("change", function() {
    if (fileInput.files.length) uploadFiles(fileInput.files);
    fileInput.value = "";
  });

  // ── Botao limpar ──
  btnClear.addEventListener("click", function() {
    fetch("/clear", { method: "POST" }).then(function() {
      fileList.innerHTML = "";
      btnClear.classList.add("hidden");
    });
  });

  // ── Botao iniciar ──
  btnStart.addEventListener("click", function() {
    startTranscription();
  });

  // ── Upload de arquivos ──
  function uploadFiles(files) {
    var form = new FormData();
    for (var i = 0; i < files.length; i++) {
      form.append("files", files[i]);
    }

    btnStart.disabled = true;
    btnStart.textContent = "ENVIANDO...";

    fetch("/upload", { method: "POST", body: form })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.uploaded) {
          for (var i = 0; i < data.uploaded.length; i++) {
            addFileToList(data.uploaded[i].id, data.uploaded[i].name);
          }
        }
        btnStart.disabled = false;
        btnStart.textContent = "INICIAR TRANSCRICAO";
      })
      .catch(function(e) {
        alert("Erro ao enviar: " + e.message);
        btnStart.disabled = false;
        btnStart.textContent = "INICIAR TRANSCRICAO";
      });
  }

  function addFileToList(id, name) {
    var div = document.createElement("div");
    div.className = "file-item";
    div.id = "file-" + id;

    var span = document.createElement("span");
    span.className = "name";
    span.textContent = name;

    var btn = document.createElement("button");
    btn.className = "remove";
    btn.innerHTML = "&times;";
    btn.addEventListener("click", function() {
      fetch("/remove/" + id, { method: "DELETE" }).then(function() {
        div.remove();
        if (!fileList.children.length) btnClear.classList.add("hidden");
      });
    });

    div.appendChild(span);
    div.appendChild(btn);
    fileList.appendChild(div);
    btnClear.classList.remove("hidden");
  }

  // ── Transcricao ──
  function startTranscription() {
    var model = modelSelect.value;

    btnStart.disabled = true;
    btnStart.textContent = "PROCESSANDO...";
    progressCard.classList.remove("hidden");
    logArea.textContent = "";
    resultsArea.innerHTML = "";
    lastLogLen = 0;
    statusText.textContent = "Iniciando...";
    progressBar.style.width = "0%";

    fetch("/transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: model })
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.error) {
        alert(data.error);
        btnStart.disabled = false;
        btnStart.textContent = "INICIAR TRANSCRICAO";
        return;
      }
      pollInterval = setInterval(pollStatus, 800);
    })
    .catch(function(e) {
      alert("Erro: " + e.message);
      btnStart.disabled = false;
      btnStart.textContent = "INICIAR TRANSCRICAO";
    });
  }

  function pollStatus() {
    fetch("/status")
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.total > 0) {
          var pct = Math.round((data.current / data.total) * 100);
          progressBar.style.width = pct + "%";
          statusText.textContent = "[" + data.current + "/" + data.total + "] Processando...";
        }

        if (data.progress.length > lastLogLen) {
          var newLogs = data.progress.slice(lastLogLen);
          logArea.textContent += newLogs.join("\n") + "\n";
          logArea.scrollTop = logArea.scrollHeight;
          lastLogLen = data.progress.length;
        }

        if (data.status === "done" || data.status === "error") {
          clearInterval(pollInterval);
          pollInterval = null;

          progressBar.style.width = "100%";
          statusText.textContent = data.status === "done" ? "Concluido!" : "Erro na transcricao";
          statusText.style.color = data.status === "done" ? "#4ade80" : "#f87171";

          btnStart.disabled = false;
          btnStart.textContent = "INICIAR TRANSCRICAO";

          if (data.results && data.results.length) {
            var header = document.createElement("div");
            header.style.cssText = "margin-top:12px; margin-bottom:6px; color:#94a3b8; font-size:0.8rem; text-transform:uppercase;";
            header.textContent = "Downloads";
            resultsArea.appendChild(header);

            for (var i = 0; i < data.results.length; i++) {
              var r = data.results[i];
              var row = document.createElement("div");
              row.className = "result-item";
              row.innerHTML = '<span class="name">' + r.filename + '</span><a href="/download/' + encodeURIComponent(r.filename) + '">Baixar</a>';
              resultsArea.appendChild(row);
            }
          }

          fileList.innerHTML = "";
          btnClear.classList.add("hidden");
        }
      })
      .catch(function() {});
  }

})();
</script>
</body>
</html>"""


# ─── Main ────────────────────────────────────────────────────────

def main():
    errors = check_dependencies()
    if errors:
        print("=" * 50)
        print("  AVISO — Dependências:")
        for e in errors:
            print(f"  • {e}")
        print("  A interface vai abrir, mas a transcrição não")
        print("  funcionará até instalar o que falta.")
        print("=" * 50)

    port = 5000
    url = f"http://localhost:{port}"
    print(f"\n  izi — Transcritor de Vídeo")
    print(f"  Abrindo no navegador: {url}")
    print(f"  Para parar: Ctrl+C\n")

    # Abrir navegador após um breve delay (para dar tempo do servidor iniciar)
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
