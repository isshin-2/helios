@echo off
echo ==========================================
echo    HELIOS Setup Utility
echo ==========================================
echo This will allow you to configure HELIOS and provide tool information.
echo.
echo =========================================================================
echo  IMPORTANT: For Gmail and Google Drive integration, you will need 
echo  an OAuth Client ID and Secret. If you don't have these:
echo  1. Go to https://console.cloud.google.com/
echo  2. Create a Project and enable the Gmail API and Google Drive API
echo  3. Go to APIs ^& Services -^> Credentials
echo  4. Create an OAuth client ID (type: Desktop app)
echo =========================================================================
echo.
python setup.py --reset
echo.
echo Setup complete. Now testing start.bat...
echo.
call start.bat
pause
