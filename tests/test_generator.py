import os
try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import RateLimitError
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app as module
from text_engine import generate_article, parse_pairs, render_text


class GeneratorTests(unittest.TestCase):
    def test_pairs_validation_and_csv(self):
        pairs = parse_pairs('"A, B", https://example.com/a,b\nIT, https://example.com/?a=1&b=2')
        self.assertEqual(pairs['A, B'], 'https://example.com/a,b')
        for raw in ['X, javascript:alert(1)', 'broken', 'X, https://example.com\nX, https://other.com', 'X, https://example.com:invalid']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_pairs(raw)

    def test_links_overlap_escape_and_missing(self):
        pairs = {'IT-Sicherheit': 'https://example.com/?a=1&b=2', 'IT': 'https://example.com/it', 'nicht da': 'https://example.com/missing'}
        html, missing = render_text('IT-Sicherheit und IT. <script>alert(1)</script>', pairs)
        self.assertEqual(html.count('<a '), 2)
        self.assertNotIn('<script>', html)
        self.assertIn('&amp;b=2', html)
        self.assertEqual(missing, ['nicht da'])

    def test_retry_then_success_and_failure(self):
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace()))
        calls = []
        def completion(**kwargs):
            calls.append(kwargs)
            text = 'Zu kurz.' if len(calls) == 1 else 'IT ' + 'Schutz ' * 799
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason='stop')])
        client.chat.completions.create = completion
        html, text, count = generate_article(client, 'gpt-4', {'IT': 'https://example.com'}, 'Sicherheit', 800)
        self.assertEqual(count, 800)
        self.assertEqual(len(calls), 2)
        self.assertIn('<a href=', html)
        client.chat.completions.create = lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Kurz.'), finish_reason='length')])
        with self.assertRaises(ValueError):
            generate_article(client, 'gpt-4', {'IT': 'https://example.com'}, 'Sicherheit', 800)

    def test_page_missing_key_and_demo_download(self):
        module.app.config.update(TESTING=True, DEMO_MODE=False)
        client = module.app.test_client()
        payload = dict(site='Marktplatz IT-Sicherheit', topic='Sicherheit', words='800', pairs='Eigener Begriff, https://example.com')
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'OUTPUT_DIR', Path(temp)), patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            self.assertEqual(client.get('/').status_code, 200)
            response = client.post('/', data=payload)
            self.assertIn('Zugang ist noch nicht eingerichtet', response.get_data(as_text=True))
            self.assertEqual(list(Path(temp).iterdir()), [])
            module.app.config['DEMO_MODE'] = True
            response = client.post('/', data=payload)
            self.assertEqual(response.status_code, 200)
            page = response.get_data(as_text=True)
            self.assertIn('800 Wörter', page)
            files = list(Path(temp).glob('*.html'))
            self.assertEqual(len(files), 1)
            output = files[0].read_text()
            self.assertIn('href="https://example.com"', output)
            self.assertNotIn('href="https://it-sicherheit.de/', output)
            for name in [files[0].name, files[0].stem + '.txt']:
                response = client.get('/download/' + name)
                self.assertEqual(response.status_code, 200)
                response.close()
            self.assertEqual(client.get('/download/../app.py').status_code, 404)
            module.app.config['DEMO_MODE'] = False

    def test_credit_exhausted_preserves_inputs_and_saves_nothing(self):
        module.app.config.update(TESTING=True, DEMO_MODE=False)
        payload = dict(topic='Testthema', words='800', pairs='IT, https://example.com')
        req = httpx.Request('POST', 'https://api.openai.com/v1/chat/completions')
        resp = httpx.Response(429, request=req)
        for body in ({'code': 'credit_balance_exhausted', 'type': 'insufficient_quota'},
                     {'error': {'code': 'insufficient_quota', 'type': 'insufficient_quota'}}):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp, patch.object(module, 'OUTPUT_DIR', Path(temp)), patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'}), patch.object(module, 'OpenAI'), patch.object(module, 'generate_article', side_effect=RateLimitError('quota', response=resp, body=body)):
                page = module.app.test_client().post('/', data=payload).get_data(as_text=True)
                self.assertIn('API-Guthaben ist aufgebraucht', page)
                self.assertIn('Testthema', page)
                self.assertIn('IT, https://example.com', page)
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_shutdown_requires_session_token(self):
        client = module.app.test_client()
        self.assertEqual(client.post('/stop', data={'token': 'wrong'}).status_code, 403)
        with patch.dict(module.app.config, {'SHUTDOWN_CALLBACK': None}):
            self.assertEqual(client.post('/stop', data={'token': module.app.config['SHUTDOWN_TOKEN']}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
