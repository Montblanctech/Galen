# Full-reference overnight chain (Galen already lemmatized with morph).
# Resumable: extract is cheap to re-run; lemmatize uses --skip-existing.
# NativeCommandError on stderr warnings must NOT abort the overnight chain
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$log = "outputs/_full_reference_pipeline.log"

function Step($name, $cmd) {
    $msg = "=== $name === $(Get-Date -Format o)"
    Write-Host $msg
    Add-Content -Path $log -Value $msg
    cmd /c "$cmd >> `"$log`" 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "Step failed: $name (exit $LASTEXITCODE)" }
}

Add-Content -Path $log -Value "`n=== RESUME $(Get-Date -Format o) ==="
# Extract is already done; re-run is idempotent and fast enough if needed.
# Skip extract on resume when extracted_text already has many files:
$nTxt = @(Get-ChildItem "data\reference_corpus\extracted_text\*.txt" -ErrorAction SilentlyContinue).Count
if ($nTxt -lt 100) {
    Step "02 extract reference" "python -u pipeline/02_extract.py --include-reference"
} else {
    Write-Host "=== skip extract ($nTxt reference txt already present) ==="
    Add-Content -Path $log -Value "=== skip extract ($nTxt reference txt already present) ==="
}

Step "03 lemmatize reference only" "python -u pipeline/03_lemmatize.py --include-reference --skip-galen --skip-existing"
Step "04 frequency" "python -u pipeline/04_frequency.py"
Step "05 keyness" "python -u pipeline/05_keyness.py"
Step "06 lsj" "python -u pipeline/06_lsj_crossref.py"
Step "07 punchlist" "python -u pipeline/07_punchlist.py"
Step "08 qc" "python -u pipeline/08_qc.py"
Write-Host "=== DONE === $(Get-Date -Format o)"
Add-Content -Path $log -Value "=== DONE === $(Get-Date -Format o)"
