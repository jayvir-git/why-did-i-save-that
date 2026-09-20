$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try { python scripts/start.py } finally { Pop-Location }
