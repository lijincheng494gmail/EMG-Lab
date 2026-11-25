"""Exercise the local HTTP contract without opening a hardware port."""
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server as s


class TestHTTP(unittest.TestCase):
    def test_demo_record_replay_and_regression(self):
        with tempfile.TemporaryDirectory() as folder:
            lab = s.Lab(folder)
            http = ThreadingHTTPServer(('127.0.0.1', 0), s.Handler)
            http.lab = lab
            http.daemon_threads = True
            worker = threading.Thread(target=http.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{http.server_port}'

            def request(path, body=None, ctype='application/json', headers=None):
                payload = None if body is None else (
                    body.encode() if isinstance(body, str) else json.dumps(body).encode())
                req = urllib.request.Request(
                    base + path, data=payload,
                    headers={'Content-Type': ctype, **(headers or {})})
                with urllib.request.urlopen(req, timeout=5) as response:
                    raw = response.read()
                    return json.loads(raw) if response.headers.get_content_type() == 'application/json' else raw

            try:
                self.assertIn(b'EMG-Lab', request('/'))
                self.assertIn(b'EMG', request('/notes'))
                request('/api/connect', {'mode': 'demo'})
                ident = request('/api/record/start', {'label': 'HTTP test', 'config': {}})['id']
                deadline = time.monotonic() + 3
                while lab.state()['recording']['count'] < 40 and time.monotonic() < deadline:
                    time.sleep(.02)
                request('/api/mark', {'label': 'event'})
                request('/api/record/stop', {})
                meta = request('/api/download/' + ident + '.json')
                self.assertGreaterEqual(meta['valid_frames'], 40)
                self.assertEqual(meta['markers'][0]['label'], 'event')
                result = request('/api/analyze', {'source': 'stream', 'n': 64, 'config': {}})
                self.assertEqual(result['fs'], 300)
                recorded = request('/api/download/' + ident + '.csv').decode()
                request('/api/replay', recorded, 'text/csv', {'X-Filename': 'synthetic.csv'})
                result = request('/api/analyze', {'source': 'replay', 'config': {}})
                self.assertIsNone(result['fs'])
                self.assertEqual(result['fs_basis'], 'unknown')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('/api/regression', {'config': {'window': 8}})
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(request('/api/example', {})['n'], 7200)
                fit = request('/api/regression', {'config': {'window': 60}})
                self.assertEqual((fit['train_n'], fit['test_n']), (90, 30))
                self.assertGreater(fit['r2'], .9)
                self.assertEqual(fit['fs_basis'], 'synthetic-known')
                request('/api/disconnect', {})
                self.assertEqual(request('/api/state')['mode'], 'idle')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('/api/state', headers={'Origin': 'https://example.invalid'})
                self.assertEqual(error.exception.code, 403)
            finally:
                lab.disconnect()
                http.shutdown()
                http.server_close()
                worker.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
