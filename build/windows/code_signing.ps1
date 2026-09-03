# Get file to be signed from first argument
$file = $args[0]

if (-not $file -or -not (Test-Path $file)) {
    Write-Error "Target file '$file' does not exist or was not specified."
    exit 1
}

if (-not $signtool) {
    $sdkPaths = @(
        "${env:ProgramFiles(x86)}\Windows Kits",
        "${env:ProgramFiles}\Windows Kits"
    ) | Where-Object { Test-Path $_ }

    if ($sdkPaths) {
        $signtool = (Get-ChildItem -Path $sdkPaths -Filter "signtool.exe" -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\' } |
            Sort-Object -Property LastWriteTime -Descending |
            Select-Object -First 1).FullName
    }
}

if (-not $signtool) {
    Write-Error "signtool.exe not found in standard Windows SDK locations or PATH."
    exit 1
}

# Display the path to the signtool
Write-Host "Current directory: $(Get-Location)"
Write-Host "Using signtool: $signtool"
Write-Host "Signing file: $file"
Write-Host "Using certificate thumbprint: ${env:CODESIGNING_THUMBPRINT}"

# Sign the given file
& $signtool sign /debug /fd sha256 /sha1 ${env:CODESIGNING_THUMBPRINT} /tr http://ts.harica.gr /td sha256 $file