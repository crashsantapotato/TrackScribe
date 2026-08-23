function Get-Sha256Hex {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not [System.IO.File]::Exists($fullPath)) {
        throw "SHA-256 input file not found: $fullPath"
    }

    $stream = $null
    $sha256 = $null
    try {
        $stream = [System.IO.File]::OpenRead($fullPath)
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        $bytes = $sha256.ComputeHash($stream)
        return ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
    }
    catch {
        throw "Could not compute SHA-256 for '$fullPath': $($_.Exception.Message)"
    }
    finally {
        if ($null -ne $sha256) {
            $sha256.Dispose()
        }
        if ($null -ne $stream) {
            $stream.Dispose()
        }
    }
}

function Assert-FileSha256 {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $normalizedExpected = $Expected.Trim().ToLowerInvariant()
    $actual = Get-Sha256Hex -Path $fullPath
    if ($actual -ne $normalizedExpected) {
        Remove-Item -LiteralPath $fullPath -Force -ErrorAction SilentlyContinue
        throw (
            "$Description failed SHA-256 verification. " +
            "Path: $fullPath. Expected: $normalizedExpected. Actual: $actual."
        )
    }
}
