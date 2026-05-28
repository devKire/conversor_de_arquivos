@echo off
REM ============================================================
REM  build_exe.bat — Gera ffimg_converter.exe com PyInstaller
REM  Pré-requisito: pip install pyinstaller
REM ============================================================

echo ============================================================
echo  FFImg Converter — Build
echo ============================================================

REM Instala dependências caso necessário
pip install customtkinter Pillow tkinterdnd2 pyinstaller --quiet

REM Limpa builds anteriores
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Gera o executável
pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "FFImgConverter" ^
  --add-data "ffmpeg;ffmpeg" ^
  --hidden-import customtkinter ^
  --hidden-import PIL ^
  --hidden-import tkinterdnd2 ^
  main.py

echo.
echo ============================================================
echo  Build concluído!
echo  Executável em: dist\FFImgConverter.exe
echo ============================================================
pause
