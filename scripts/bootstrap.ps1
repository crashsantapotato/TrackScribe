[CmdletBinding()]
param(
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

. (Join-Path $PSScriptRoot "bootstrap_hash.ps1")
. (Join-Path $PSScriptRoot "bootstrap_environment.ps1")

$TrackScribeRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$BootstrapRoot = Join-Path $TrackScribeRoot ".bootstrap"
$UvPath = Join-Path $BootstrapRoot "uv.exe"
$ManagedPythonRoot = Join-Path $BootstrapRoot "python"
$StatePath = Join-Path $BootstrapRoot "setup-state.json"
$VersionCheckerPath = Join-Path $PSScriptRoot "bootstrap_versions.py"
$UvVersion = "0.12.5"
$PythonVersion = "3.12.14"
$AmtRevision = "c210559a481ed22fc72af2f54e020250f9aabae1"
$FfmpegVersion = "8.1.2"
$UvArchiveUrl = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
$AmtArchiveUrl = "https://github.com/anime-song/instrument-agnostic-amt/archive/$AmtRevision.zip"
$FfmpegArchiveUrl = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-$FfmpegVersion-essentials_build.zip"
$UvArchiveSha256 = "4c4d49d8738847d9b71ba319e49a5688c93eac0fe6204b1df24e98528dddf39a"
$AmtArchiveSha256 = "eff3abd93ec953f637964f55c77e4a7a382052fc59cb34ef5bdbec5d0723ccee"
$FfmpegArchiveSha256 = "db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec"
$MegaModelSlug = "roformer-model-bs-roformer-mvsep-mega-53-stems"
$MegaCheckpointName = "mvsep_mega_model_bs_roformer_53_stems_v1.ckpt"

$EnvironmentDefinitions = @(
    [ordered]@{
        Name = "Core environment"
        Directory = ".venv"
        Requirements = "requirements/core.txt"
        Imports = @("audio_separator", "adtof_pytorch", "librosa", "torch")
        Torch = $true
        Versions = [ordered]@{
            "audio-separator" = "0.44.5"
            "adtof-pytorch" = "0.1.0"
            "torch" = "2.13.0+cu130"
            "torchvision" = "0.28.0"
            "onnxruntime-gpu" = "1.29.0"
        }
    },
    [ordered]@{
        Name = "UI environment"
        Directory = ".venv-ui"
        Requirements = "requirements/ui.txt"
        Imports = @("PySide6")
        Torch = $false
        Versions = [ordered]@{
            "PySide6" = "6.11.2"
        }
    },
    [ordered]@{
        Name = "Bass environment"
        Directory = ".venv-bass"
        Requirements = "requirements/bass.txt"
        Imports = @("hf_midi_transcription", "torch")
        Torch = $true
        Versions = [ordered]@{
            "hf-midi-transcription" = "0.1.1"
            "piano-transcription-inference" = "0.1.0"
            "torch" = "2.13.0+cu130"
        }
    },
    [ordered]@{
        Name = "Piano environment"
        Directory = ".venv-piano"
        Requirements = "requirements/piano.txt"
        Imports = @("transkun", "torch")
        Torch = $true
        Versions = [ordered]@{
            "transkun" = "2.0.1"
            "torch" = "2.13.0+cu130"
            "torchaudio" = "2.11.0"
        }
    },
    [ordered]@{
        Name = "Mega environment"
        Directory = ".venv-mega"
        Requirements = "requirements/mega.txt"
        Imports = @("bs_roformer", "torch")
        Torch = $true
        Versions = [ordered]@{
            "bs-roformer-infer" = "0.1.6"
            "torch" = "2.13.0+cu130"
        }
    },
    [ordered]@{
        Name = "AMT environment"
        Directory = ".venv-amt"
        Requirements = "requirements/amt.txt"
        Imports = @("torch", "torchaudio", "mido", "soundfile")
        Torch = $true
        Versions = [ordered]@{
            "torch" = "2.13.0+cu130"
            "torchaudio" = "2.11.0+cu130"
            "dlchordx" = "1.0.5"
        }
    }
)

function Write-Status {
    param(
        [Parameter(Mandatory = $true)][string]$State,
        [Parameter(Mandatory = $true)][string]$Message
    )
    Write-Host ("[{0}] {1}" -f $State, $Message)
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )
    & $Executable @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

function Get-EnvironmentPython {
    param([Parameter(Mandatory = $true)][string]$Directory)
    return Join-Path $TrackScribeRoot "$Directory\Scripts\python.exe"
}

function Get-EnvironmentSelfCheck {
    param([Parameter(Mandatory = $true)]$Definition)
    $python = Get-EnvironmentPython $Definition.Directory
    return Invoke-EnvironmentSelfCheck `
        -PythonExecutable $python `
        -CheckerPath $VersionCheckerPath `
        -ExpectedPythonVersion $PythonVersion `
        -Definition $Definition
}

function Test-EnvironmentRuntime {
    param([Parameter(Mandatory = $true)]$Definition)
    $python = Get-EnvironmentPython $Definition.Directory
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        return $false
    }
    & $python -c "import sys; assert sys.version_info[:3] == (3, 12, 14)" *> $null
    return $LASTEXITCODE -eq 0
}

function Get-RequirementsHash {
    param([Parameter(Mandatory = $true)]$Definition)
    $path = Join-Path $TrackScribeRoot $Definition.Requirements
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing environment definition: $path"
    }
    return Get-Sha256Hex -Path $path
}

function Read-SetupState {
    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    }
    catch {
        Write-Status "WARN" "Ignoring unreadable setup state; real executables will be checked."
        return $null
    }
}

function Get-StateRequirementsHash {
    param(
        $State,
        [Parameter(Mandatory = $true)][string]$Directory
    )
    if ($null -eq $State) {
        return $null
    }
    $environmentsProperty = $State.PSObject.Properties["environments"]
    if ($null -eq $environmentsProperty -or $null -eq $environmentsProperty.Value) {
        return $null
    }
    $property = $environmentsProperty.Value.PSObject.Properties[$Directory]
    if ($null -eq $property -or $null -eq $property.Value) {
        return $null
    }
    $hashProperty = $property.Value.PSObject.Properties["requirements_sha256"]
    if ($null -eq $hashProperty) {
        return $null
    }
    return [string]$hashProperty.Value
}

function Get-UvVersion {
    param([Parameter(Mandatory = $true)][string]$Executable)
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $null
    }
    $value = & $Executable --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return [string]$value
}

function Ensure-Uv {
    $localVersion = Get-UvVersion $UvPath
    if ($localVersion -match "\b$([regex]::Escape($UvVersion))\b") {
        Write-Status "OK" "uv $UvVersion"
        return
    }
    New-Item -ItemType Directory -Path $BootstrapRoot -Force | Out-Null
    $systemUv = Get-Command uv.exe -ErrorAction SilentlyContinue
    if ($null -ne $systemUv) {
        $systemVersion = & $systemUv.Source --version 2>$null
        if ($LASTEXITCODE -eq 0 -and $systemVersion -match "\b$([regex]::Escape($UvVersion))\b") {
            Copy-Item -LiteralPath $systemUv.Source -Destination $UvPath -Force
            Write-Status "OK" "Copied version-validated uv $UvVersion to .bootstrap."
            return
        }
    }
    $archive = Join-Path $BootstrapRoot "uv.zip"
    $extract = Join-Path $BootstrapRoot "uv-download"
    Write-Status "GET" "Downloading portable uv $UvVersion"
    Invoke-WebRequest -Uri $UvArchiveUrl -OutFile $archive -UseBasicParsing
    Assert-FileSha256 $archive $UvArchiveSha256 "uv archive"
    if (Test-Path -LiteralPath $extract) {
        Remove-Item -LiteralPath $extract -Recurse -Force
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $extract -Force
    $downloaded = Get-ChildItem -LiteralPath $extract -Filter uv.exe -Recurse | Select-Object -First 1
    if ($null -eq $downloaded) {
        throw "The uv archive did not contain uv.exe."
    }
    Copy-Item -LiteralPath $downloaded.FullName -Destination $UvPath -Force
    Remove-Item -LiteralPath $archive -Force
    Remove-Item -LiteralPath $extract -Recurse -Force
    $installedVersion = Get-UvVersion $UvPath
    if ($installedVersion -notmatch "\b$([regex]::Escape($UvVersion))\b") {
        throw "Downloaded uv failed its version check."
    }
    Write-Status "OK" "uv $UvVersion"
}

function Ensure-ManagedPython {
    New-Item -ItemType Directory -Path $ManagedPythonRoot -Force | Out-Null
    $env:UV_PYTHON_INSTALL_DIR = $ManagedPythonRoot
    Invoke-Checked $UvPath @(
        "python", "install", $PythonVersion,
        "--install-dir", $ManagedPythonRoot,
        "--managed-python", "--no-bin", "--no-registry"
    ) "Managed Python installation"
    Write-Status "OK" "Managed Python $PythonVersion"
}

function Ensure-Environment {
    param(
        [Parameter(Mandatory = $true)]$Definition,
        $PreviousState
    )
    $environmentPath = Join-Path $TrackScribeRoot $Definition.Directory
    $python = Get-EnvironmentPython $Definition.Directory
    $requirements = Join-Path $TrackScribeRoot $Definition.Requirements
    $requirementsHash = Get-RequirementsHash $Definition
    $previousHash = Get-StateRequirementsHash $PreviousState $Definition.Directory
    $initialCheck = Get-EnvironmentSelfCheck $Definition
    $healthy = $initialCheck.Success
    $definitionChanged = $null -ne $previousHash -and $previousHash -ne $requirementsHash
    if ($healthy -and -not $definitionChanged) {
        Write-Status "OK" $Definition.Name
        Write-EnvironmentSelfCheckOutput $initialCheck
        return $requirementsHash
    }
    if (-not $healthy) {
        Write-Status "FIX" "$($Definition.Name): creating or repairing isolated environment"
        $arguments = @(
            "venv", $environmentPath,
            "--python", $PythonVersion,
            "--managed-python"
        )
        if (Test-Path -LiteralPath $environmentPath) {
            $arguments += "--clear"
        }
        Invoke-Checked $UvPath $arguments "$($Definition.Name) creation"
    }
    else {
        Write-Status "SYNC" "$($Definition.Name): dependency definition changed"
    }
    Invoke-Checked $UvPath @(
        "pip", "sync", $requirements,
        "--python", $python,
        "--index-strategy", "unsafe-best-match",
        "--strict"
    ) "$($Definition.Name) dependency sync"
    $finalCheck = Get-EnvironmentSelfCheck $Definition
    if (-not $finalCheck.Success) {
        Write-Status "ERROR" "Environment self-check failed: $($Definition.Name)"
        Write-EnvironmentSelfCheckOutput $finalCheck
        throw "$($Definition.Name) failed its Python/import self-check with exit code $($finalCheck.ExitCode)."
    }
    Write-Status "OK" $Definition.Name
    Write-EnvironmentSelfCheckOutput $finalCheck
    return $requirementsHash
}

function Ensure-AmtSource {
    $target = Join-Path $TrackScribeRoot "tools\instrument-agnostic-amt"
    $infer = Join-Path $target "infer.py"
    $marker = Join-Path $target ".trackscribe-revision"
    if (Test-Path -LiteralPath $infer -PathType Leaf) {
        if ((Test-Path -LiteralPath $marker -PathType Leaf) -and
            ((Get-Content -LiteralPath $marker -Raw).Trim() -eq $AmtRevision)) {
            Write-Status "OK" "Instrument-Agnostic AMT source $AmtRevision"
        }
        else {
            Write-Status "OK" "Existing Instrument-Agnostic AMT source (revision marker unavailable)"
        }
        return
    }
    $toolsRoot = Join-Path $TrackScribeRoot "tools"
    $archive = Join-Path $BootstrapRoot "instrument-agnostic-amt.zip"
    $extract = Join-Path $BootstrapRoot "instrument-agnostic-amt-download"
    New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
    Write-Status "GET" "Downloading Instrument-Agnostic AMT source $AmtRevision"
    Invoke-WebRequest -Uri $AmtArchiveUrl -OutFile $archive -UseBasicParsing
    Assert-FileSha256 $archive $AmtArchiveSha256 "Instrument-Agnostic AMT source archive"
    if (Test-Path -LiteralPath $extract) {
        Remove-Item -LiteralPath $extract -Recurse -Force
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $extract -Force
    $source = Get-ChildItem -LiteralPath $extract -Directory | Select-Object -First 1
    if ($null -eq $source -or -not (Test-Path -LiteralPath (Join-Path $source.FullName "infer.py"))) {
        throw "The Instrument-Agnostic AMT archive is incomplete."
    }
    if (Test-Path -LiteralPath $target) {
        $backup = "$target.broken.$(Get-Date -Format yyyyMMddHHmmss)"
        Move-Item -LiteralPath $target -Destination $backup
        Write-Status "WARN" "Moved incomplete AMT source to $backup"
    }
    Move-Item -LiteralPath $source.FullName -Destination $target
    Set-Content -LiteralPath $marker -Value $AmtRevision -Encoding ascii
    Remove-Item -LiteralPath $archive -Force
    Remove-Item -LiteralPath $extract -Recurse -Force
    Write-Status "OK" "Instrument-Agnostic AMT source $AmtRevision"
}

function Find-WorkingFfmpeg {
    $local = Join-Path $TrackScribeRoot "tools\ffmpeg\bin\ffmpeg.exe"
    $candidates = @($local)
    $system = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($null -ne $system) {
        $candidates += $system.Source
    }
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        & $candidate -version *> $null
        if ($LASTEXITCODE -eq 0) {
            return $candidate
        }
    }
    return $null
}

function Ensure-Ffmpeg {
    $working = Find-WorkingFfmpeg
    if ($null -ne $working) {
        Write-Status "OK" "FFmpeg: $working"
        return $working
    }
    $destination = Join-Path $TrackScribeRoot "tools\ffmpeg\bin"
    $archive = Join-Path $BootstrapRoot "ffmpeg.zip"
    $extract = Join-Path $BootstrapRoot "ffmpeg-download"
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Write-Status "GET" "Downloading portable FFmpeg $FfmpegVersion"
    Invoke-WebRequest -Uri $FfmpegArchiveUrl -OutFile $archive -UseBasicParsing
    Assert-FileSha256 $archive $FfmpegArchiveSha256 "FFmpeg archive"
    if (Test-Path -LiteralPath $extract) {
        Remove-Item -LiteralPath $extract -Recurse -Force
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $extract -Force
    foreach ($name in @("ffmpeg.exe", "ffprobe.exe")) {
        $source = Get-ChildItem -LiteralPath $extract -Filter $name -Recurse | Select-Object -First 1
        if ($null -eq $source) {
            throw "The FFmpeg archive did not contain $name."
        }
        Copy-Item -LiteralPath $source.FullName -Destination (Join-Path $destination $name) -Force
    }
    Remove-Item -LiteralPath $archive -Force
    Remove-Item -LiteralPath $extract -Recurse -Force
    $working = Find-WorkingFfmpeg
    if ($null -eq $working) {
        throw "Downloaded FFmpeg failed its version check."
    }
    Write-Status "OK" "FFmpeg: $working"
    return $working
}

function Ensure-Models {
    $separatorModels = Join-Path $TrackScribeRoot "models\audio-separator"
    $megaModels = Join-Path $TrackScribeRoot "models\mega53"
    New-Item -ItemType Directory -Path $separatorModels -Force | Out-Null
    New-Item -ItemType Directory -Path $megaModels -Force | Out-Null
    $megaCheckpoint = Join-Path $megaModels "$MegaModelSlug\$MegaCheckpointName"
    if (-not (Test-Path -LiteralPath $megaCheckpoint -PathType Leaf)) {
        $megaPython = Get-EnvironmentPython ".venv-mega"
        Write-Status "GET" "Downloading official Mega53 checkpoint (large download)"
        Invoke-Checked $megaPython @(
            "-m", "bs_roformer.download",
            "--model", $MegaModelSlug,
            "--output-dir", $megaModels,
            "--models-only"
        ) "Mega53 checkpoint download"
    }
    if (-not (Test-Path -LiteralPath $megaCheckpoint -PathType Leaf)) {
        throw "Mega53 downloader completed but the configured checkpoint is missing: $megaCheckpoint"
    }
    Write-Status "OK" "Mega53 checkpoint"
    Write-Status "INFO" "htdemucs_ft, HF transcription, and Agnostic AMT checkpoints download from their official upstreams on first use."
    Write-Status "OK" "ADTOF and Transkun weights are installed with their pinned packages."
}

function Test-CudaBackends {
    $unavailable = @()
    foreach ($definition in $EnvironmentDefinitions | Where-Object { $_.Torch }) {
        $python = Get-EnvironmentPython $definition.Directory
        $result = & $python -c "import torch; print('available' if torch.cuda.is_available() else 'unavailable')" 2>$null
        if ($LASTEXITCODE -ne 0 -or ([string]$result).Trim() -ne "available") {
            $unavailable += $definition.Directory
        }
    }
    if ($unavailable.Count -gt 0) {
        Write-Status "WARN" "CUDA-capable NVIDIA GPU was not detected in: $($unavailable -join ', ')"
        Write-Host "       TrackScribe GPU backends may not work. No global CUDA Toolkit was installed."
        return $false
    }
    Write-Status "OK" "CUDA is available in all GPU backend environments"
    return $true
}

function Show-DryRunPlan {
    Write-Host "TrackScribe bootstrap dry run"
    Write-Host "Root: $TrackScribeRoot"
    Write-Host "Portable uv: $UvPath (version $UvVersion)"
    Write-Host "Managed Python: $ManagedPythonRoot (CPython $PythonVersion)"
    Write-Host "Fallback FFmpeg: $FfmpegVersion essentials build (SHA-256 pinned)"
    Write-Host ""
    foreach ($definition in $EnvironmentDefinitions) {
        # Keep -DryRun structural and quick: full imports/version checks happen
        # during normal setup and can initialize heavyweight GPU libraries.
        $state = if (Test-EnvironmentRuntime $definition) { "OK" } else { "PLAN" }
        Write-Status $state "$($definition.Name): $($definition.Directory) <- $($definition.Requirements)"
    }
    $amtInfer = Join-Path $TrackScribeRoot "tools\instrument-agnostic-amt\infer.py"
    Write-Status $(if (Test-Path -LiteralPath $amtInfer) { "OK" } else { "PLAN" }) "Instrument-Agnostic AMT source $AmtRevision"
    $ffmpeg = Find-WorkingFfmpeg
    Write-Status $(if ($null -ne $ffmpeg) { "OK" } else { "PLAN" }) $(if ($null -ne $ffmpeg) { "FFmpeg: $ffmpeg" } else { "Download portable FFmpeg to tools\ffmpeg" })
    $mega = Join-Path $TrackScribeRoot "models\mega53\$MegaModelSlug\$MegaCheckpointName"
    Write-Status $(if (Test-Path -LiteralPath $mega) { "OK" } else { "PLAN" }) "Official Mega53 checkpoint"
    Write-Host ""
    Write-Host "Dry run complete. No files were changed and nothing was downloaded."
}

try {
    if ($DryRun) {
        Show-DryRunPlan
        exit 0
    }

    Write-Host "Root: $TrackScribeRoot"
    Write-Host ""
    $previousState = Read-SetupState
    Ensure-Uv
    Ensure-ManagedPython
    Ensure-AmtSource

    $environmentState = [ordered]@{}
    foreach ($definition in $EnvironmentDefinitions) {
        $hash = Ensure-Environment $definition $previousState
        $environmentState[$definition.Directory] = [ordered]@{
            requirements_sha256 = $hash
            python = $PythonVersion
            checked_at = (Get-Date).ToString("o")
        }
    }

    $ffmpeg = Ensure-Ffmpeg
    Ensure-Models
    $cudaAvailable = Test-CudaBackends
    $state = [ordered]@{
        schema_version = 1
        completed_at = (Get-Date).ToString("o")
        root = $TrackScribeRoot
        uv_version = $UvVersion
        python_version = $PythonVersion
        ffmpeg_bootstrap_version = $FfmpegVersion
        environments = $environmentState
        ffmpeg = $ffmpeg
        amt_revision = $AmtRevision
        cuda_available = $cudaAvailable
    }
    New-Item -ItemType Directory -Path $BootstrapRoot -Force | Out-Null
    $state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatePath -Encoding utf8
    Write-Host ""
    Write-Host "TrackScribe is ready."
    if (-not $cudaAvailable) {
        Write-Host "Setup completed with a CUDA warning; GPU stages may not run."
    }
}
catch {
    Write-Host ""
    Write-Status "ERROR" $_.Exception.Message
    Write-Host "Run setup.bat again after resolving the issue. Healthy components will be reused."
    exit 1
}
