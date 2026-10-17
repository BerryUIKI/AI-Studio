"""Exercise the real Windows setup transport without changing system settings."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows setup transport"
)
HELPER = Path(__file__).resolve().parents[2] / "desktop-runtime/src/setup_network.ps1"
PAYLOAD = b"Berry synthetic runtime download fixture\x00\xff"


@pytest.fixture
def transport() -> Iterator[tuple[str, list[str]]]:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()
            self.wfile.write(PAYLOAD)

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def run_script(tmp_path: Path, body: str) -> str:
    script = tmp_path / "probe.ps1"
    script.write_text(
        "$ErrorActionPreference='Stop'\n"
        f". '{str(HELPER).replace(chr(39), chr(39) * 2)}'\n{body}\n",
        encoding="utf-8-sig",
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_explicit_proxy_routes_download_and_preserves_binary_hash(
    tmp_path: Path, transport: tuple[str, list[str]]
) -> None:
    proxy_url, requests = transport
    target = tmp_path / "runtime.bin"
    output = run_script(
        tmp_path,
        f"""
$proxy = New-Object Net.WebProxy('{proxy_url}')
Assert-BerryProxyReachable ([Uri]'{proxy_url}')
Save-BerryDownload ([Uri]'http://berry-fixture.invalid/runtime') '{target}' $proxy
Write-Output (Get-BerryFileHash '{target}')
""",
    )
    assert target.read_bytes() == PAYLOAD
    assert output == hashlib.sha256(PAYLOAD).hexdigest()
    assert requests == ["http://berry-fixture.invalid/runtime"]


def test_disabled_proxy_and_bypass_use_direct_connection(
    tmp_path: Path, transport: tuple[str, list[str]]
) -> None:
    url, requests = transport
    target = tmp_path / "direct.bin"
    run_script(
        tmp_path,
        f"""
$proxy = New-Object Net.WebProxy('http://127.0.0.1:1')
$proxy.BypassList = @('127\\.0\\.0\\.1')
if ($null -ne (Get-BerryProxyUri ([Uri]'{url}/direct') $proxy)) {{ throw 'Bypass ignored' }}
Save-BerryDownload ([Uri]'{url}/direct') '{target}' $proxy
Set-BerryPackageProxy $null
if ($env:HTTPS_PROXY) {{ throw 'Disabled proxy was retained' }}
""",
    )
    assert target.read_bytes() == PAYLOAD
    assert requests == ["/direct"]


def test_package_installer_receives_proxy_only_in_its_child_process(
    tmp_path: Path, transport: tuple[str, list[str]]
) -> None:
    url, _ = transport
    run_script(
        tmp_path,
        f"""
$proxy = New-Object Net.WebProxy('{url}')
Set-BerryPackageProxy $proxy
if ($env:HTTPS_PROXY -ne '{url}/') {{ throw 'Package proxy missing' }}
if ($env:NO_PROXY) {{ throw 'Package traffic bypassed the explicit proxy' }}
""",
    )


def test_unreachable_proxy_has_a_specific_failure(tmp_path: Path) -> None:
    output = run_script(
        tmp_path,
        """
$failed = $false
try { Assert-BerryProxyReachable ([Uri]'http://127.0.0.1:1') }
catch { $failed = $true }
if (-not $failed) { throw 'Unexpected connection' }
Write-Output 'proxy-unreachable'
""",
    )
    assert output == "proxy-unreachable"


def test_core_validation_survives_windows_powershell_argument_passing(
    tmp_path: Path,
) -> None:
    verification = HELPER.with_name("verify_core.py")
    python = sys.executable.replace("'", "''")
    prefix = sys.prefix.replace("'", "''")
    output = run_script(
        tmp_path,
        f"""
& '{python}' -I '{verification}' '{prefix}'
if ($LASTEXITCODE -ne 0) {{ throw 'Core validation failed' }}
Write-Output 'core-validated'
""",
    )
    assert output == "core-validated"
