[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [string]$InputPath,

  [Parameter(Mandatory)]
  [string]$OutputPath
)

$resolvedInput = (Resolve-Path -LiteralPath $InputPath).Path
$extension = [System.IO.Path]::GetExtension($OutputPath).TrimStart('.').ToLowerInvariant()
if ($extension -notin @('svg', 'png', 'pdf')) {
  throw "OutputPath must use .svg, .png, or .pdf."
}

$commands = @(
  Get-Command 'draw.io' -ErrorAction SilentlyContinue
  Get-Command 'drawio' -ErrorAction SilentlyContinue
) | Where-Object { $_ } | Select-Object -First 1

$candidates = @(
  if ($commands) { $commands.Source }
  Join-Path $env:LOCALAPPDATA 'Programs\draw.io\draw.io.exe'
  Join-Path $env:ProgramFiles 'draw.io\draw.io.exe'
  if (${env:ProgramFiles(x86)}) {
    Join-Path ${env:ProgramFiles(x86)} 'draw.io\draw.io.exe'
  }
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$executable = $candidates | Select-Object -First 1
if (-not $executable) {
  throw "diagrams.net Desktop was not found. Install it or export the file manually from https://app.diagrams.net/."
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
  New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

& $executable --export --crop --format $extension --output $OutputPath $resolvedInput
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $OutputPath)) {
  throw "diagrams.net export failed with exit code $LASTEXITCODE."
}

Write-Output (Resolve-Path -LiteralPath $OutputPath).Path
