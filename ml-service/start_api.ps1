# Starts the MoodDrobe ML API on http://localhost:8000 (keep this window open).
# Usage (from anywhere):  powershell -ExecutionPolicy Bypass -File C:\Users\Singh\Desktop\MoodDrobe\ml-service\start_api.ps1
Set-Location $PSScriptRoot
$env:FASHIONCLIP_MODEL = Join-Path $PSScriptRoot "models\fashion-clip"
$env:HF_HUB_OFFLINE = "1"
$host.UI.RawUI.WindowTitle = "MoodDrobe API :8000"
Write-Output "FASHIONCLIP_MODEL = $env:FASHIONCLIP_MODEL"
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn recommend_server:app --host 0.0.0.0 --port 8000
