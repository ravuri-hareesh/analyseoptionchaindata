# Start OptEazy Databases (MySQL and MongoDB)

$mysqlBase = "C:\Users\ravur\Downloads\opteazy\db_persist\mysql"
$mysqlData = "$mysqlBase\data"
$mongoBase = "C:\Users\ravur\Downloads\opteazy\db_persist\mongodb"
$mongoData = "$mongoBase\data"

# Ensure log directories exist in persist
$mysqlLogDir = "$mysqlBase\log"
$mongoLogDir = "$mongoBase\log"
New-Item -ItemType Directory -Path $mysqlLogDir -Force | Out-Null
New-Item -ItemType Directory -Path $mongoLogDir -Force | Out-Null

# 0. KILL ZOMBIE PROCESSES (Release locks on ibdata1 and log files)
Write-Host "Cleaning up existing database processes..." -ForegroundColor Yellow
Stop-Process -Name "mysqld" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "mongod" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 1. Initialize MySQL if needed
if (-not (Test-Path $mysqlData)) {
    Write-Host "Initializing MySQL data directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $mysqlData -Force | Out-Null
    mysqld --initialize-insecure --datadir=$mysqlData
}

# 2. Initialize MongoDB if needed
if (-not (Test-Path $mongoData)) {
    Write-Host "Creating MongoDB data directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $mongoData -Force | Out-Null
}

# 3. Start MySQL in background
Write-Host "Starting MySQL (Port 3306)..." -ForegroundColor Cyan
# Using explicit log paths to avoid permission issues in the apps folder
Start-Process "mysqld" -ArgumentList "--datadir=$mysqlData", "--console", "--log-error=$mysqlLogDir\error.log" -NoNewWindow -PassThru

# 4. Start MongoDB in background
Write-Host "Starting MongoDB (Port 27017)..." -ForegroundColor Cyan
# Using explicit log path to avoid FileNotOpen errors in apps folder
Start-Process "mongod" -ArgumentList "--dbpath=$mongoData", "--logpath=$mongoLogDir\mongod.log", "--logappend" -NoNewWindow -PassThru

Write-Host "Databases are starting up. Please wait about 10-15 seconds for them to be ready." -ForegroundColor Green
