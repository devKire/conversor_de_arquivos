# ⚡ FFImg Converter

Aplicativo desktop com interface gráfica moderna para converter imagens usando FFmpeg.
Tema escuro, conversão em lote, drag & drop, barra de progresso e log em tempo real.

---

## 📁 Estrutura do projeto

```
ffmpeg_converter/
├── main.py          ← Ponto de entrada
├── gui.py           ← Interface gráfica (CustomTkinter)
├── converter.py     ← Lógica FFmpeg + threading
├── utils.py         ← Utilitários, configurações, histórico
├── requirements.txt ← Dependências Python
├── build_exe.bat    ← Script para gerar .exe (Windows)
├── assets/          ← Ícones e recursos visuais (opcional)
└── ffmpeg/          ← Coloque ffmpeg.exe aqui para embutir
```

---

## 🚀 Como executar

### 1. Pré-requisitos

- Python 3.11 ou superior
- FFmpeg instalado (veja abaixo)

### 2. Instalar dependências Python

```bash
pip install -r requirements.txt
```

Ou individualmente:

```bash
pip install customtkinter Pillow tkinterdnd2
```

> `tkinterdnd2` é opcional — sem ele o drag & drop fica desabilitado,
> mas o restante funciona normalmente.

### 3. Executar

```bash
python main.py
```

---

## 🔧 Instalar o FFmpeg

### Windows (recomendado)

**Opção A — Winget (mais fácil):**
```powershell
winget install Gyan.FFmpeg
```

**Opção B — Manual:**
1. Acesse https://ffmpeg.org/download.html
2. Baixe o build Windows (ex: ffmpeg-release-essentials.zip)
3. Extraia e copie `ffmpeg.exe` para `C:\ffmpeg\bin\`
4. Adicione `C:\ffmpeg\bin` ao PATH do Windows

**Opção C — Embutido no aplicativo:**
1. Copie `ffmpeg.exe` para a pasta `ffmpeg/` do projeto
2. O app detectará automaticamente

### Verificar instalação
```bash
ffmpeg -version
```

---

## 📦 Gerar executável (.exe)

```bash
pip install pyinstaller
build_exe.bat
```

O arquivo `dist\FFImgConverter.exe` será criado.

**Para embutir o FFmpeg no .exe:**
1. Coloque `ffmpeg.exe` na pasta `ffmpeg/` do projeto
2. Execute `build_exe.bat`
3. O FFmpeg será incluído automaticamente no executável

---

## 🎨 Funcionalidades

| Funcionalidade | Status |
|---|---|
| Conversão única | ✅ |
| Preview da imagem | ✅ |
| Conversão em lote | ✅ |
| Processamento paralelo | ✅ |
| Drag & drop | ✅ (requer tkinterdnd2) |
| Barra de progresso | ✅ |
| Log FFmpeg em tempo real | ✅ |
| Exportar log | ✅ |
| Renomeação sequencial (001, 002…) | ✅ |
| Tema dark | ✅ |
| Configuração do caminho do FFmpeg | ✅ |
| Detecção automática do FFmpeg | ✅ |
| Histórico de conversões | ✅ |
| Formatos: WEBP, JPG, PNG, AVIF, BMP | ✅ |
| Cancelar lote | ✅ |

---

## 📝 Comandos FFmpeg usados internamente

```bash
# WEBP
ffmpeg -y -i input.png -qscale 60 output.webp

# JPEG
ffmpeg -y -i input.png -q:v 2 output.jpg

# PNG (lossless)
ffmpeg -y -i input.png -compression_level 6 output.png

# AVIF
ffmpeg -y -i input.png -crf 30 -b:v 0 output.avif

# BMP
ffmpeg -y -i input.png output.bmp
```

---

## ⚙️ Configurações salvas

As configurações ficam em `~/.ffimg_converter/config.json`:
- Caminho do FFmpeg
- Última pasta de saída
- Presets de qualidade
- Histórico de conversões (últimas 200)

---

## 🛠️ Dependências

| Pacote | Versão mínima | Uso |
|---|---|---|
| customtkinter | 5.2.0 | Interface gráfica |
| Pillow | 10.0.0 | Preview de imagens |
| tkinterdnd2 | 0.3.0 | Drag & drop (opcional) |
| pyinstaller | qualquer | Gerar .exe (build) |

---

## 📄 Licença

MIT — uso livre, pessoal e comercial.
