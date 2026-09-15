# Run in Windows PowerShell as Administrator after WSL starts.
param([Parameter(Mandatory=$true)][string]$LanAddress, [Parameter(Mandatory=$true)][string]$Subnet, [string]$Distro = '')
$ErrorActionPreference = 'Stop'
$wslArgs = @()
if ($Distro) { $wslArgs += @('-d', $Distro) }
$wslArgs += @('--', 'hostname', '-I')
$addresses = & "$env:SystemRoot\System32\wsl.exe" @wslArgs
$wslAddress = ($addresses.Trim() -split '\s+')[0]
if ($wslAddress -notmatch '^\d+\.\d+\.\d+\.\d+$') { throw 'Cannot detect WSL IPv4 address' }
& "$env:SystemRoot\System32\netsh.exe" interface portproxy add v4tov4 "listenaddress=$LanAddress" listenport=7860 "connectaddress=$wslAddress" connectport=7860
if ($LASTEXITCODE -ne 0) { throw 'portproxy setup failed; run as Administrator' }
Get-NetFirewallRule -Name 'YuE2-Studio-LAN-7860' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name 'YuE2-Studio-LAN-7860' -DisplayName 'YuE2 Studio LAN TCP 7860' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 7860 -LocalAddress $LanAddress -RemoteAddress $Subnet -Profile Any | Out-Null
Write-Host "Ready: http://${LanAddress}:7860/ -> ${wslAddress}:7860"
