$ErrorActionPreference = 'Stop'
$repo = 'sinanaghdi/retailsignal'
$description = 'RetailSignal: e-commerce revenue, customer retention, and market performance analytics portfolio project'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI (gh) is not installed. Install it from https://cli.github.com/ and rerun this script.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git is not installed or is not on PATH.'
}
if (-not (Test-Path 'README.md') -or -not (Test-Path 'requirements.txt')) {
    throw 'Run this script from the extracted RetailSignal project root (the folder containing README.md and requirements.txt).'
}

Write-Warning 'The canonical repository already exists at https://github.com/sinanaghdi/retailsignal.'
Write-Warning 'For normal work, clone the repository first and work inside that clone; do not initialize a separate history and attempt to push it.'
Write-Host 'If you are using the published remote, start with:' -ForegroundColor Cyan
Write-Host '  git clone https://github.com/sinanaghdi/retailsignal.git'
Write-Host '  Set-Location retailsignal'
Write-Host '  # Copy/modify project files here, then: git add <files>; git commit -m "describe the change"; git push'
Write-Host ''
Write-Host 'This legacy bootstrap script intentionally refuses to create a parallel history.' -ForegroundColor Yellow
throw 'No action taken. Clone the existing repository and make commits on top of its current main branch.'
