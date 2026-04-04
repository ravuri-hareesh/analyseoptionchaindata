# Provision Databases using Scoop (with Winget fallback for MongoDB)

Write-Host "--- Provisioning OptEazy Databases ---" -ForegroundColor Cyan

# 1. Ensure Buckets
Write-Host "[1/3] Preparing Scoop Buckets..."
scoop bucket add extras 2>$null
scoop bucket add nonportable 2>$null

# 2. Install/Update MySQL
Write-Host "[2/3] Installing/Updating MySQL..."
if (scoop list | Select-String "mysql") {
    Write-Host "MySQL already installed via Scoop. Updating..."
    scoop update mysql
} else {
    Write-Host "Installing MySQL via Scoop..."
    scoop install mysql
}

# 3. Install/Update MongoDB
Write-Host "[3/3] Installing/Updating MongoDB..."
$mongoInstalled = (scoop list | Select-String -Pattern "mongodb|percona-server-mongodb")
if ($mongoInstalled) {
    Write-Host "MongoDB already found in Scoop. Updating..."
    scoop update mongodb 2>$null
} else {
    Write-Host "Searching specifically for MongoDB in known buckets..."
    $mongoSearch = scoop search mongodb | Select-String "mongodb"
    if ($mongoSearch) {
        Write-Host "Found MongoDB in Scoop. Installing..."
        scoop install mongodb
    } else {
        Write-Host "MongoDB not found in Scoop. Falling back to Winget..." -ForegroundColor Yellow
        winget install MongoDB.Server --silent --accept-package-agreements --accept-source-agreements
    }
}

Write-Host "--- Provisioning Complete ---" -ForegroundColor Green
