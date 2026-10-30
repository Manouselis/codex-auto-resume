import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_resume.protocol import find_codex
from auto_resume.websocket import LocalWebSocket, ProxyStream


class RuntimeDiscoveryTests(unittest.TestCase):
    def test_macos_app_binary_without_shell_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary = home / 'Applications/ChatGPT.app/Contents/Resources/codex'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'fixture')
            binary.chmod(0o755)
            with patch('auto_resume.protocol.sys.platform', 'darwin'), patch('auto_resume.protocol.Path.home', return_value=home), patch('auto_resume.protocol.shutil.which', return_value=None):
                self.assertEqual(find_codex(), str(binary))

    def test_windows_installer_binary_without_shell_path(self):
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            binary = local / 'Programs/OpenAI/Codex/bin/codex.exe'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'fixture')
            binary.chmod(0o755)
            with patch('auto_resume.protocol.sys.platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': str(local)}), patch('auto_resume.protocol.shutil.which', return_value=None):
                self.assertEqual(find_codex(), str(binary))

    def test_managed_runtime_without_shell_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary = home / 'packages/app-server-daemon/releases/0.166/bin/codex.exe'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'fixture')
            binary.chmod(0o755)
            with patch('auto_resume.protocol.sys.platform', 'win32'), patch.dict(os.environ, {'CODEX_HOME': str(home), 'LOCALAPPDATA': str(home)}), patch('auto_resume.protocol.Path.home', return_value=home), patch('auto_resume.protocol.shutil.which', return_value=None):
                self.assertEqual(find_codex(), str(binary))


class ProxyTransportTests(unittest.TestCase):
    def test_raw_proxy_performs_real_websocket_handshake_and_frame(self):
        # Real pipes/child process exercise byte framing, not a JSONL substitute.
        child = """
import sys,hashlib,base64
h=bytearray()
while not h.endswith(b'\\r\\n\\r\\n'):
 h.extend(sys.stdin.buffer.read(1))
key=[v.split(':',1)[1].strip() for v in h.decode().split('\\r\\n') if v.startswith('Sec-WebSocket-Key:')][0]
accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
sys.stdout.buffer.write(('HTTP/1.1 101 Switching Protocols\\r\\nUpgrade: websocket\\r\\nSec-WebSocket-Accept: '+accept+'\\r\\n\\r\\n').encode()+b'\\x81\\x02{}')
sys.stdout.buffer.flush()
sys.stdin.buffer.read()
"""
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'raw_proxy.py'
            script.write_text(child)
            real_popen = subprocess.Popen
            commands = []
            def start(command, **options):
                commands.append(command)
                options.pop('creationflags', None)
                return real_popen([sys.executable, '-u', str(script)], **options)
            with patch('auto_resume.websocket.sys.platform', 'win32'), patch('auto_resume.websocket.find_codex', return_value='official-codex.exe'), patch('auto_resume.websocket.subprocess.Popen', side_effect=start):
                socket = LocalWebSocket('private-socket', timeout=3)
                try:
                    self.assertEqual(json.loads(socket.receive()), {})
                    self.assertEqual(commands[0], ['official-codex.exe', 'app-server', 'proxy', '--sock', 'private-socket'])
                finally:
                    socket.close()
                self.assertIsNotNone(socket.sock.process.poll())

    def test_broken_proxy_never_becomes_a_new_writer(self):
        with patch('auto_resume.websocket.find_codex', return_value='missing-codex'), patch('auto_resume.websocket.subprocess.Popen', side_effect=FileNotFoundError):
            from auto_resume.domain import TransientError
            with self.assertRaises(TransientError):
                ProxyStream('private', timeout=.01)


class NativePowerTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Windows API requires a Windows host')
    def test_real_windows_idle_sleep_request_acquired_and_released(self):
        from auto_resume.power import WindowsAwake
        lease = WindowsAwake()
        try:
            self.assertTrue(lease.ready.wait(3))
            self.assertTrue(lease.acquired)
            self.assertTrue(lease.thread.is_alive())
        finally:
            lease.close()
        self.assertFalse(lease.thread.is_alive())

    def test_frozen_linux_inhibitor_uses_own_entrypoint(self):
        from unittest.mock import Mock
        from auto_resume.power import AwakeLease
        import io
        process = Mock()
        process.poll.return_value = None
        process.stdout = io.BytesIO(b'ready\n')
        process.stdin = io.BytesIO()
        with patch('auto_resume.power.sys.platform', 'linux'), patch('auto_resume.power.sys.frozen', True, create=True), patch('auto_resume.power.shutil.which', return_value='/usr/bin/systemd-inhibit'), patch('auto_resume.power.subprocess.Popen', return_value=process) as start, patch('auto_resume.power.select.select', return_value=([process.stdout], [], [])):
            lease = AwakeLease()
            lease.update(True)
            self.assertIn('--inhibit-wait', start.call_args.args[0])
            self.assertNotIn('-c', start.call_args.args[0])
            lease.close()


class FrozenEnvironmentTests(unittest.TestCase):
    def test_external_program_does_not_inherit_bundled_linux_libraries(self):
        from auto_resume.process import external_options
        with patch('auto_resume.process.sys.frozen', True, create=True), patch.dict(os.environ, {'LD_LIBRARY_PATH': '/bundled-libraries', 'LD_LIBRARY_PATH_ORIG': '/user-libraries'}):
            self.assertEqual(external_options()['env']['LD_LIBRARY_PATH'], '/user-libraries')
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/bundled-libraries')
