# Read the current user's Windows Internet options; never change system settings.
$script:BerrySystemProxy = [Net.WebRequest]::GetSystemWebProxy()

function Get-BerryFileHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Get-BerryProxyUri([Uri]$Uri, [Net.IWebProxy]$Proxy = $script:BerrySystemProxy) {
    if ($null -eq $Proxy -or $Proxy.IsBypassed($Uri)) { return $null }
    $resolved = $Proxy.GetProxy($Uri)
    if ($resolved -eq $Uri) { return $null }
    return $resolved
}

function Assert-BerryProxyReachable([Uri]$ProxyUri) {
    if ($null -eq $ProxyUri) { return }
    $client = New-Object Net.Sockets.TcpClient
    try {
        if (-not $client.ConnectAsync($ProxyUri.Host, $ProxyUri.Port).Wait(3000) -or -not $client.Connected) {
            throw 'BERRY_PROXY_UNREACHABLE'
        }
    } finally { $client.Dispose() }
}

function Save-BerryDownload([Uri]$Uri, [string]$Destination, [Net.IWebProxy]$Proxy = $script:BerrySystemProxy) {
    $request = [Net.HttpWebRequest]::Create($Uri)
    $request.Proxy = $Proxy
    $request.Timeout = 180000
    $request.ReadWriteTimeout = 30000
    $response = $null
    $inputStream = $null
    $outputStream = $null
    try {
        $response = $request.GetResponse()
        $inputStream = $response.GetResponseStream()
        $outputStream = [IO.File]::Create($Destination)
        $inputStream.CopyTo($outputStream)
    } finally {
        if ($null -ne $outputStream) { $outputStream.Dispose() }
        if ($null -ne $inputStream) { $inputStream.Dispose() }
        if ($null -ne $response) { $response.Dispose() }
    }
}

function Set-BerryPackageProxy([Net.IWebProxy]$Proxy = $script:BerrySystemProxy) {
    # Requests/pip do not read Windows Internet options. Configure this child only.
    $index = Get-BerryProxyUri ([Uri]'https://pypi.org/simple/') $Proxy
    $files = Get-BerryProxyUri ([Uri]'https://files.pythonhosted.org/') $Proxy
    if ($null -ne $index -and $null -ne $files -and $index.AbsoluteUri -ne $files.AbsoluteUri) {
        throw 'BERRY_DISTINCT_PACKAGE_PROXIES'
    }
    $route = if ($null -ne $index) { $index } else { $files }
    Assert-BerryProxyReachable $route
    $env:HTTP_PROXY = if ($null -ne $route) { $route.AbsoluteUri } else { $null }
    $env:HTTPS_PROXY = $env:HTTP_PROXY
    $env:ALL_PROXY = $null
    $bypass = @()
    if ($null -eq $index) { $bypass += 'pypi.org' }
    if ($null -eq $files) { $bypass += 'files.pythonhosted.org' }
    $env:NO_PROXY = $bypass -join ','
}
