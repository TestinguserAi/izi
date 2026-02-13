@echo off
title izi — Transcritor de Video
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

:: Instalar dependências se necessário
echo   Verificando dependencias...
pip install flask openai-whisper >nul 2>&1

:: Rodar o app
echo   Abrindo no navegador...
echo   Para fechar, feche esta janela.
echo.
python "%~dp0izi.py"
pause
