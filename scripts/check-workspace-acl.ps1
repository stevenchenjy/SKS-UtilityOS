param([Parameter(Mandatory=$true)][string]$Directory)
$ErrorActionPreference = "Stop"
try {
    $Names = @("", "utilityos.sqlite3", "sources", "backups")
    foreach ($Name in $Names) {
        $Path = if ($Name) { Join-Path $Directory $Name } else { $Directory }
        if (-not (Test-Path -LiteralPath $Path)) { continue }
        $Item = Get-Item -LiteralPath $Path -Force
        if ($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            Write-Output "review_required"; exit 0
        }
        $Acl = Get-Acl -LiteralPath $Path
        $Rules = $Acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])
        foreach ($Rule in $Rules) {
            if ($Rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
                $Rule.IdentityReference.Value -in @("S-1-1-0", "S-1-5-11", "S-1-5-32-545")) {
                Write-Output "review_required"; exit 0
            }
        }
    }
    Write-Output "no_broad_acl_grants_found"
} catch {
    Write-Output "acl_check_unavailable"
}
