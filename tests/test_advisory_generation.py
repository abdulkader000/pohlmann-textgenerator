"""Offline acceptance: word goals never discard purchased text or weaken links."""
from html.parser import HTMLParser
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as module
from test_engine_acceptance import fake_client, paragraph, reply
from text_engine import (_repair_options, article_plan, assess_article, generate_article,
                         render_text, word_count)


def sample(pairs, site, words=800, missing=()):
    plan = article_plan(pairs, 'Test', 800, template=site)
    blocks = []
    for i, section in enumerate(plan):
        start = '; '.join(k for k in section['keys'] if k not in missing) or 'Text'
        count = words // len(plan) + (1 if i < words % len(plan) else 0)
        blocks.append(paragraph(start + '.', count).strip())
    text = '\n\n'.join(blocks)
    assert word_count(text) == words
    return text


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.append(dict(attrs).get('href'))


class AdvisoryGenerationTests(unittest.TestCase):
    def post(self, temp, pairs, site, responses):
        api, calls = fake_client(responses)
        payload = dict(site=site, words='800', topic='Test',
                       pairs='\n'.join(f'{key}, {url}' for key, url in pairs.items()))
        with patch.object(module, 'OUTPUT_DIR', Path(temp) / 'outputs'), \
                patch.object(module, 'DIAGNOSTIC_DIR', Path(temp) / 'diagnostics'), \
                patch.dict(module.app.config, {'TESTING': True, 'DEMO_MODE': False}), \
                patch.dict(os.environ, {'OPENAI_API_KEY': 'mock-only', 'OPENAI_MODEL': 'gpt-4.1'}), \
                patch.object(module, 'OpenAI', return_value=api):
            web = module.app.test_client()
            response = web.post('/', data=payload)
            self.assertEqual(response.status_code, 200)
            files = sorted((Path(temp) / 'outputs').iterdir())
            self.assertEqual(len(files), 2)
            for file in files:
                with web.get('/download/' + file.name) as downloaded:
                    self.assertEqual(downloaded.status_code, 200)
                    self.assertEqual(downloaded.data, file.read_bytes())
                    self.assertIn('attachment;', downloaded.headers['Content-Disposition'])
            return response.get_data(as_text=True), files, calls

    def test_both_templates_and_custom_save_700_935_1000_and_short_warning(self):
        cases = list(module.site_data.items()) + [('custom', {'Kaffee': 'https://example.org/?x=1&y=2',
                                                            'Mühle': 'https://example.org/m'})]
        for site, pairs in cases:
            for words in (700, 935, 1000, 699):
                with self.subTest(site=site, words=words), tempfile.TemporaryDirectory() as temp:
                    source = sample(pairs, site, words)
                    page, files, calls = self.post(temp, pairs, site, [reply(source)])
                    self.assertEqual(len(calls), 1)
                    self.assertIn('alle eingegebenen Linktexte verlinkt', page)
                    self.assertEqual('kürzer als gewünscht' in page, words < 700)
                    self.assertFalse((Path(temp) / 'diagnostics').exists())
                    for file in files:
                        if file.suffix == '.txt':
                            self.assertEqual(file.read_text(encoding='utf-8'), source)
                        else:
                            parser = Anchors()
                            parser.feed(file.read_text(encoding='utf-8'))
                            self.assertEqual(set(parser.urls), set(pairs.values()))

    def test_coverage_improvement_accepts_growth_and_preserves_other_paragraphs(self):
        site = 'Marktplatz IT-Sicherheit'
        pairs = module.site_data[site]
        source = sample(pairs, site, 935, ('Backup',))
        blocks, options, _ = _repair_options(assess_article(source, pairs), pairs, 800,
                                            article_plan(pairs, 'Test', 800, template=site))
        self.assertEqual(len(options), 1)
        index = options[0]['paragraph_index']
        replacement = blocks[index] + ' Backup. ' + 'Prüfung ' * 200
        api, calls = fake_client([reply(source), reply(replacement)])
        _, merged, count = generate_article(api, 'gpt-4.1', pairs, 'Test', 800, template=site)
        self.assertGreater(count, 1000)
        self.assertEqual(render_text(merged, pairs)[1], [])
        for i, before in enumerate(blocks):
            if i != index:
                self.assertEqual(merged.split('\n\n')[i], before)
        prompt = calls[1]['messages'][-1]['content']
        self.assertIn('bereits verlinkte Begriffe mit zulässigen Formen', prompt)
        self.assertNotIn('Gesamtwortbudget', prompt)
        self.assertNotIn('Bei Überlänge', prompt)
        self.assertEqual(len(calls), 2)

    def test_lost_link_rejected_and_best_downloadable_without_false_success(self):
        site = 'Marktplatz IT-Sicherheit'
        pairs = module.site_data[site]
        source = sample(pairs, site, 935, ('Backup',))
        blocks, options, _ = _repair_options(assess_article(source, pairs), pairs, 800)
        option = options[0]
        lost = option['existing'][0]
        replacement = (blocks[option['paragraph_index']] + ' Backup.').replace(lost, 'Prüfung')
        with tempfile.TemporaryDirectory() as temp:
            page, files, calls = self.post(temp, pairs, site, [reply(source), reply(replacement), reply(replacement)])
            self.assertEqual(len(calls), 3)
            self.assertIn('Unvollständiger Entwurf', page)
            self.assertIn('Fehlende Linktexte: Backup', page)
            self.assertNotIn('alle eingegebenen Linktexte verlinkt', page)
            for file in files:
                self.assertTrue(file.name.startswith('UNVOLLSTAENDIGER_ENTWURF_'))
                text = file.read_text(encoding='utf-8')
                self.assertIn('Unvollständiger Entwurf', text)
                if file.suffix == '.txt':
                    self.assertTrue(text.endswith(source))
                else:
                    parser = Anchors()
                    parser.feed(text)
                    self.assertNotIn(pairs['Backup'], parser.urls)
                    self.assertEqual(set(parser.urls), set(pairs.values()) - {pairs['Backup']})
            import json
            report = json.loads(next((Path(temp) / 'diagnostics').glob('*/report.json')).read_text(encoding='utf-8'))
            self.assertEqual(report['best_draft']['text'], source)
            self.assertTrue(all(d['rejection_reasons'] == ['lost_linktexts'] for d in report['drafts'][1:]))

    def test_complete_but_truncated_response_saves_with_visible_format_notice(self):
        pairs = {'Kaffee': 'https://example.org/k'}
        source = sample(pairs, 'custom', 700)
        with tempfile.TemporaryDirectory() as temp:
            page, _, calls = self.post(temp, pairs, 'custom', [reply(source, finish='length')])
            self.assertEqual(len(calls), 1)
            self.assertIn('unfinished_response', page)
            self.assertIn('Inhalt und Sprache vor Veröffentlichung prüfen', page)

    def test_custom_incomplete_download_keeps_links_and_warns_when_short(self):
        pairs = {'Kaffee': 'https://example.org/k', 'Mühle': 'https://example.org/m'}
        source = sample(pairs, 'custom', 699, ('Mühle',))
        blocks, options, _ = _repair_options(assess_article(source, pairs), pairs, 800)
        unchanged = '\n\n'.join(blocks[o['paragraph_index']] for o in options)
        with tempfile.TemporaryDirectory() as temp:
            page, files, calls = self.post(temp, pairs, 'custom', [reply(source), reply(unchanged), reply(unchanged)])
            self.assertEqual(len(calls), 3)
            self.assertIn('Unvollständiger Entwurf', page)
            self.assertIn('kürzer als gewünscht', page)
            self.assertNotIn('alle eingegebenen Linktexte verlinkt', page)
            for file in files:
                content = file.read_text(encoding='utf-8')
                if file.suffix == '.html':
                    parser = Anchors()
                    parser.feed(content)
                    self.assertEqual(set(parser.urls), {pairs['Kaffee']})
                else:
                    self.assertTrue(content.startswith('Unvollständiger Entwurf'))
                    self.assertTrue(content.endswith(source))

    def test_link_still_present_elsewhere_is_not_a_false_loss(self):
        pairs = {'Alpha': 'https://example.org/a', 'Beta': 'https://example.org/b',
                 'Gamma': 'https://example.org/g'}
        source = 'Alpha.\n\nAlpha und Beta.\n\nSchluss.'
        # Alpha stays in the protected introduction, so removing its duplicate is allowed.
        api, calls = fake_client([reply(source), reply('Beta und Gamma.')])
        _, text, _ = generate_article(api, 'gpt-4.1', pairs, 'Test', 800)
        self.assertEqual(text, 'Alpha.\n\nBeta und Gamma.\n\nSchluss.')
        self.assertEqual(render_text(text, pairs)[1], [])
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
