"""
izi - Transcritor de Video Local usando Whisper
Rode: python izi.py
"""

import os
import sys
import threading
import time
import uuid
import webbrowser

from flask import Flask, request, jsonify, send_file, Response

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

state = {
    "files": [],
    "is_processing": False,
    "progress": [],
    "current": 0,
    "total": 0,
    "status": "idle",
    "results": [],
}
state_lock = threading.Lock()
loaded_model = None
loaded_model_name = None


def add_log(msg):
    with state_lock:
        state["progress"].append(msg)


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024


@app.route("/")
def index():
    return Response(HTML_PAGE, content_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-store"})


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
        save_path = os.path.join(UPLOAD_DIR, file_id + "_" + f.filename)
        f.save(save_path)
        entry = {"id": file_id, "name": f.filename, "path": save_path}
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
            return jsonify({"error": "Ja em processamento"}), 409
        if not state["files"]:
            return jsonify({"error": "Nenhum arquivo adicionado"}), 400
    data = request.get_json(silent=True) or {}
    model_name = data.get("model", "base")
    if model_name not in MODELS:
        model_name = "base"
    if not WHISPER_AVAILABLE:
        return jsonify({"error": "openai-whisper nao esta instalado. Rode: pip install openai-whisper"}), 500
    with state_lock:
        state["is_processing"] = True
        state["status"] = "processing"
        state["progress"] = []
        state["results"] = []
        state["current"] = 0
        state["total"] = len(state["files"])
        files_snapshot = list(state["files"])
    thread = threading.Thread(target=transcribe_worker, args=(files_snapshot, model_name), daemon=True)
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
        })


@app.route("/download/<filename>")
def download(filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(filepath):
        return jsonify({"error": "Arquivo nao encontrado"}), 404
    return send_file(filepath, as_attachment=True)


def transcribe_worker(files, model_name):
    global loaded_model, loaded_model_name
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if loaded_model is None or loaded_model_name != model_name:
        add_log("Carregando modelo '" + model_name + "'...")
        try:
            loaded_model = whisper.load_model(model_name)
            loaded_model_name = model_name
            add_log("Modelo '" + model_name + "' pronto.")
        except Exception as e:
            add_log("Erro ao carregar modelo: " + str(e))
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
        add_log("[" + str(i) + "/" + str(total) + "] Transcrevendo: " + name)
        try:
            result = model.transcribe(filepath)
            text = result["text"].strip()
            out_name = os.path.splitext(name)[0] + ".txt"
            out_path = os.path.join(OUTPUT_DIR, out_name)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            add_log("  Salvo: " + out_name)
            with state_lock:
                state["results"].append({"name": name, "filename": out_name})
            successes += 1
        except Exception as e:
            add_log("  Erro: " + str(e))
    for file_info in files:
        try:
            os.remove(file_info["path"])
        except OSError:
            pass
    elapsed = time.time() - t_start
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    add_log("Concluido: " + str(successes) + "/" + str(total) + " em " + str(mins) + "min " + str(secs) + "s")
    add_log("Pasta: " + OUTPUT_DIR)
    with state_lock:
        state["is_processing"] = False
        state["status"] = "done"
        state["files"].clear()


HTML_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>izi</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#1a1b2e;color:#e2e8f0;min-height:100vh;display:flex;justify-content:center;padding:40px 20px}
.c{width:100%;max-width:640px}
h1{font-size:2rem;color:#fff;margin-bottom:2px}
.sub{color:#94a3b8;font-size:.9rem;margin-bottom:24px}
.card{background:#232540;border:1px solid #3d4066;border-radius:12px;padding:20px;margin-bottom:16px}
.ct{font-size:.85rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}
.dz{border:2px dashed #3d4066;border-radius:10px;padding:40px 20px;text-align:center;cursor:pointer;transition:all .2s}
.dz:hover,.dz.over{border-color:#6c63ff;background:rgba(108,99,255,.08)}
.dzi{font-size:2.5rem;margin-bottom:8px}
.dzt{color:#94a3b8;font-size:.9rem}
.dzt b{color:#6c63ff}
.fl{margin-top:12px}
.fi{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#2a2d4a;border-radius:8px;margin-bottom:6px;font-size:.85rem}
.fi .n{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fi .x{background:none;border:none;color:#f87171;cursor:pointer;font-size:1.1rem;padding:0 4px;margin-left:8px}
.cr{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.cr label{color:#94a3b8;font-size:.85rem}
.cr select{background:#2a2d4a;color:#e2e8f0;border:1px solid #3d4066;border-radius:6px;padding:6px 12px;font-size:.9rem}
.op{font-family:Consolas,monospace;font-size:.8rem;color:#94a3b8}
.bs{width:100%;padding:14px;background:#6c63ff;color:#fff;border:none;border-radius:10px;font-size:1rem;font-weight:700;cursor:pointer;transition:background .2s}
.bs:hover{background:#5a52e0}
.bs:disabled{background:#3d4066;cursor:not-allowed}
.bc{background:none;border:1px solid #3d4066;color:#94a3b8;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:.8rem}
.pb{width:100%;height:8px;background:#2a2d4a;border-radius:4px;overflow:hidden;margin-bottom:12px}
.pf{height:100%;background:#6c63ff;border-radius:4px;transition:width .3s;width:0}
.st{font-size:.85rem;color:#94a3b8;margin-bottom:8px}
.log{background:#1a1b2e;border:1px solid #3d4066;border-radius:8px;padding:12px;font-family:Consolas,monospace;font-size:.8rem;max-height:240px;overflow-y:auto;white-space:pre-wrap;line-height:1.5;color:#94a3b8}
.rs{margin-top:12px}
.ri{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#2a2d4a;border-radius:8px;margin-bottom:6px}
.ri .n{font-size:.85rem}
.ri a{color:#6c63ff;text-decoration:none;font-size:.85rem;font-weight:600}
.hd{display:none}
</style>
</head>
<body>
<div class="c">
<h1>izi</h1>
<p class="sub">Transcricao de video local com Whisper</p>
<p id="ver" style="color:#4ade80;font-size:.8rem;margin-bottom:12px">v3 - JS OK</p>

<div class="card">
<div class="ct">Videos</div>
<div class="dz" id="dz">
<div class="dzi">&#128194;</div>
<div class="dzt">Arraste videos aqui ou <b>clique para selecionar</b></div>
</div>
<input type="file" id="fi" multiple accept=".mp4,.mkv,.avi,.mov,.webm,.m4v,.mpg,.mpeg,.wmv,.flv" style="display:none">
<div class="fl" id="fl"></div>
<div style="margin-top:8px;text-align:right">
<button class="bc hd" id="bc">Limpar tudo</button>
</div>
</div>

<div class="card">
<div class="ct">Configuracoes</div>
<div class="cr">
<label>Modelo Whisper:</label>
<select id="ms">
<option value="tiny">tiny (rapido)</option>
<option value="base" selected>base (equilibrado)</option>
<option value="small">small (boa qualidade)</option>
<option value="medium">medium (alta qualidade)</option>
<option value="large">large (maxima qualidade)</option>
</select>
</div>
<div style="margin-top:8px"><span class="op">&#128193; Saida: ~/Transcricoes</span></div>
</div>

<button class="bs" id="bs">INICIAR TRANSCRICAO</button>

<div class="card hd" id="pc" style="margin-top:16px">
<div class="ct">Progresso</div>
<div class="st" id="st">Aguardando...</div>
<div class="pb"><div class="pf" id="pf"></div></div>
<div class="log" id="lg"></div>
<div class="rs" id="ra"></div>
</div>
</div>

<script>
var dz=document.getElementById("dz");
var fi=document.getElementById("fi");
var fl=document.getElementById("fl");
var bc=document.getElementById("bc");
var bs=document.getElementById("bs");
var ms=document.getElementById("ms");
var pc=document.getElementById("pc");
var pf=document.getElementById("pf");
var st=document.getElementById("st");
var lg=document.getElementById("lg");
var ra=document.getElementById("ra");
var pi=null,ll=0;

dz.onclick=function(){fi.click()};
dz.ondragover=function(e){e.preventDefault();dz.className="dz over"};
dz.ondragleave=function(){dz.className="dz"};
dz.ondrop=function(e){e.preventDefault();dz.className="dz";if(e.dataTransfer.files.length)up(e.dataTransfer.files)};
fi.onchange=function(){if(fi.files.length)up(fi.files);fi.value=""};
bc.onclick=function(){fetch("/clear",{method:"POST"}).then(function(){fl.innerHTML="";bc.style.display="none"})};
bs.onclick=function(){go()};

function up(files){
var fd=new FormData();
for(var i=0;i<files.length;i++)fd.append("files",files[i]);
bs.disabled=true;bs.textContent="ENVIANDO...";
fetch("/upload",{method:"POST",body:fd}).then(function(r){return r.json()}).then(function(d){
if(d.uploaded){for(var i=0;i<d.uploaded.length;i++)af(d.uploaded[i].id,d.uploaded[i].name)}
bs.disabled=false;bs.textContent="INICIAR TRANSCRICAO";
}).catch(function(e){alert("Erro: "+e.message);bs.disabled=false;bs.textContent="INICIAR TRANSCRICAO"});
}

function af(id,name){
var d=document.createElement("div");d.className="fi";d.id="f-"+id;
var s=document.createElement("span");s.className="n";s.textContent=name;
var b=document.createElement("button");b.className="x";b.textContent="x";
b.onclick=function(){fetch("/remove/"+id,{method:"DELETE"}).then(function(){d.remove();if(!fl.children.length)bc.style.display="none"})};
d.appendChild(s);d.appendChild(b);fl.appendChild(d);bc.style.display="inline-block";
}

function go(){
bs.disabled=true;bs.textContent="PROCESSANDO...";
pc.style.display="block";lg.textContent="";ra.innerHTML="";ll=0;
st.textContent="Iniciando...";st.style.color="#94a3b8";pf.style.width="0%";
fetch("/transcribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({model:ms.value})})
.then(function(r){return r.json()}).then(function(d){
if(d.error){alert(d.error);bs.disabled=false;bs.textContent="INICIAR TRANSCRICAO";return}
pi=setInterval(poll,800);
}).catch(function(e){alert("Erro: "+e.message);bs.disabled=false;bs.textContent="INICIAR TRANSCRICAO"});
}

function poll(){
fetch("/status").then(function(r){return r.json()}).then(function(d){
if(d.total>0){var p=Math.round(d.current/d.total*100);pf.style.width=p+"%";st.textContent="["+d.current+"/"+d.total+"] Processando...";}
if(d.progress.length>ll){var n=d.progress.slice(ll);lg.textContent+=n.join("\\n")+"\\n";lg.scrollTop=lg.scrollHeight;ll=d.progress.length}
if(d.status==="done"||d.status==="error"){clearInterval(pi);pi=null;pf.style.width="100%";
st.textContent=d.status==="done"?"Concluido!":"Erro";st.style.color=d.status==="done"?"#4ade80":"#f87171";
bs.disabled=false;bs.textContent="INICIAR TRANSCRICAO";
if(d.results&&d.results.length){for(var i=0;i<d.results.length;i++){var r=d.results[i];var row=document.createElement("div");row.className="ri";
row.innerHTML='<span class="n">'+r.filename+'</span><a href="/download/'+encodeURIComponent(r.filename)+'">Baixar</a>';ra.appendChild(row)}}
fl.innerHTML="";bc.style.display="none"}
}).catch(function(){});
}
</script>
</body>
</html>"""


def main():
    port = 5000
    url = "http://localhost:" + str(port)
    print("")
    print("  izi - Transcritor de Video")
    print("  Abrindo: " + url)
    print("  Para parar: Ctrl+C")
    print("")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
