# izi — Transcritor de Vídeo Local

Transcrição automática de vídeos usando OpenAI Whisper. Interface gráfica minimalista, roda 100% local.

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

> No Linux, se o tkinter não estiver disponível: `sudo apt install python3-tk`

## Uso

```bash
python izi.py
```

1. Clique em **Adicionar Vídeos** e selecione os arquivos
2. Escolha o **modelo** Whisper (base é um bom padrão)
3. Clique em **INICIAR TRANSCRIÇÃO**
4. Um `.txt` é criado para cada vídeo na pasta de saída

## Modelos Whisper

| Modelo | Qualidade | Velocidade | RAM |
|--------|-----------|------------|-----|
| tiny   | Básica    | Muito rápida | ~1 GB |
| base   | Razoável  | Rápida     | ~1 GB |
| small  | Boa       | Moderada   | ~2 GB |
| medium | Muito boa | Lenta      | ~5 GB |
| large  | Excelente | Muito lenta | ~10 GB |

Na primeira vez, o modelo é baixado automaticamente (~140MB para base, ~1.5GB para medium).
