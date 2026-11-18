# MoodDrobe: one script for the whole setup, run from the ml-service folder.
#
#   cd C:\Users\nishi\OneDrive\Desktop\MoodDrobe\MoodDrobe\ml-service
#   powershell -ExecutionPolicy Bypass -File .\setup_and_run.ps1
#
# It installs packages, checks the saved embeddings, starts Qdrant, trains the
# category/attribute models, extracts catalogue colours, loads Qdrant, runs both evaluations, then starts
# the API. It never deletes or re-computes embeddings. It stops at the first
# step that fails and tells you which one.
#
# Options:
#   -SkipEval     skip the two evaluation scripts
#   -NoServer     do not start the API at the end
#   -LocalQdrant  use Qdrant's built-in local mode instead of Docker

param(
    [switch]$SkipEval,
    [switch]$NoServer,
    [switch]$LocalQdrant
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

Step "1/8 Python environment"
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Host "No .venv found in $PSScriptRoot. Create it first: python -m venv .venv" -ForegroundColor Red
    exit 1
}
. .\.venv\Scripts\Activate.ps1
Run "pip install" { python -m pip install -r requirements-vectordb.txt }

Step "2/8 Check saved embeddings (read-only)"
Run "inspect chunk" { python -m scripts.verify_embeddings --inspect }
python -m scripts.verify_embeddings
if ($LASTEXITCODE -eq 1) { Write-Host "No embedding chunks found." -ForegroundColor Red; exit 1 }
if ($LASTEXITCODE -ne 0) {
    Write-Host "Some chunks are missing or invalid (normal if embedding is still running). Continuing with the valid ones." -ForegroundColor Yellow
}

Step "3/8 Qdrant"
if ($LocalQdrant) {
    $env:QDRANT_PATH = "data/processed/qdrant_local"
    Write-Host "Using local mode at $env:QDRANT_PATH (no Docker)."
} else {
    Push-Location ..\backend
    Run "docker compose up qdrant (is Docker Desktop running?)" { docker compose up -d qdrant }
    Pop-Location
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        try { Invoke-RestMethod http://localhost:6333/readyz -TimeoutSec 2 | Out-Null; $ready = $true; break }
        catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { Write-Host "Qdrant did not start on port 6333." -ForegroundColor Red; exit 1 }
    Write-Host "Qdrant is running: http://localhost:6333/dashboard"
}

Step "4/8 Train category + attribute models (minutes)"
Run "train_heads" { python -m scripts.train_heads }

Step "4b/8 Catalogue colours (resumable, skips finished parts)"
if (Test-Path "data\raw\deepfashion\Img\img") {
    Run "extract_colors" { python -m scripts.extract_colors }
} else {
    Write-Host "No photos in data\raw\deepfashion\Img\img: skipping colours (colour matching stays off)." -ForegroundColor Yellow
}

Step "5/8 Load vectors into Qdrant"
python -m scripts.ingest_qdrant --force
if ($LASTEXITCODE -ne 0) {
    Write-Host "Some chunks were skipped (listed above). Search still works with the loaded ones." -ForegroundColor Yellow
}

if (-not $SkipEval) {
    Step "6/8 Evaluate search (Precision@K, Recall@K, MRR, latency)"
    Run "evaluate_retrieval" { python -m scripts.evaluate_retrieval }
    Step "7/8 Evaluate recommendations (variety vs similarity)"
    Run "evaluate_recommendations" { python -m scripts.evaluate_recommendations }
    Write-Host "Reports saved in data\processed\reports"
}

if (-not $NoServer) {
    Step "8/8 Start the API on http://localhost:8000/docs (Ctrl+C to stop)"
    Write-Host "The first request loads FashionCLIP (10-30 seconds)."
    uvicorn recommend_server:app --port 8000
}
