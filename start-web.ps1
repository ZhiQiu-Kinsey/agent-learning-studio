$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
# lab.py installs what is missing, rebuilds the UI when needed and starts the server.
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is missing. Install it from https://docs.astral.sh/uv/, then run: uv run lab.py'
}
& uv run lab.py @args
exit $LASTEXITCODE
