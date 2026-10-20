param([switch]$Watch)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:NODE_PATH = (Join-Path $projectRoot "node_modules")

$arguments = @(
    (Join-Path $projectRoot "node_modules\tailwindcss\lib\cli.js"),
    "-i", (Join-Path $projectRoot "dashboard\static\dashboard\src\app.css"),
    "-o", (Join-Path $projectRoot "dashboard\static\dashboard\css\app.css"),
    "--minify"
)

if ($Watch) {
    $arguments += "--watch"
}

& node @arguments
exit $LASTEXITCODE
