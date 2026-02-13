#!/bin/bash
echo ""
echo "  izi - Transcritor de Video"
echo "  ============================"
echo ""

cd "$(dirname "$0")"

# Atualizar codigo automaticamente
git checkout claude/video-transcription-tool-2yWZW 2>/dev/null
git pull origin claude/video-transcription-tool-2yWZW 2>/dev/null

# Verificar Python
if command -v python3 &> /dev/null; then
    PY=python3
elif command -v python &> /dev/null; then
    PY=python
else
    echo "  ERRO: Python nao esta instalado."
    read -p "  Pressione Enter para sair..."
    exit 1
fi

# Instalar dependencias
echo "  Verificando dependencias..."
$PY -m pip install flask openai-whisper -q 2>/dev/null

# Rodar
echo "  Iniciando..."
echo ""
$PY izi.py
