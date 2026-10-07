[CmdletBinding()]
param(
  [string] $AgentPath = '.github\agents\apim-limit-ui-tester.agent.md'
)

$ErrorActionPreference = 'Stop'

$raw = Get-Content -LiteralPath $AgentPath -Raw
$normalized = $raw -replace '\s+', ' '
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($frontmatter in @(
    'name: APIM Limit UI Tester'
    'target: vscode'
    'user-invocable: true'
    'disable-model-invocation: true'
  )) {
  if (-not $raw.Contains($frontmatter)) {
    $failures.Add("Missing frontmatter '$frontmatter'.")
  }
}

foreach ($tool in @(
    'read'
    'search'
    'openBrowserPage'
    'readPage'
    'runPlaywrightCode'
    'screenshotPage'
  )) {
  if (-not $raw.Contains("  - $tool")) {
    $failures.Add("Missing allowed tool '$tool'.")
  }
}

$frontmatterEnd = $raw.IndexOf("`n---", 4)
if ($frontmatterEnd -lt 0) {
  $failures.Add('YAML frontmatter is not closed.')
}
else {
  $yaml = $raw.Substring(0, $frontmatterEnd)
  foreach ($forbiddenTool in @(
      'edit'
      'execute'
      'powershell'
      'Azure MCP'
      'azure_'
    )) {
    if ($yaml -match "(?im)^\s*-\s*$([regex]::Escape($forbiddenTool))") {
      $failures.Add("Forbidden tool '$forbiddenTool' is enabled.")
    }
  }
}

foreach ($scenario in @(
    'smoke'
    'rpm-serial'
    'rpm-concurrent'
    'tpm-serial'
    'tpm-concurrent'
    'cross-model-rpm'
    'recovery-after-429'
    'workbook-visual-check'
  )) {
  if (-not $raw.Contains($scenario)) {
    $failures.Add("Missing scenario '$scenario'.")
  }
}

foreach ($safetyMarker in @(
    'maximum 60-minute window'
    'testModelTpm < testSkuTpm'
    'min(operator value, 4)'
    'testRpm + 2'
    'ceil(1.25 * testSkuTpm / calibratedRequestTokens)'
    'BLOCKED_DETERMINISTIC_RUNNER'
    'BLOCKED_SELECTOR_AMBIGUITY'
    'BLOCKED_CORRELATION'
    'Never retry a 429'
    'exact, case-insensitive host membership'
    'exactly one `runPlaywrightCode` call'
    'Never capture request/response bodies'
    'apim-limit-ui-tester.preflight.js'
    'Embed its `validateRunManifest` function'
    'fixedModelMode'
    '/deployments/{model}/'
  )) {
  if (-not $normalized.Contains($safetyMarker)) {
    $failures.Add("Missing safety contract '$safetyMarker'.")
  }
}

if ($failures.Count -gt 0) {
  throw ($failures -join [Environment]::NewLine)
}

Write-Output 'Validated bounded APIM limit UI tester agent.'
