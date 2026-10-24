<#
Read db/contracts.mdb back through the 32-bit "Microsoft Access Driver (*.mdb)" ODBC driver,
a different access path from the ADO/DAO calls that built it, and write outputs/*.csv:

  q*.csv            every saved select, totals, parameter, crosstab and exception query
  AgencyFYSummary   the table the append query filled
  table_counts.csv  row count per table
  integrity.csv     referential-integrity probes (each must be rejected by the engine)

Python (tests/, scripts/reconcile.py) compares these files with totals computed from the CSVs.
#>
param(
    [string]$DbPath = (Join-Path $PSScriptRoot '..\db\contracts.mdb'),
    [string]$OutDir = (Join-Path $PSScriptRoot '..\outputs')
)
$ErrorActionPreference = 'Stop'

if ([Environment]::Is64BitProcess) {
    & "$env:windir\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -File $PSCommandPath -DbPath $DbPath -OutDir $OutDir
    exit $LASTEXITCODE
}

[Threading.Thread]::CurrentThread.CurrentCulture = [Globalization.CultureInfo]::InvariantCulture
New-Item -ItemType Directory -Force $OutDir | Out-Null
$cn = New-Object System.Data.Odbc.OdbcConnection("Driver={Microsoft Access Driver (*.mdb)};Dbq=$([IO.Path]::GetFullPath($DbPath));")
$cn.Open()

function Export-Query([string]$sql, [string]$name, [object[]]$params = @()) {
    $cmd = $cn.CreateCommand()
    $cmd.CommandText = $sql
    foreach ($p in $params) { $null = $cmd.Parameters.AddWithValue("p$($cmd.Parameters.Count)", $p) }
    $table = New-Object System.Data.DataTable
    $null = (New-Object System.Data.Odbc.OdbcDataAdapter($cmd)).Fill($table)
    $table.Rows | ForEach-Object {
        $row = $_; $o = [ordered]@{}
        foreach ($c in $table.Columns) {
            $v = $row[$c]
            $o[$c.ColumnName] = $(if ($v -is [datetime]) { $v.ToString('yyyy-MM-dd') } else { $v })
        }
        [pscustomobject]$o
    } | Export-Csv (Join-Path $OutDir "$name.csv") -NoTypeInformation -Encoding UTF8
    Write-Host ("{0,-28} {1,5} rows" -f $name, $table.Rows.Count)
}

foreach ($q in 'qryActionDetail', 'qtotRecipientObligations', 'qtotAwardsPerAgency',
               'qxtbAgencyByFY', 'qexcAwardsWithoutBaseAction') {
    Export-Query "SELECT * FROM [$q]" $q
}
# A parameter query is called like a stored procedure; ? markers bind [Start Date], [End Date].
Export-Query '{CALL qparActionsByDateRange(?, ?)}' 'qparActionsByDateRange_FY2025' @(
    [datetime]'2024-10-01', [datetime]'2025-09-30')
Export-Query 'SELECT * FROM AgencyFYSummary' 'AgencyFYSummary'

$counts = foreach ($t in 'Agency', 'Recipient', 'NAICS', 'ActionType', 'Award', 'ContractAction', 'AgencyFYSummary') {
    $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT Count(*) FROM [$t]"
    [pscustomobject]@{ table = $t; rows = [int]$cmd.ExecuteScalar() }
}
$counts | Export-Csv (Join-Path $OutDir 'table_counts.csv') -NoTypeInformation -Encoding UTF8

# Each probe should fail. Run inside a transaction and roll back, so a probe that wrongly
# succeeds cannot change the database.
$probes = [ordered]@{
    orphan_action   = "INSERT INTO ContractAction VALUES ('PROBE', 'NO_SUCH_AWARD', '0', #2025-01-01#, '0', 1)"
    delete_parent   = "DELETE FROM Award WHERE AwardKey = (SELECT TOP 1 AwardKey FROM ContractAction)"
    duplicate_key   = "INSERT INTO Agency SELECT TOP 1 * FROM Agency"
    null_required   = "INSERT INTO Recipient (RecipientUEI, RecipientName) VALUES ('PROBE', NULL)"
}
$integrity = foreach ($name in $probes.Keys) {
    $tx = $cn.BeginTransaction()
    $cmd = $cn.CreateCommand(); $cmd.Transaction = $tx; $cmd.CommandText = $probes[$name]
    try { $null = $cmd.ExecuteNonQuery(); $rejected = $false; $msg = 'accepted' }
    catch { $rejected = $true; $msg = $_.Exception.InnerException.Message -replace '\s+', ' ' }
    $tx.Rollback()
    [pscustomobject]@{ probe = $name; rejected = $rejected; message = $msg }
}
$integrity | Export-Csv (Join-Path $OutDir 'integrity.csv') -NoTypeInformation -Encoding UTF8
$integrity | Format-Table -AutoSize | Out-String | Write-Host
$cn.Close()
