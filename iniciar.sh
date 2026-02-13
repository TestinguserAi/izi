#!/bin/bash
echo ""
echo "  izi — Transcritor de Vídeo"
echo "  ============================"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "  ERRO: Python3 não está instalado."
    echo "  Linux: sudo apt install python3 python3-pip"
    echo "  Mac: brew install python3"
    read -p "  Pressione Enter para sair..."
    exit 1
fi

# Instalar dependências
echo "  Verificando dependências..."
pip3 install flask openai-whisper -q

# Rodar
echo "  Abrindo no navegador..."
echo "  Para fechar: Ctrl+C"
echo ""
python3 "$(dirname "$0")/izi.py"
