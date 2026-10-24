<#
Build db/contracts.mdb (Access 2000-2003 format) from data/clean/*.csv with the Jet 4.0 engine.

  ADOX   creates the empty .mdb file
  ADO    runs the Jet DDL in sql/schema.sql and loads the CSVs with parameterized INSERTs
  DAO    saves sql/queries/*.sql as QueryDefs (the native Access query objects) and runs
         the append query once

Jet 4.0 and DAO 3.6 are 32-bit only, so a 64-bit shell relaunches this script under
32-bit Windows PowerShell. Nothing is installed and no settings are changed.
#>
param(
    [string]$OutPath = (Join-Path $PSScriptRoot '..\db\contracts.mdb'),
    [string]$DataDir = (Join-Path $PSScriptRoot '..\data\clean')
)
$ErrorActionPreference = 'Stop'

if ([Environment]::Is64BitProcess) {
    & "$env:windir\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -File $PSCommandPath -OutPath $OutPath -DataDir $DataDir
    exit $LASTEXITCODE
}

[Threading.Thread]::CurrentThread.CurrentCulture = [Globalization.CultureInfo]::InvariantCulture
$SqlDir = Join-Path $PSScriptRoot '..\sql'
$OutPath = [IO.Path]::GetFullPath($OutPath)
New-Item -ItemType Directory -Force (Split-Path $OutPath) | Out-Null
if (Test-Path $OutPath) { Remove-Item $OutPath }

# 1. Empty database. Engine Type 5 = Jet 4.0 (.mdb that Access 2000 and later open).
$connStr = "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$OutPath"
$cat = New-Object -ComObject ADOX.Catalog
$null = $cat.Create("$connStr;Jet OLEDB:Engine Type=5")
$cat.ActiveConnection.Close()

# 2. Tables, keys and relationships.
$cn = New-Object -ComObject ADODB.Connection
$cn.Open($connStr)
$ddl = (Get-Content (Join-Path $SqlDir 'schema.sql') -Raw) -replace '(?m)^\s*--.*$', ''
foreach ($stmt in $ddl -split ';') {
    if ($stmt.Trim()) { $null = $cn.Execute($stmt) }
}

# 3. Load parents before children so every foreign key already has its parent row.
$tables = 'Agency', 'Recipient', 'NAICS', 'ActionType', 'Award', 'ContractAction'
$cn.BeginTrans() | Out-Null
foreach ($table in $tables) {
    $rows = @(Import-Csv (Join-Path $DataDir "$table.csv"))
    $rs = $cn.Execute("SELECT * FROM [$table] WHERE 1 = 0")   # read column types from the table
    $fields = @(foreach ($f in $rs.Fields) { [pscustomobject]@{ Name = $f.Name; Type = $f.Type; Size = $f.DefinedSize } })
    $rs.Close()

    $cmd = New-Object -ComObject ADODB.Command
    $cmd.ActiveConnection = $cn
    $cols = ($fields | ForEach-Object { "[$($_.Name)]" }) -join ', '
    $marks = (@('?') * $fields.Count) -join ', '
    $cmd.CommandText = "INSERT INTO [$table] ($cols) VALUES ($marks)"
    foreach ($f in $fields) {
        $size = [Math]::Max(1, [Math]::Min($f.Size, 255))
        $null = $cmd.Parameters.Append($cmd.CreateParameter($f.Name, $f.Type, 1, $size))
    }
    foreach ($row in $rows) {
        for ($i = 0; $i -lt $fields.Count; $i++) {
            $v = $row.($fields[$i].Name)
            # Pass text and let ADO convert to the parameter's type (dates are ISO yyyy-MM-dd).
            # PowerShell's COM binder rejects typed values here after it has seen strings.
            $cmd.Parameters.Item($i).Value = $(if ($v -eq '') { [DBNull]::Value } else { $v })
        }
        $null = $cmd.Execute()
    }
    Write-Host ("{0,-15} {1,6} rows" -f $table, $rows.Count)
}
$cn.CommitTrans()
$cn.Close()

# 4. Saved queries. qry* first: the other queries are stacked on qryActionDetail.
$dbe = New-Object -ComObject DAO.DBEngine.36
$db = $dbe.OpenDatabase($OutPath)
$files = Get-ChildItem (Join-Path $SqlDir 'queries') -Filter *.sql |
    Sort-Object @{ Expression = { -not $_.BaseName.StartsWith('qry') } }, BaseName
foreach ($file in $files) {
    $null = $db.CreateQueryDef($file.BaseName, (Get-Content $file.FullName -Raw))
    Write-Host "query  $($file.BaseName)"
}

# 5. Run the append query once (128 = dbFailOnError: roll back and raise on any error).
$append = $db.QueryDefs.Item('qappAgencyFYSummary')
$append.Execute(128)
Write-Host "qappAgencyFYSummary appended $($append.RecordsAffected) rows"
$db.Close()
Write-Host "built $OutPath"
