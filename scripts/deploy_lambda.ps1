# Deploy Lambda function for CTI Scraper
# Usage: .\scripts\deploy_lambda.ps1

$ErrorActionPreference = "Stop"

# Configuration
$PROJECT_ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LAMBDA_PACKAGE = "$PROJECT_ROOT\lambda_package.zip"
$FUNCTION_NAME = "cti-scraper-dev-scraper"  # Adjust based on your terraform config

Write-Host "=" * 50
Write-Host "CTI Scraper Lambda Deployment"
Write-Host "=" * 50

# Step 1: Build the package
Write-Host "`nStep 1: Building Lambda package..."
python "$PROJECT_ROOT\scripts\build_lambda.py"

if (-not (Test-Path $LAMBDA_PACKAGE)) {
    Write-Error "Lambda package not found at $LAMBDA_PACKAGE"
    exit 1
}

$size = (Get-Item $LAMBDA_PACKAGE).Length / 1MB
Write-Host "Package size: $([math]::Round($size, 2)) MB"

# Step 2: Update Lambda function code
Write-Host "`nStep 2: Updating Lambda function..."
try {
    aws lambda update-function-code `
        --function-name $FUNCTION_NAME `
        --zip-file "fileb://$LAMBDA_PACKAGE" `
        --output json | ConvertFrom-Json | Select-Object FunctionName, LastModified, CodeSize

    Write-Host "Lambda function updated successfully!"
} catch {
    Write-Error "Failed to update Lambda function: $_"
    exit 1
}

# Step 3: Wait for update to complete
Write-Host "`nStep 3: Waiting for function to be ready..."
aws lambda wait function-updated --function-name $FUNCTION_NAME
Write-Host "Function is ready!"

# Step 4: Optional - Test invocation
$testInvoke = Read-Host "`nWould you like to test the function? (y/n)"
if ($testInvoke -eq "y") {
    Write-Host "`nInvoking Lambda function..."
    $payload = '{"action": "scrape", "sources": ["microsoft-security-blog"]}'

    aws lambda invoke `
        --function-name $FUNCTION_NAME `
        --payload $payload `
        --cli-binary-format raw-in-base64-out `
        response.json

    Write-Host "`nResponse:"
    Get-Content response.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
    Remove-Item response.json
}

Write-Host "`n" + "=" * 50
Write-Host "Deployment complete!"
Write-Host "=" * 50
