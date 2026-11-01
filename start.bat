@echo off
setlocal EnableDelayedExpansion
title Margin - study notes assistant
cd /d "%~dp0"

echo.
echo  Margin: study notes assistant
echo  =============================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo  Python is not installed. Install Python 3.10+ from python.org
  echo  and tick "Add python.exe to PATH" during setup, then run this again.
  pause & exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo  Node.js is not installed. Install the LTS version from nodejs.org,
  echo  then run this again.
  pause & exit /b 1
)

rem ---- Groq key: asked once, saved in backend\.env --------------------------
if not exist backend\.env (
  copy backend\.env.example backend\.env >nul
  powershell -NoProfile -Command "(Get-Content backend\.env) -replace '^VECTOR_STORE=.*','VECTOR_STORE=memory' | Set-Content backend\.env"
)
findstr /c:"GROQ_API_KEY=your_groq_key_here" backend\.env >nul
if not errorlevel 1 (
  echo  You need a free Groq API key. Get one at https://console.groq.com/keys
  echo  ^(sign in, click "Create API Key", copy the key starting with gsk_^)
  echo.
  set /p GROQKEY= Paste your key here and press Enter:
  powershell -NoProfile -Command "(Get-Content backend\.env) -replace '^GROQ_API_KEY=.*','GROQ_API_KEY=!GROQKEY!' | Set-Content backend\.env"
)

rem ---- Backend setup (first run only) -----------------------------------------
if not exist backend\.venv\installed-v2.txt (
  echo.
  echo  First run: installing the backend. This takes 5-10 minutes once.
  if not exist backend\.venv\Scripts\python.exe (
    python -m venv backend\.venv || (echo  Could not create a Python environment. & pause & exit /b 1)
  )
  backend\.venv\Scripts\python -m pip install --upgrade pip --disable-pip-version-check
  backend\.venv\Scripts\python -m pip install -r backend\requirements.txt --disable-pip-version-check --progress-bar on || (echo  Backend install failed, see the error above. & pause & exit /b 1)
  echo done> backend\.venv\installed-v2.txt
  findstr /b /c:"VECTOR_STORE=atlas" backend\.env >nul
  if not errorlevel 1 (
    echo  Setting up the MongoDB Atlas vector index...
    pushd backend
    .venv\Scripts\python -m scripts.create_index
    popd
  )
)

rem ---- Frontend setup (first run only) ----------------------------------------
if not exist frontend\node_modules (
  echo.
  echo  First run: installing the frontend...
  pushd frontend
  call npm install --no-audit --no-fund || (popd & echo  Frontend install failed. & pause & exit /b 1)
  popd
)

rem ---- Start both servers ------------------------------------------------------
echo.
echo  Starting... two windows will open. Keep them open while you use the app.
start "Margin backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --port 8000"
start "Margin frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --port 5173"

rem give the backend time to load the embedding model, then open the browser
timeout /t 12 /nobreak >nul
start "" http://localhost:5173
echo.
echo  Opened http://localhost:5173 in your browser.
echo  To stop, close the two server windows.
echo.
pause
