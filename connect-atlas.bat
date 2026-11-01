@echo off
title Margin - connect MongoDB Atlas
cd /d "%~dp0backend"

echo.
echo  Testing the MongoDB Atlas connection and creating the vector index...
echo.
.venv\Scripts\python -c "from pymongo import MongoClient; from app.config import settings; MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=15000).admin.command('ping'); print('  Connected to Atlas.')"
if errorlevel 1 goto failed

.venv\Scripts\python -m scripts.create_index
if errorlevel 1 goto failed

powershell -NoProfile -Command "(Get-Content .env) -replace '^VECTOR_STORE=.*','VECTOR_STORE=atlas' | Set-Content .env"
echo.
echo  Done. The app now saves your notes in MongoDB Atlas.
echo  Close the two server windows, then double-click start.bat again.
echo.
pause
exit /b 0

:failed
echo.
echo  Could not connect to Atlas, so the app stays on in-memory storage.
echo  Check on cloud.mongodb.com that:
echo    - the cluster is not paused (click Resume if it is)
echo    - Network Access shows 0.0.0.0/0 as Active
echo    - the username and password in backend\.env are correct
echo.
pause
exit /b 1
