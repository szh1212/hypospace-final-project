param([string]$LocalRoot = "$env:USERPROFILE\HypoSpaceLocal")
$ErrorActionPreference = 'Stop'
$env:OLLAMA_MODELS = Join-Path $LocalRoot 'models'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_CONTEXT_LENGTH = '8192'
$env:OLLAMA_VULKAN = '0'
$exe = Join-Path $LocalRoot 'ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $exe)) { $exe = (Get-Command ollama -ErrorAction Stop).Source }
try {
    $version = Invoke-RestMethod http://localhost:11434/api/version -TimeoutSec 2
    Write-Output "Ollama already running: $($version.version). Verify its model path before pulling."
} catch {
    Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LocalRoot 'ollama-server.stdout.log') -RedirectStandardError (Join-Path $LocalRoot 'ollama-server.stderr.log')
}
