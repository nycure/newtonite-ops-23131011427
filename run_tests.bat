@echo off
echo ========================================================
echo  Running Newtonite Ops Behavioral Test Suite (Pytest)
echo ========================================================
if exist "backend\venv\Scripts\pytest.exe" (
    backend\venv\Scripts\pytest -v
) else (
    pytest -v
)
