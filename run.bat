@echo off
cd /d "%~dp0"
if not exist "data" mkdir data
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)
python -c "from backend.app import create_app; app=create_app(); import webbrowser; webbrowser.open('http://127.0.0.1:5000'); app.run(host='127.0.0.1', port=5000, threaded=True)"
pause
