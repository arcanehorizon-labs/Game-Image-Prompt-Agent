[CmdletBinding()]
param(
    [string]$GddPath,
    [string]$GameRoot,
    [string]$StyleFile,
    [ValidateSet('ChatGPT','Gemini','Canonical')][string]$Provider = 'ChatGPT',
    [ValidateSet('Individual','Batch','Both')][string]$PromptMode = 'Individual',
    [ValidateSet('A','B','C','All')][string]$Variant = 'A',
    [string]$OutputDir,
    [string]$FinalPromptPath,
    [switch]$ForceResetOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Normalize-InputPath([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $Value }
    $Value = $Value.Trim()
    if (($Value.StartsWith('"') -and $Value.EndsWith('"')) -or ($Value.StartsWith("'") -and $Value.EndsWith("'"))) {
        $Value = $Value.Substring(1, $Value.Length - 2).Trim()
    }
    return [Environment]::ExpandEnvironmentVariables($Value)
}

function Show-NearbyFiles([string]$Value) {
    try {
        $normalized = Normalize-InputPath $Value
        $parent = Split-Path $normalized -Parent
        if (-not [string]::IsNullOrWhiteSpace($parent) -and (Test-Path -LiteralPath $parent -PathType Container)) {
            Write-Host 'Files available in that folder:' -ForegroundColor Yellow
            Get-ChildItem -LiteralPath $parent -File |
                Where-Object { $_.Extension -in @('.md','.txt','.docx','.pdf') } |
                Select-Object -First 20 -ExpandProperty FullName |
                ForEach-Object { Write-Host ('  ' + $_) }
        }
    } catch {}
}

function Read-ExistingFile([string]$Label, [string]$Current) {
    while ($true) {
        $Current = Normalize-InputPath $Current
        if (-not [string]::IsNullOrWhiteSpace($Current) -and (Test-Path -LiteralPath $Current -PathType Leaf)) { return (Resolve-Path -LiteralPath $Current).Path }
        if (-not [string]::IsNullOrWhiteSpace($Current)) {
            Write-Warning ('File not found: ' + $Current)
            Show-NearbyFiles $Current
        }
        $Current = Read-Host $Label
    }
}

function Read-ExistingDirectory([string]$Label, [string]$Current) {
    while ($true) {
        $Current = Normalize-InputPath $Current
        if (-not [string]::IsNullOrWhiteSpace($Current) -and (Test-Path -LiteralPath $Current -PathType Container)) { return (Resolve-Path -LiteralPath $Current).Path }
        if (-not [string]::IsNullOrWhiteSpace($Current)) { Write-Warning ('Directory not found: ' + $Current) }
        $Current = Read-Host $Label
    }
}

function Invoke-Gipa([string[]]$GipaArgs, [int[]]$AllowedExitCodes = @(0)) {
    Write-Host ''
    Write-Host ('gipa ' + ($GipaArgs -join ' ')) -ForegroundColor Cyan
    & gipa @GipaArgs
    $code = $LASTEXITCODE
    if ($AllowedExitCodes -notcontains $code) { throw "GIPA failed with exit code $code." }
    return $code
}

function Get-GipaStatus([string]$StatePath) {
    $lines = & gipa status --state $StatePath
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read GIPA state.' }
    foreach ($line in $lines) { if ($line -match '^status:\s*(.+)$') { return $Matches[1].Trim() } }
    throw 'Unable to determine GIPA status.'
}

function New-StyleFile([string]$Destination) {
    Write-Host ''
    Write-Host 'The GDD has unresolved art direction. Enter the approved style:' -ForegroundColor Yellow
    $rendering = Read-Host 'Rendering style [premium stylized 3D]'
    if ([string]::IsNullOrWhiteSpace($rendering)) { $rendering = 'premium stylized 3D' }
    $tone = Read-Host 'Tone / mood'
    $camera = Read-Host 'Gameplay viewpoint [top-down or high-angle]'
    if ([string]::IsNullOrWhiteSpace($camera)) { $camera = 'top-down or high-angle' }
    $palette = Read-Host 'Primary palette and accents'
    $lighting = Read-Host 'Lighting style'
    $constraints = Read-Host 'Additional visual constraints [optional]'
    $summary = @($rendering, ('Tone: ' + $tone), ('Gameplay viewpoint: ' + $camera), ('Palette: ' + $palette), ('Lighting: ' + $lighting))
    if (-not [string]::IsNullOrWhiteSpace($constraints)) { $summary += ('Additional constraints: ' + $constraints) }
    $yaml = @('schema_version: 1','game:','  title: resolved-from-gdd','visual_style:','  status: resolved','  summary:')
    foreach ($item in $summary) { $safe = $item.Replace("'", "''"); $yaml += ("    - '" + $safe + "'") }
    $yaml += @('mobile_readability:','  enabled: true','  avoid_micro_detail: true','  silhouette_priority: high','sources:','  - type: user','    reference: interactive approved style','confidence: explicit')
    $yaml | Set-Content -LiteralPath $Destination -Encoding UTF8
    return $Destination
}

if (-not (Get-Command gipa -ErrorAction SilentlyContinue)) { throw 'gipa is not available. Activate the GIPA .venv or install the package first.' }

$GddPath = Read-ExistingFile 'GDD path (.md/.txt/.docx/.pdf)' $GddPath
$GameRoot = Read-ExistingDirectory 'Game root path' $GameRoot
if ([string]::IsNullOrWhiteSpace($OutputDir)) { $OutputDir = Join-Path $GameRoot '.ai-assets' }
if ([string]::IsNullOrWhiteSpace($FinalPromptPath)) { $FinalPromptPath = Join-Path $OutputDir 'prompts.md' }

if (Test-Path -LiteralPath $OutputDir) {
    $remove = $ForceResetOutput
    if (-not $remove) { $answer = Read-Host 'Existing .ai-assets found. Remove it? [Y/n]'; $remove = [string]::IsNullOrWhiteSpace($answer) -or $answer -match '^(y|yes)$' }
    if ($remove) { Remove-Item -LiteralPath $OutputDir -Recurse -Force }
}

$planArgs = @('plan','--gdd',$GddPath,'--game-root',$GameRoot,'--out',$OutputDir)
if (-not [string]::IsNullOrWhiteSpace($StyleFile)) { $StyleFile = Read-ExistingFile 'Approved style YAML' $StyleFile; $planArgs += @('--style-file',$StyleFile) }
Invoke-Gipa -GipaArgs $planArgs -AllowedExitCodes @(0,1) | Out-Null
$status = Get-GipaStatus (Join-Path $OutputDir 'STATE.yaml')

if ($status -eq 'blocked') {
    Write-Host ''
    Write-Host 'GIPA is blocked by unresolved art direction.' -ForegroundColor Yellow
    $choice = Read-Host 'Enter existing style YAML path, or press ENTER to create one interactively'
    if ([string]::IsNullOrWhiteSpace($choice)) { $StyleFile = New-StyleFile (Join-Path $GameRoot 'APPROVED_ART_STYLE.yaml') }
    else { $StyleFile = Read-ExistingFile 'Approved style YAML' $choice }
    $planArgs = @('plan','--gdd',$GddPath,'--game-root',$GameRoot,'--style-file',$StyleFile,'--out',$OutputDir)
    Invoke-Gipa -GipaArgs $planArgs -AllowedExitCodes @(0) | Out-Null
    $status = Get-GipaStatus (Join-Path $OutputDir 'STATE.yaml')
}

if ($status -ne 'awaiting_human_approval') { throw "Unexpected GIPA status: $status" }

$review = Join-Path $OutputDir 'ASSET_REVIEW.md'
$manifest = Join-Path $OutputDir 'ASSET_MANIFEST.yaml'
Write-Host ''
Write-Host '===== ASSET REVIEW =====' -ForegroundColor Cyan
Get-Content -LiteralPath $review
Write-Host ''
Write-Host "Manifest: $manifest"
try { Invoke-Item $review; Invoke-Item $manifest } catch {}
Read-Host 'Review/edit the manifest, then press ENTER to validate it'
Invoke-Gipa -GipaArgs @('validate','manifest',$manifest) | Out-Null
$approval = Read-Host 'Approve this inventory and create prompts? [Y/n]'
if (-not ([string]::IsNullOrWhiteSpace($approval) -or $approval -match '^(y|yes)$')) { Write-Host 'Stopped before prompt generation.'; exit 0 }

Invoke-Gipa -GipaArgs @('approve','--out',$OutputDir) | Out-Null
Invoke-Gipa -GipaArgs @('prompts','--out',$OutputDir) | Out-Null
Invoke-Gipa -GipaArgs @('validate-project','--out',$OutputDir) | Out-Null

$jsonName = switch ($Provider) { 'ChatGPT' { 'chatgpt_images.json' } 'Gemini' { 'gemini_images.json' } default { 'canonical.json' } }
$pack = Get-Content -LiteralPath (Join-Path $OutputDir ('prompts\' + $jsonName)) -Raw | ConvertFrom-Json
$records = @($pack.prompts)
if ($Variant -ne 'All') { $records = @($records | Where-Object { $_.variant -eq $Variant }) }
if ($records.Count -eq 0) { throw 'No matching prompts were generated.' }

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('# Game Image Generation Prompts')
$lines.Add('')
$lines.Add('- Provider: **' + $Provider + '**')
$lines.Add('- Mode: **' + $PromptMode + '**')
$lines.Add('- Variant: **' + $Variant + '**')
$lines.Add('- GDD: ' + $GddPath)
$lines.Add('- Game root: ' + $GameRoot)
$lines.Add('')

if ($PromptMode -in @('Individual','Both')) {
    $lines.Add('## Individual prompts'); $lines.Add('')
    foreach ($record in $records) {
        $lines.Add('### ' + $record.asset_id + ' - Variant ' + $record.variant)
        $lines.Add('')
        $lines.Add('Target: **' + $record.production_dimensions.width + ' x ' + $record.production_dimensions.height + ' px**')
        $lines.Add(''); $lines.Add('~~~text'); $lines.Add([string]$record.text); $lines.Add('~~~'); $lines.Add('')
    }
}

if ($PromptMode -in @('Batch','Both')) {
    $lines.Add('## Batch prompts'); $lines.Add('')
    foreach ($group in @($records | Group-Object category,variant | Sort-Object Name)) {
        $first = $group.Group | Select-Object -First 1
        $lines.Add('### ' + $first.category + ' - Variant ' + $first.variant)
        $lines.Add(''); $lines.Add('~~~text')
        $lines.Add('Generate these as a cohesive asset batch. Generate each asset as a separate image; do not create an atlas or collage.')
        $lines.Add('')
        $index = 1
        foreach ($record in $group.Group) { $lines.Add('ASSET ' + $index + ' - ' + $record.asset_id); $lines.Add(''); $lines.Add([string]$record.text); $lines.Add(''); $index++ }
        $lines.Add('~~~'); $lines.Add('')
    }
}

$parent = Split-Path $FinalPromptPath -Parent
if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$lines | Set-Content -LiteralPath $FinalPromptPath -Encoding UTF8

Write-Host ''
Write-Host 'GIPA workflow completed successfully.' -ForegroundColor Green
Write-Host ('Final prompts: ' + $FinalPromptPath) -ForegroundColor Green