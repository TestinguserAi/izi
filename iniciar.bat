@echo off
title izi
cd /d "%~dp0"

echo.
echo   izi - Transcritor de Video
echo   ============================
echo.

:: Atualizar codigo automaticamente
git checkout claude/video-transcription-tool-2yWZW >nul 2>&1
git pull origin claude/video-transcription-tool-2yWZW >nul 2>&1

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERRO: Python nao esta instalado.
    echo   Baixe em: https://www.python.org/downloads/
    echo   IMPORTANTE: Marque "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

:: Instalar dependencias
echo   Verificando dependencias...
python -m pip install flask openai-whisper -q 2>nul

:: Rodar
echo   Iniciando...
echo.
python izi.py
pause
