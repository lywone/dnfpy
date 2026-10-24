@echo off
rem Relist expired auction items (My Listings) - requires game stopped on auction "My Listings" page
cd /d %~dp0
.\.venv\Scripts\python.exe mail_claim.py relist
echo.
pause
