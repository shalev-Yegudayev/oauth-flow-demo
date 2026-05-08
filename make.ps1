param(
    [Parameter(Position = 0)]
    [string]$Target = "help"
)

$ErrorActionPreference = "Stop"

$Python = "backend\venv\Scripts\python.exe"
$Pytest = "backend\venv\Scripts\pytest.exe"
$Ruff   = "backend\venv\Scripts\ruff.exe"

$BackendSources = @("app/", "main.py", "deps.py", "config.py")

function Invoke-Step {
    param([string]$Label, [scriptblock]$Block)
    Write-Host "`n==> $Label" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Label" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

switch ($Target) {

    "help" {
        Write-Host @"

Usage: .\make.ps1 <target>

  install          Install all dependencies (backend + frontend)
  install-backend  pip install -r backend/requirements.txt
  install-frontend npm ci in frontend/

  lint             Lint backend (ruff) + frontend (eslint)
  lint-backend     ruff check on backend source files
  lint-frontend    eslint via npm run lint

  format           Auto-format backend with ruff

  test             Run all tests
  test-backend     pytest -x -q

  verify           lint + test  (CI gate)
"@
    }

    "install" {
        .\make.ps1 install-backend
        .\make.ps1 install-frontend
    }

    "install-backend" {
        Invoke-Step "pip upgrade" { & $Python -m pip install --upgrade pip }
        Invoke-Step "pip install" { & $Python -m pip install -r backend/requirements.txt }
    }

    "install-frontend" {
        Invoke-Step "npm ci" { Push-Location frontend; npm ci; Pop-Location }
    }

    "lint" {
        .\make.ps1 lint-backend
        .\make.ps1 lint-frontend
    }

    "lint-backend" {
        Invoke-Step "ruff check" {
            Push-Location backend
            & $PSScriptRoot\$Ruff check @BackendSources
            Pop-Location
        }
    }

    "lint-frontend" {
        Invoke-Step "eslint" { Push-Location frontend; npm run lint; Pop-Location }
    }

    "format" {
        .\make.ps1 format-backend
    }

    "format-backend" {
        Invoke-Step "ruff format" {
            Push-Location backend
            & $PSScriptRoot\$Ruff format @BackendSources
            & $PSScriptRoot\$Ruff check --fix @BackendSources
            Pop-Location
        }
    }

    "test" {
        .\make.ps1 test-backend
    }

    "test-backend" {
        Invoke-Step "pytest" {
            Push-Location backend
            & $PSScriptRoot\$Pytest -x -q
            # exit 5 = no tests collected — warn but don't fail
            if ($LASTEXITCODE -eq 5) {
                Write-Host "WARNING: no tests found yet" -ForegroundColor Yellow
                $global:LASTEXITCODE = 0
            }
            Pop-Location
        }
    }

    "verify" {
        .\make.ps1 lint
        .\make.ps1 test
    }

    default {
        Write-Host "Unknown target: $Target. Run .\make.ps1 help" -ForegroundColor Red
        exit 1
    }
}
