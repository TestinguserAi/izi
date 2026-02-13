# izi — Transcritor de Vídeo Local

Transcrição automática de vídeos usando OpenAI Whisper. Interface web minimalista que abre no navegador, roda 100% local.

## Instalação

### 1. ffmpeg

```bash
# Linux (Ubuntu/Debian)
sudo apt install ffmpeg

# Mac
brew install ffmpeg

# Windows: baixe em https://ffmpeg.org/download.html
```

### 2. Dependências Python

```bash
pip install -r requirements.txt
```

## Uso

```bash
python izi.py
```

O navegador abre automaticamente em `http://localhost:5000`.

1. Arraste vídeos para a área de upload (ou clique para selecionar)
2. Escolha o **modelo** Whisper (base é um bom padrão)
3. Clique em **INICIAR TRANSCRIÇÃO**
4. Acompanhe o progresso em tempo real
5. Baixe os arquivos `.txt` quando pronto

As transcrições também ficam salvas em `~/Transcricoes`.

## Modelos Whisper

| Modelo | Qualidade | Velocidade | RAM |
|--------|-----------|------------|-----|
| tiny   | Básica    | Muito rápida | ~1 GB |
| base   | Razoável  | Rápida     | ~1 GB |
| small  | Boa       | Moderada   | ~2 GB |
| medium | Muito boa | Lenta      | ~5 GB |
| large  | Excelente | Muito lenta | ~10 GB |

Na primeira vez, o modelo é baixado automaticamente (~140MB para base, ~1.5GB para medium).
