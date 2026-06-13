# deploy_k8s.ps1
# Automates building the Docker image and deploying it to local Kubernetes (Docker Desktop)

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Stock Analyst App Local Kubernetes Deployer   " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# 1. Load .env variables
if (-not (Test-Path ".env")) {
    Write-Error "Error: .env file not found in current directory."
}

Write-Host "[1/5] Loading environment variables from .env..." -ForegroundColor Yellow
$envVars = @{}
Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) {
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            # Remove optional quotes
            if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            if ($value.StartsWith("'") -and $value.EndsWith("'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $envVars[$key] = $value
        }
    }
}

$sfUser = $envVars["SNOWFLAKE_USER"]
$sfPass = $envVars["SNOWFLAKE_PASSWORD"]
$sfAcct = $envVars["SNOWFLAKE_ACCOUNT"]

if (-not $sfUser -or -not $sfPass -or -not $sfAcct) {
    Write-Error "Error: Missing SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, or SNOWFLAKE_ACCOUNT in .env"
}

# 2. Base64 encode credentials
Write-Host "[2/5] Base64 encoding Snowflake credentials..." -ForegroundColor Yellow
$userB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sfUser))
$passB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sfPass))
$acctB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sfAcct))

# 3. Generate secrets manifest from template
Write-Host "[3/5] Generating k8s/secrets_generated.yaml..." -ForegroundColor Yellow
if (-not (Test-Path "k8s/secrets.yaml")) {
    Write-Error "Error: k8s/secrets.yaml template not found."
}

$secretTemplate = Get-Content "k8s/secrets.yaml" -Raw
$secretGenerated = $secretTemplate.Replace("YOUR_BASE64_USER", $userB64)
$secretGenerated = $secretGenerated.Replace("YOUR_BASE64_PASSWORD", $passB64)
$secretGenerated = $secretGenerated.Replace("YOUR_BASE64_ACCOUNT", $acctB64)

$secretGenerated | Out-File -FilePath "k8s/secrets_generated.yaml" -Encoding utf8

# 4. Build Docker Image
Write-Host "[4/5] Building Docker image 'stocks-analyst:latest'..." -ForegroundColor Yellow
docker build -t stocks-analyst:latest .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed."
}

# 5. Deploy to Kubernetes
Write-Host "[5/5] Deploying resources to local Kubernetes cluster..." -ForegroundColor Yellow
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets_generated.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

if ($LASTEXITCODE -ne 0) {
    Write-Error "Kubernetes deployment failed."
}

Write-Host "`n===============================================" -ForegroundColor Green
Write-Host " Deployment Completed Successfully! " -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host "To monitor deployment, run:" -ForegroundColor Gray
Write-Host "  kubectl get pods -l app=stocks-analyst" -ForegroundColor Cyan
Write-Host "  kubectl logs -f deployment/stocks-analyst-deployment" -ForegroundColor Cyan
Write-Host "`nAccess the application in your browser at:" -ForegroundColor Gray
Write-Host "  http://localhost:30501" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Green
