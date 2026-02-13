# PROMPT PARA RECRIAR O IZI — TRANSCRITOR DE VIDEO

Cole tudo abaixo em uma nova conversa com uma IA (Claude, ChatGPT, etc):

---

## CONTEXTO

Preciso que voce crie do ZERO um transcritor de video local usando Python + Whisper (openai-whisper). Interface web bonita, escura, minimalista. Tudo em UM UNICO ARQUIVO PYTHON. O usuario da double-click e funciona.

## O QUE O SISTEMA FAZ

1. Abre uma interface web no navegador automaticamente
2. O usuario arrasta ou clica para selecionar videos (.mp4, .mkv, .avi, .mov, .webm, etc)
3. Escolhe o modelo Whisper (tiny, base, small, medium, large)
4. Clica "Iniciar Transcricao"
5. Ve o progresso em tempo real (barra de progresso + log)
6. Quando termina, pode baixar os arquivos .txt com a transcricao
7. Os .txt sao salvos em ~/Transcricoes

## REQUISITOS TECNICOS

- Python 3
- Flask para o servidor web
- openai-whisper para transcrever
- Interface HTML/CSS/JS embutida no proprio arquivo Python
- Porta: usar 5001 (NAO 5000, para evitar conflito)
- Upload de arquivos ate 4GB
- Processamento em thread separada (nao travar a interface)
- Polling via fetch para atualizar progresso em tempo real
- Arquivos temporarios de upload em ~/.izi_uploads (limpar apos transcrever)

## ERROS QUE A IA ANTERIOR COMETEU (NAO REPITA)

### Erro 1: JavaScript que nao funcionava
- Usou `onclick="funcao()"` inline no HTML junto com `const` no JS — isso pode falhar em alguns browsers
- SOLUCAO: Use SOMENTE `element.onclick = function(){}` ou `addEventListener` no JS. ZERO onclick no HTML.

### Erro 2: String Python com JS embutido causando problemas de escape
- Colocou o HTML dentro de `"""..."""` e `r"""..."""` — caracteres como `\n` dentro do JS ficavam ambiguos (escape do Python vs escape do JS)
- SOLUCAO: Use string normal `"""..."""` e no JS use SOMENTE aspas duplas. Evite `\n` no JS — use concatenacao ou Array.join(). Ou melhor ainda: sirva o HTML como arquivo separado.

### Erro 3: Demorou demais debugando em vez de reescrever
- Ficou lendo o arquivo linha por linha, fazendo micro-edits, tentando achar o bug
- Gastou 1 hora do usuario sem resolver
- SOLUCAO: Se algo nao funciona, reescreve do zero. Nao fica remendando.

### Erro 4: Dependeu de git para o usuario atualizar o codigo
- O usuario nao sabia usar git. Baixou o projeto como ZIP.
- SOLUCAO: Tudo deve funcionar com um unico arquivo. O usuario da double-click e pronto.

### Erro 5: Nao testou se o JS realmente executava
- Nunca verificou se o JavaScript carregava no browser. Ficou assumindo que o problema era outro.
- SOLUCAO: Adicione um indicador visual de que o JS carregou (ex: um texto que muda quando o script roda).

## O QUE FUNCIONOU BEM (MANTER)

1. Design visual escuro com cards — ficou bonito
2. Drag and drop + clique para selecionar — boa UX
3. Barra de progresso + log em tempo real — essencial
4. Selecao de modelo Whisper — util
5. Download dos .txt direto na interface — pratico
6. Thread separada para transcricao — nao trava
7. Estrutura Flask com rotas REST — limpa e funcional
8. Botao "Limpar tudo" para remover arquivos da fila

## DESIGN DA INTERFACE (MANTER ESTE ESTILO)

- Fundo: #1a1b2e (azul escuro)
- Cards: #232540 com borda #3d4066
- Cor de destaque: #6c63ff (roxo)
- Texto principal: #e2e8f0
- Texto secundario: #94a3b8
- Sucesso: #4ade80 (verde)
- Erro: #f87171 (vermelho)
- Font: Segoe UI / system-ui
- Log: Consolas monospace
- Border radius: 12px nos cards, 10px nos botoes
- Dropzone com borda dashed que muda de cor no hover/drag

## ESTRUTURA DAS ROTAS FLASK

- GET / → retorna o HTML da interface
- POST /upload → recebe arquivos, salva em ~/.izi_uploads, retorna JSON com ids
- DELETE /remove/<id> → remove um arquivo da fila
- POST /clear → limpa todos os arquivos da fila
- POST /transcribe → inicia transcricao em thread, recebe {model: "base"}
- GET /status → retorna JSON com status, progresso, resultados
- GET /download/<filename> → baixa o .txt transcrito

## ENTREGA FINAL

Crie UM UNICO ARQUIVO chamado `izi.py` e salve em:

```
C:\Users\DELL\Desktop\NEW\izi.py
```

Crie tambem um `iniciar.bat` na mesma pasta:

```
C:\Users\DELL\Desktop\NEW\iniciar.bat
```

O `iniciar.bat` deve:
1. Verificar se Python esta instalado
2. Instalar flask e openai-whisper automaticamente (`python -m pip install flask openai-whisper -q`)
3. Rodar `python izi.py`
4. Se der erro, mostrar mensagem clara

O `izi.py` deve:
1. Usar porta 5001
2. Abrir o navegador automaticamente em http://localhost:5001
3. Funcionar 100% ao dar double-click no iniciar.bat
4. JavaScript DEVE funcionar (testar com indicador visual)

## IMPORTANTE

- NAO use f-strings dentro do HTML/JS (conflito com chaves do JS)
- NAO use emojis no codigo JS (pode quebrar encoding)
- NAO use const/let/arrow functions no JS (use var e function para max compatibilidade)
- NAO use async/await no JS (use .then() para max compatibilidade)
- NAO use template literals no JS (use concatenacao com +)
- Use HTML entities para icones (&#128194; em vez de emojis)
- Teste mentalmente se cada onclick/evento realmente funciona
- O HTML deve ter charset UTF-8 E o Flask deve retornar com content-type text/html; charset=utf-8
