# Start/reuse the LOCAL lab. Never reset a database, ledger or existing product.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:PATHEXT -notmatch '(^|;)\.EXE(;|$)') { $env:PATHEXT = '.COM;.EXE;.BAT;.CMD;' + $env:PATHEXT }
Set-Location -LiteralPath $PSScriptRoot
function Invoke-Docker {
    $result = & docker.exe @args
    if ($LASTEXITCODE -ne 0) { throw 'Docker operation failed; existing data preserved.' }
    return $result
}
Invoke-Docker version --format '{{.Server.Version}}'
Write-Output 'Inspecting existing containers...'
$names = @(Invoke-Docker ps -a --format '{{.Names}}')
if ($names -notcontains 'revolv-db') {
    $dbPassword = [guid]::NewGuid().ToString('N')
    Invoke-Docker run -d --name revolv-db --restart unless-stopped -e POSTGRES_USER=odoo -e "POSTGRES_PASSWORD=$dbPassword" -e POSTGRES_DB=postgres postgres:15
}
Write-Output 'Inspecting PostgreSQL...'
$db = (Invoke-Docker inspect revolv-db | ConvertFrom-Json)[0]
$dbPassword = ($db.Config.Env | Where-Object { $_.StartsWith('POSTGRES_PASSWORD=') }).Substring(18)
if ($db.State.Status -ne 'running') { Invoke-Docker start revolv-db }
if (@(Invoke-Docker network ls --format '{{.Name}}') -notcontains 'revolv-lab') { Invoke-Docker network create revolv-lab }
if ($db.NetworkSettings.Networks.PSObject.Properties.Name -notcontains 'revolv-lab') { Invoke-Docker network connect revolv-lab revolv-db }
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    & docker.exe exec revolv-db pg_isready -U odoo | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw 'PostgreSQL did not become ready.' }
$names = @(Invoke-Docker ps -a --format '{{.Names}}')
$volumeArgs = @()
if ($names -contains 'revolv-odoo') {
    $old = (Invoke-Docker inspect revolv-odoo | ConvertFrom-Json)[0]
    if ($old.Config.Cmd -contains 'dfvd') {
        $savedName = 'revolv-odoo-stopped-' + (Get-Date -Format yyyyMMddHHmmss)
        Invoke-Docker rename revolv-odoo $savedName
        $volumeArgs = @('--volumes-from', $savedName)
        $names = @(Invoke-Docker ps -a --format '{{.Names}}')
    }
}
if ($volumeArgs.Count -eq 0 -and $names -notcontains 'revolv-odoo') {
    $volumeArgs = @('-v','revolv-odoo-data:/var/lib/odoo')
}
# Only the system database catalogue is queried here; no stock SQL is used.
Write-Output 'Checking local test database...'
$dbExists = Invoke-Docker exec revolv-db psql -U odoo -d postgres -Atc "SELECT datname FROM pg_database WHERE datname='revolv_test'"
if (-not $dbExists) {
    Invoke-Docker run --rm --network revolv-lab @volumeArgs -e HOST=revolv-db -e USER=odoo -e "PASSWORD=$dbPassword" odoo:19.0 odoo -d revolv_test -i stock --without-demo=all --stop-after-init
}
if ($names -notcontains 'revolv-odoo') {
    Invoke-Docker run -d --name revolv-odoo --restart unless-stopped --network revolv-lab @volumeArgs -p 127.0.0.1:8069:8069 -e HOST=revolv-db -e USER=odoo -e "PASSWORD=$dbPassword" odoo:19.0 odoo -d revolv_test '--db-filter=^revolv_test$' --no-database-list
} else {
    $existing = (Invoke-Docker inspect revolv-odoo | ConvertFrom-Json)[0]
    $port = $existing.HostConfig.PortBindings.'8069/tcp'
    if ($existing.Config.Image -ne 'odoo:19.0' -or $port[0].HostIp -ne '127.0.0.1') {
        throw 'Existing Odoo configuration differs; preserve and inspect it before reuse.'
    }
    if ($existing.State.Status -ne 'running') { Invoke-Docker start revolv-odoo }
}
# Generate LOCAL-only credentials once. Never print the password or put it in a ZIP.
if (-not (Test-Path -LiteralPath '.local_credentials.json')) {
    $localPassword = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $quotedPassword = ConvertTo-Json -InputObject $localPassword -Compress
    $script = "env.ref('base.user_admin').write({'password': $quotedPassword})" + [Environment]::NewLine + 'env.cr.commit()' + [Environment]::NewLine + "print('LOCAL_ADMIN_PASSWORD_CONFIGURED')"
    $script | & docker.exe exec -i revolv-odoo odoo shell -d revolv_test --db_host revolv-db --db_user odoo --db_password $dbPassword --no-http
    if ($LASTEXITCODE -ne 0) { throw 'Local password setup failed; inspect before continuing.' }
    @{password=$localPassword} | ConvertTo-Json | Set-Content -LiteralPath '.local_credentials.json' -Encoding UTF8
}
Write-Output 'Verifying fixture without reset...'
$probe = "import json,os,runpy; os.environ['ODOO_PASSWORD']=json.load(open('.local_credentials.json',encoding='utf-8-sig'))['password']; runpy.run_path('setup_product.py',run_name='__main__')"
& py -3.14 -c $probe
if ($LASTEXITCODE -ne 0) { throw 'Local fixture verification failed; existing stock preserved.' }
Write-Output 'Local lab ready. Existing stock and ledger were preserved.'
