# MoodDrobe: train the outfit compatibility model (Polyvore Outfits).
# Run from the ml-service folder, with .venv already set up (setup_and_run.ps1 does that):
#
#   cd C:\Users\Singh\Desktop\MoodDrobe\ml-service
#   powershell -ExecutionPolicy Bypass -File .\run_compat.ps1
#
# One-time before the first run (see COMPATIBILITY.md):
#   1. Request access at https://huggingface.co/datasets/mvasil/polyvore-outfits
#   2. hf auth login   (paste a "Read" token from https://huggingface.co/settings/tokens)
#
# Steps: download (~2.7 GB) -> FashionCLIP vectors for ~250k items (GPU) -> train + test.
# Every step can be stopped and re-run; finished work is skipped.
# Options:
#   -SkipDownload   data is already in data\raw\polyvore_outfits
#   -SkipEmbed      item_embeddings.npz already exists
#   -Epochs 5       shorter training for a quick try

param(
    [switch]$SkipDownload,
    [switch]$SkipEmbed,
    [int]$Epochs = 40
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }

function Run($description, [scriptblock]$command) {
    & $command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nStopped: '$description' failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        Write-Host "Copy the messages above and send them to Claude." -ForegroundColor Red
        exit 1
    }
}

Step "1/4 Python environment"
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Host "No .venv found. Run setup_and_run.ps1 first (or: python -m venv .venv)." -ForegroundColor Red
    exit 1
}
. .\.venv\Scripts\Activate.ps1
Run "pip install" { python -m pip install pyarrow huggingface_hub }
python -c "import torch; print('PyTorch', torch.__version__, '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none (CPU, slower)')"

if (-not $SkipDownload) {
    Step "2/4 Download Polyvore Outfits (nondisjoint, ~2.7 GB)"
    Run "download_polyvore" { python -m scripts.download_polyvore }
}

if (-not $SkipEmbed) {
    Step "3/4 FashionCLIP vectors for every Polyvore item (about 30-60 min on an RTX 3050)"
    Run "embed_polyvore" { python -m scripts.embed_polyvore }
}

Step "4/4 Train and test the compatibility model (minutes on GPU)"
Run "train_compat" { python -m scripts.train_compat --epochs $Epochs }

Write-Host "`nDone. Restart the API (uvicorn recommend_server:app --port 8000);" -ForegroundColor Green
Write-Host "complete-the-look now ranks by outfit compatibility. Results: data\processed\reports\compat_eval.json" -ForegroundColor Green
