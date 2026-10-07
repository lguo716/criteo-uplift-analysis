param([int]$DesktopPid)
$ErrorActionPreference = 'Stop'
# Add two display-only items through TOM; never replace tables or report content.
$engine = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object { $_.ParentProcessId -eq $DesktopPid }
if (@($engine).Count -ne 1) { throw 'Expected one analysis engine owned by DesktopPid.' }
$match = [regex]::Match($engine.CommandLine, '-s "([^"]+)"')
if (-not $match.Success) { throw 'Missing returned workspace path.' }
$endpointPort = [int]([IO.File]::ReadAllText((Join-Path $match.Groups[1].Value 'msmdsrv.port.txt'),[Text.Encoding]::Unicode).Trim())
$desktop = Get-Process -Id $DesktopPid
$installDirectory = Split-Path $desktop.Path -Parent
Add-Type -Path (Join-Path $installDirectory 'Microsoft.PowerBI.Amo.Core.dll')
Add-Type -Path (Join-Path $installDirectory 'Microsoft.PowerBI.Tabular.dll')
$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect("localhost:$endpointPort")
try {
    if ($server.Databases.Count -ne 1) { throw 'Expected one project database.' }
    $model = $server.Databases[0].Model
    if ($null -eq $model.Tables.Find('experiment_summary') -or $null -eq $model.Tables.Find('budget_strategies')) { throw 'Not the Criteo project.' }
    $metrics = $model.Tables.Find('Metrics')
    if ($null -eq $metrics.Measures.Find('ATE Points')) {
        $displayMeasure = New-Object Microsoft.AnalysisServices.Tabular.Measure
        $displayMeasure.Name = 'ATE Points'
        $displayMeasure.Expression = '[ATE]*100'
        $displayMeasure.FormatString = '0.0000'
        $displayMeasure.DisplayFolder = '增量评估'
        $metrics.Measures.Add($displayMeasure)
    }
    if ($null -eq $metrics.Measures.Find('ATE Interval')) {
        $intervalMeasure = New-Object Microsoft.AnalysisServices.Tabular.Measure
        $intervalMeasure.Name = 'ATE Interval'
        $intervalMeasure.Expression = '"[" & FORMAT([ATE Lower]*100,"0.0000") & ", " & FORMAT([ATE Upper]*100,"0.0000") & "]"'
        $intervalMeasure.DisplayFolder = '增量评估'
        $metrics.Measures.Add($intervalMeasure)
    }
    $budget = $model.Tables.Find('dim_budget')
    $budget.Columns.Find('budget_label').SortByColumn = $budget.Columns.Find('budget_fraction')
    $model.SaveChanges()
    Write-Output 'Added point/interval displays and numeric budget label sorting.'
} finally { $server.Disconnect() }
