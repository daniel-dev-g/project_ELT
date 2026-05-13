@echo off
setlocal EnableDelayedExpansion

where uv >nul 2>&1
if %errorlevel% equ 0 goto :sync

echo uv no encontrado -- instalando...
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

rem uv instala en %APPDATA%\uv\bin en versiones recientes
rem o en %USERPROFILE%\.local\bin en versiones anteriores
for %%P in ("%APPDATA%\uv\bin" "%USERPROFILE%\.local\bin") do (
    if exist "%%~P\uv.exe" (
        set "PATH=%%~P;!PATH!"
        goto :sync
    )
)

echo.
echo uv instalado. Abre una nueva terminal y ejecuta:
echo   uv sync
echo   uv run python gui.py
exit /b 0

:sync
uv sync

echo.
echo Instalacion completa.
echo Lanza la interfaz con:  uv run python gui.py
