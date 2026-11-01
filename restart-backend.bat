@echo off
title Margin - restart backend
cd /d "%~dp0backend"

echo.
echo  Checking backend packages...
.venv\Scripts\python -m pip install -r requirements.txt --disable-pip-version-check -q || (echo  Package install failed, see the error above. & pause & exit /b 1)
echo done> .venv\installed-v2.txt
echo  Loading the embedding model (downloads ~90 MB the first time)...
.venv\Scripts\python -c "from app.main import get_embedder; e = get_embedder(); v = e.embed(['CAP theorem']); print('  Embedding model OK:', v.shape[1], 'dimensions')" || (echo  Embedding model failed to load, see the error above. & pause & exit /b 1)

echo  Stopping the backend running on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":8000 .*LISTENING"') do (
  taskkill /PID %%p /F >nul 2>nul && echo  Stopped process %%p.
)
timeout /t 2 /nobreak >nul

echo  Starting the backend with the current .env settings...
start "Margin backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --port 8000"
echo.
echo  Done. Refresh http://localhost:5173 in your browser.
timeout /t 5 >nul
