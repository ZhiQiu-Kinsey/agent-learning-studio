$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExecutable = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$webBundle = Join-Path $PSScriptRoot 'frontend/dist/index.html'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Python environment missing. Run: uv sync --dev'
}
if (-not (Test-Path -LiteralPath $webBundle)) {
    throw 'Web bundle missing. Run: npm.cmd --prefix frontend ci ; npm.cmd --prefix frontend run build'
}
Write-Host 'Agent Learning Studio: http://127.0.0.1:8765'
Write-Host 'Keep this terminal open. Press Ctrl+C to stop.'
& $pythonExecutable (Join-Path $PSScriptRoot 'run_web.py')
exit $LASTEXITCODE
