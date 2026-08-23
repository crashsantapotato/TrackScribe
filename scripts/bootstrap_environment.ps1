function Invoke-EnvironmentSelfCheck {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExecutable,
        [Parameter(Mandatory = $true)][string]$CheckerPath,
        [Parameter(Mandatory = $true)][string]$ExpectedPythonVersion,
        [Parameter(Mandatory = $true)]$Definition
    )

    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        return [pscustomobject]@{
            Success = $false
            ExitCode = -1
            StdOut = ""
            StdErr = "Python executable is missing: $PythonExecutable"
        }
    }

    $specification = [ordered]@{
        name = $Definition.Name
        python_version = $ExpectedPythonVersion
        imports = @($Definition.Imports)
        versions = $Definition.Versions
    }
    $json = $specification | ConvertTo-Json -Depth 6 -Compress
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
    $quotedChecker = '"' + $CheckerPath.Replace('"', '\"') + '"'

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PythonExecutable
    $startInfo.Arguments = "$quotedChecker --spec-base64 $payload"
    $checkerDirectory = [System.IO.Path]::GetDirectoryName($CheckerPath)
    $startInfo.WorkingDirectory = [System.IO.Path]::GetFullPath(
        (Join-Path $checkerDirectory "..")
    )
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        [void]$process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $exitCode = $process.ExitCode
    }
    catch {
        $stdout = ""
        $stderr = $_.Exception.ToString()
        $exitCode = -1
    }
    finally {
        $process.Dispose()
    }

    return [pscustomobject]@{
        Success = $exitCode -eq 0
        ExitCode = $exitCode
        StdOut = $stdout
        StdErr = $stderr
    }
}

function Write-EnvironmentSelfCheckOutput {
    param([Parameter(Mandatory = $true)]$Result)

    foreach ($value in @($Result.StdOut, $Result.StdErr)) {
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Write-Host $value.TrimEnd()
        }
    }
}
