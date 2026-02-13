@echo off
title izi — Transcritor de Video

:: Ir para a pasta onde este .bat está (onde o izi.py está)
cd /d "%~dp0"

echo.
echo   izi — Transcritor de Video
echo   ============================
echo.

:: Verificar se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERRO: Python nao esta instalado.
    echo   Baixe em: https://www.python.org/downloads/
    echo   IMPORTANTE: Marque "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

:: Instalar dependências (usa python -m pip, que sempre funciona)
echo   Verificando dependencias...
python -m pip install flask openai-whisper -q 2>nul

:: Rodar o app
echo   Abrindo no navegador...
echo   Para fechar, feche esta janela.
echo.
python izi.py
pause
