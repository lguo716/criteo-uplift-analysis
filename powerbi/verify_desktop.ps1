param([int]$DesktopPid, [switch]$Refresh)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$process = Get-CimInstance -ClassName Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object { $_.ParentProcessId -eq $DesktopPid }
if (@($process).Count -ne 1) { throw 'Expected exactly one child analysis engine for the specified Desktop PID.' }
$directoryMatch = [regex]::Match($process.CommandLine, '-s "([^"]+)"')
if (-not $directoryMatch.Success) { throw 'No returned analysis workspace path.' }
$portFile = Join-Path $directoryMatch.Groups[1].Value 'msmdsrv.port.txt'
$endpointPort = [int]([System.IO.File]::ReadAllText($portFile,[System.Text.Encoding]::Unicode).Trim())
Add-Type -Path 'D:\ATools\bin\Microsoft.PowerBI.Amo.Core.dll'
Add-Type -Path 'D:\ATools\bin\Microsoft.PowerBI.Tabular.dll'
Add-Type -Path 'D:\ATools\bin\Microsoft.PowerBI.AdomdClient.dll'
$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect("localhost:$endpointPort")
try {
    if ($server.Databases.Count -ne 1) { throw 'Expected exactly one project database.' }
    $database = $server.Databases[0]
    if ($null -eq $database.Model.Tables.Find('experiment_summary') -or $null -eq $database.Model.Tables.Find('budget_strategies')) { throw 'Endpoint is not the Criteo project.' }
    if ($Refresh) {
        # Process CSV-backed partitions. This does not reload report files or replace model definitions.
        $database.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
        $database.Model.SaveChanges()
    }
    $connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$endpointPort")
    $connection.Open()
    try {
        $queries = [ordered]@{
            visit = 'EVALUATE CALCULATETABLE(ROW("n",[Sample N],"treatment_n",[Treatment N],"control_n",[Control N],"treatment_rate",[Treatment Rate],"control_rate",[Control Rate],"ate",[ATE],"lower",[ATE Lower],"upper",[ATE Upper],"selected",[Selected Model],"budget",[Selected Budget],"uplift",[Uplift Budget Gain],"response",[Response Budget Gain],"advantage",[Uplift Budget Advantage],"cost",[Normalized Cost]),dim_outcome[outcome]="visit")'
            conversion = 'EVALUATE CALCULATETABLE(ROW("n",[Sample N],"ate",[ATE],"selected",[Selected Model],"uplift",[Uplift Budget Gain],"response",[Response Budget Gain]),dim_outcome[outcome]="conversion")'
            budget50 = 'EVALUATE CALCULATETABLE(ROW("budget",[Selected Budget],"uplift",[Uplift Budget Gain],"cost",[Normalized Cost]),dim_outcome[outcome]="visit",dim_budget[budget_fraction]=0.5)'
            budget0 = 'EVALUATE CALCULATETABLE(ROW("budget",[Selected Budget],"uplift",[Uplift Budget Gain],"cost",[Normalized Cost]),dim_outcome[outcome]="visit",dim_budget[budget_fraction]=0.0)'
            budget100 = 'EVALUATE CALCULATETABLE(ROW("budget",[Selected Budget],"uplift",[Uplift Budget Gain],"response",[Response Budget Gain],"advantage",[Uplift Budget Advantage],"cost",[Normalized Cost]),dim_outcome[outcome]="visit",dim_budget[budget_fraction]=1.0)'
            interval = 'EVALUATE CALCULATETABLE(ROW("points",[ATE Points],"interval",[ATE Interval]),dim_outcome[outcome]="visit")'
            counts = 'EVALUATE ROW("experiment_rows",COUNTROWS(experiment_summary),"group_rows",COUNTROWS(experiment_groups),"curve_rows",COUNTROWS(uplift_curves),"strategy_rows",COUNTROWS(budget_strategies),"decile_rows",COUNTROWS(decile_profiles))'
            models = 'EVALUATE SUMMARIZECOLUMNS(dim_model[model_label],"qini",[Test Qini],"qini_low",[Test Qini Lower],"qini_high",[Test Qini Upper])'
        }
        $results = [ordered]@{}
        foreach ($entry in $queries.GetEnumerator()) {
            $command = $connection.CreateCommand()
            $command.CommandText = $entry.Value
            $reader = $command.ExecuteReader()
            $rows = @()
            while ($reader.Read()) {
                $row = [ordered]@{}
                for ($i=0; $i -lt $reader.FieldCount; $i++) { $row[$reader.GetName($i)] = if ($reader.IsDBNull($i)) { $null } else { $reader.GetValue($i) } }
                $rows += [pscustomobject]$row
            }
            $reader.Close()
            $results[$entry.Key] = $rows
        }
        $checks = @()
        function Assert-Number($Group,$Field,$Expected,$Tolerance=0.0000001) {
            $actual = $results[$Group][0].PSObject.Properties["[$Field]"].Value
            $passed = $null -ne $actual -and [Math]::Abs([double]$actual - [double]$Expected) -le $Tolerance
            $script:checks += [pscustomobject]@{check="$Group.$Field";actual=$actual;expected=$Expected;passed=$passed}
            if (-not $passed) { throw "DAX mismatch: $Group.$Field; actual=$actual expected=$Expected" }
        }
        function Number($Value) { return [double]::Parse($Value, [System.Globalization.CultureInfo]::InvariantCulture) }
        $experiments = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports\tables\experiment_summary.csv')
        $strategies = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports\tables\budget_strategies.csv')
        foreach ($outcome in @('visit','conversion')) {
            $row = $experiments | Where-Object { $_.outcome -eq $outcome }
            Assert-Number $outcome 'n' (Number $row.n)
            Assert-Number $outcome 'ate' (Number $row.ate)
            $target = $strategies | Where-Object { $_.outcome -eq $outcome -and $_.strategy -eq 'uplift' -and $_.budget_fraction -eq '0.2' }
            $baseline = $strategies | Where-Object { $_.outcome -eq $outcome -and $_.strategy -eq 'response' -and $_.budget_fraction -eq '0.2' }
            Assert-Number $outcome 'uplift' (Number $target.incremental_per_10000)
            Assert-Number $outcome 'response' (Number $baseline.incremental_per_10000)
        }
        $visit = $experiments | Where-Object { $_.outcome -eq 'visit' }
        foreach ($pair in @(@('treatment_n','n_treatment'),@('control_n','n_control'),@('treatment_rate','rate_treatment'),@('control_rate','rate_control'),@('lower','ci_lower'),@('upper','ci_upper'))) { Assert-Number 'visit' $pair[0] (Number $visit.($pair[1])) }
        Assert-Number 'visit' 'budget' 0.2
        Assert-Number 'visit' 'cost' 2000
        Assert-Number 'budget50' 'budget' 0.5
        Assert-Number 'budget50' 'cost' 5000
        $target50 = $strategies | Where-Object { $_.outcome -eq 'visit' -and $_.strategy -eq 'uplift' -and $_.budget_fraction -eq '0.5' }
        Assert-Number 'budget50' 'uplift' (Number $target50.incremental_per_10000)
        Assert-Number 'budget0' 'budget' 0
        Assert-Number 'budget0' 'uplift' 0
        Assert-Number 'budget0' 'cost' 0
        Assert-Number 'budget100' 'budget' 1
        Assert-Number 'budget100' 'cost' 10000
        $target100 = $strategies | Where-Object { $_.outcome -eq 'visit' -and $_.strategy -eq 'uplift' -and (Number $_.budget_fraction) -eq 1 }
        Assert-Number 'budget100' 'uplift' (Number $target100.incremental_per_10000)
        Assert-Number 'budget100' 'response' (Number $target100.incremental_per_10000)
        Assert-Number 'budget100' 'advantage' 0
        Assert-Number 'interval' 'points' ((Number $visit.ate) * 100)
        foreach ($pair in @(@('experiment_rows','experiment_summary'),@('group_rows','experiment_groups'),@('curve_rows','uplift_curves'),@('strategy_rows','budget_strategies'),@('decile_rows','decile_profiles'))) { Assert-Number 'counts' $pair[0] @(Import-Csv -LiteralPath (Join-Path $projectRoot ('reports\tables\'+$pair[1]+'.csv'))).Count }
        $output = [ordered]@{status='PASS';desktop_pid=$DesktopPid;engine_port=$endpointPort;refreshed=[bool]$Refresh;checked_at=(Get-Date).ToString('s');results=$results;checks=$checks}
        [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'desktop_verification.json'),($output|ConvertTo-Json -Depth 10),[System.Text.UTF8Encoding]::new($false))
        Write-Output ("Desktop DAX: " + $checks.Count + '/' + $checks.Count + ' passed')
    } finally { $connection.Close() }
} finally { $server.Disconnect() }
