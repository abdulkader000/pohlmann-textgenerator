"""Offline mechanics only: synthetic drafts are not evidence of generation quality."""
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import RateLimitError

import app as module
from text_engine import (ArticleGenerationError, POHLMANN_TEMPLATE, _repair_options,
                         approved_link_forms, article_plan, assess_article, generate_article,
                         generation_prompt, render_text, word_count)

PAIRS = module.site_data[POHLMANN_TEMPLATE]
MISSING = ('Risiko', 'Phishing', 'RSA', 'Künstliche Intelligenz')  # Hypothetical, not Sara's four.


def response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason='stop')],
                           model='gpt-4.1-MOCK', usage=None)


def client_for(*items):
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=items))))


def synthetic_article(missing=(), pairs=PAIRS):
    plan = article_plan(pairs, 'Cybersicherheit', 700, template=POHLMANN_TEMPLATE)
    blocks = []
    for i, section in enumerate(plan):
        start = '; '.join(key for key in section['keys'] if key not in missing) or 'Text'
        start += '.'
        budget = section['words'] - (17 if i == 0 else 0)
        blocks.append((start + ' ' + 'Prüfung ' * (budget - word_count(start))).strip())
    text = '\n\n'.join(blocks)
    assert word_count(text) == 683
    return text, plan


def replacement_for(source, pairs=PAIRS):
    draft = assess_article(source, pairs)
    plan = article_plan(pairs, 'Cybersicherheit', 700, template=POHLMANN_TEMPLATE)
    blocks, options, insert = _repair_options(draft, pairs, 700, plan)
    assert not insert
    replacements = [blocks[o['paragraph_index']] + ' ' + '. '.join(o['missing']) + '.' for o in options]
    return '\n\n'.join(replacements), options


class PohlmannTemplateTests(unittest.TestCase):
    def test_verified_url_correction_and_topic_budgets(self):
        self.assertEqual(len(PAIRS), 38)
        self.assertEqual(PAIRS['Kritische Infrastruktur'],
                         'https://norbert-pohlmann.com/glossar-cyber-sicherheit/kritische-infrastrukturen-kritis/')
        self.assertEqual(PAIRS['Privatsphäre'], 'https://norbert-pohlmann.com/glossar-cyber-sicherheit/privatsphaere/')
        for target in (700, 800, 1200):
            plan = article_plan(PAIRS, 'Cybersicherheit', target, template=POHLMANN_TEMPLATE)
            self.assertEqual(sum(s['words'] for s in plan), target)
            self.assertCountEqual([key for s in plan for key in s['keys']], PAIRS)
            self.assertEqual(len(plan), 7)
            self.assertEqual(len(set(s['name'] for s in plan)), 7)
            self.assertIn('Risiko', plan[1]['keys'])
            self.assertIn('Phishing', plan[2]['keys'])
            self.assertIn('OSINT', plan[3]['keys'])
            self.assertIn('RSA', plan[4]['keys'])
            self.assertIn('Singularität', plan[5]['keys'])
            self.assertGreater(plan[4]['words'], plan[3]['words'])
            prompt = generation_prompt(PAIRS, 'Cybersicherheit', target, plan, template=POHLMANN_TEMPLATE)
            self.assertIn('alle 38 geklärten Pflichtbegriffe', prompt)
            for context in ('digital souveränen Gesellschaft', 'hypothetisches, umstrittenes Zukunftskonzept',
                            'High-Level Security Module', 'Norbert Pohlmann als Autor'):
                self.assertIn(context, prompt)
        self.assertEqual([s['words'] for s in article_plan(PAIRS, 'Cybersicherheit', 700, template=POHLMANN_TEMPLATE)],
                         [70, 105, 115, 100, 154, 104, 52])

    def test_custom_and_edited_lists_keep_actual_inputs(self):
        custom = {'Kaffee': 'https://example.org/a', 'Mühle': 'https://example.org/b'}
        plan = article_plan(custom, 'Kaffee', 700)
        prompt = generation_prompt(custom, 'Kaffee', 700, plan)
        self.assertCountEqual([key for s in plan for key in s['keys']], custom)
        for unwanted in ('Cybersicherheit', 'Pohlmann', 'High-Level Security Module', 'KRITIS'):
            self.assertNotIn(unwanted, prompt)
        # Matching words in a custom list do not activate this template's outline.
        small = {key: PAIRS[key] for key in ('Risiko', 'RSA', 'Künstliche Intelligenz')}
        self.assertNotIn('Sicherheitsmanagement:', generation_prompt(small, 'Test', 700, article_plan(small, 'Test', 700)))
        edited = {key: value for key, value in PAIRS.items() if key != 'Spam'}
        edited.update(custom)
        plan = article_plan(edited, 'Cybersicherheit', 700, template=POHLMANN_TEMPLATE)
        self.assertCountEqual([key for s in plan for key in s['keys']], edited)
        self.assertNotIn('Spam', [key for s in plan for key in s['keys']])

    def test_explicit_inflections_link_original_urls_and_reject_word_parts(self):
        cases = {'Risiko': 'Risiken und Risikos', 'Künstliche Intelligenz': 'mit künstlicher Intelligenz',
                 'Kritische Infrastruktur': 'einer kritischen Infrastruktur und kritischer Infrastrukturen',
                 'Angriffsvektor': 'Angriffsvektoren', 'Firewall': 'Firewalls', 'Passwörter': 'Passwörtern',
                 'Schwachstellen': 'Schwachstelle', 'Filterblasen': 'Filterblase', 'HSM': 'HSMs', 'TPM': 'TPMs'}
        for key, text in cases.items():
            with self.subTest(key=key):
                html, missing = render_text(text, {key: PAIRS[key]})
                self.assertEqual(missing, [])
                self.assertIn(f'href="{PAIRS[key]}"', html)
        for key, text in (('Risiko', 'Risikomanagement Risikenanalyse'),
                          ('Künstliche Intelligenz', 'KI künstlicher Intelligenzsysteme'),
                          ('Firewall', 'Firewallsysteme Firewall-Regel'), ('HSM', 'HSMspezifikation AHSM'),
                          ('Kritische Infrastruktur', 'kritischer Infrastrukturbetreiber')):
            self.assertEqual(render_text(text, {key: PAIRS[key]})[1], [key])

    def test_overlaps_and_explicitly_entered_variant_keep_separate_links(self):
        pairs = {key: PAIRS[key] for key in ('Cyber-Sicherheit', 'Lehrbuch Cyber-Sicherheit',
                                            'Schwachstellen', 'Schwachstellenmanagement')}
        html, missing = render_text('Lehrbuch Cyber-Sicherheit und Schwachstellenmanagement.', pairs)
        self.assertEqual(set(missing), {'Cyber-Sicherheit', 'Schwachstellen'})
        self.assertEqual(html.count('<a '), 2)
        text = 'Lehrbuch Cyber-Sicherheit; Cyber-Sicherheit; Schwachstellenmanagement; Schwachstelle.'
        self.assertEqual(render_text(text, pairs)[1], [])
        independent = {'Risiko': 'https://example.org/risk', 'Risiken': 'https://example.org/risks'}
        self.assertNotIn('Risiken', approved_link_forms(independent)['Risiko'])
        html, missing = render_text('Risiko und Risiken', independent)
        self.assertEqual(missing, [])
        self.assertIn('href="https://example.org/risk">Risiko', html)
        self.assertIn('href="https://example.org/risks">Risiken', html)

    def test_four_missing_phrases_repair_different_paragraphs_preserving_others(self):
        source, _ = synthetic_article(MISSING)
        replacement, options = replacement_for(source)
        self.assertEqual([o['paragraph_index'] + 1 for o in options], [2, 3, 5, 6])
        self.assertTrue(all(o['existing'] for o in options))
        client = client_for(response(source), response(replacement))
        html, merged, count = generate_article(client, 'gpt-4.1', PAIRS, 'Cybersicherheit', 700,
                                               template=POHLMANN_TEMPLATE, max_attempts=2)
        self.assertTrue(613 <= count <= 787)
        self.assertEqual(render_text(merged, PAIRS)[1], [])
        for url in PAIRS.values():
            self.assertIn(f'href="{url}"', html)
        before, after = re.split(r'(\n\s*\n)', source), re.split(r'(\n\s*\n)', merged)
        for i in (0, 3, 6):
            self.assertEqual(before[i * 2], after[i * 2])
        self.assertEqual(before[1::2], after[1::2])
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_lost_link_patch_is_rejected_then_next_repair_uses_best_draft(self):
        source, _ = synthetic_article(MISSING)
        good, _ = replacement_for(source)
        bad = good.replace('Ransomware', 'Prüfung')
        client = client_for(response(source), response(bad), response(good))
        drafts = []
        _, merged, _ = generate_article(client, 'gpt-4.1', PAIRS, 'Cybersicherheit', 700,
                                        template=POHLMANN_TEMPLATE, on_draft=drafts.append)
        self.assertIn('lost_linktexts', drafts[1]['rejection_reasons'])
        self.assertFalse(drafts[1]['draft_updated'])
        self.assertEqual(drafts[1]['best'].text, source)
        third = client.chat.completions.create.call_args_list[2].kwargs
        self.assertEqual(third['messages'][2]['content'], source)
        self.assertEqual(render_text(merged, PAIRS)[1], [])

    def test_failed_app_run_saves_actual_inputs_names_best_and_patch_reasons(self):
        pairs = {**PAIRS, 'RSA': 'https://example.org/custom-rsa?x=1&y=2'}
        source, _ = synthetic_article(MISSING, pairs)
        good, _ = replacement_for(source, pairs)
        client = client_for(response(source), response(good.replace('Ransomware', 'Prüfung')),
                            response(good.replace('Ransomware', 'Prüfung')))
        secret = 'LOCAL_SECRET_SENTINEL_DO_NOT_SAVE'
        data = {'site': POHLMANN_TEMPLATE, 'custom_site_name': 'Actual input', 'topic': 'Cybersicherheit ' + secret,
                'words': '700', 'pairs': '\n'.join(f'{key}, {url}' for key, url in pairs.items())}
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'OUTPUT_DIR', Path(temp) / 'outputs'), \
                patch.object(module, 'DIAGNOSTIC_DIR', Path(temp) / 'diagnostics'), \
                patch.dict(module.app.config, {'TESTING': True, 'DEMO_MODE': False}), \
                patch.dict(os.environ, {'OPENAI_API_KEY': secret, 'OPENAI_MODEL': 'gpt-4.1'}), \
                patch.object(module, 'OpenAI', return_value=client):
            page = module.app.test_client().post('/', data=data).get_data(as_text=True)
            self.assertIn('Fehlende Linktexte:', page)
            for term in MISSING:
                self.assertIn(term, page)
            self.assertIn('HTML herunterladen', page)
            self.assertIn('Unvollständiger Entwurf', page)
            self.assertNotIn('alle eingegebenen Linktexte verlinkt', page)
            self.assertIn('Diagnose lokal gespeichert:', page)
            self.assertEqual(len(list((Path(temp) / 'outputs').iterdir())), 2)
            folder = next((Path(temp) / 'diagnostics').iterdir())
            report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['pairs'], pairs)
            self.assertEqual(report['inputs']['pairs'], data['pairs'])
            self.assertEqual(report['inputs']['topic'], 'Cybersicherheit [REDACTED_API_KEY]')
            self.assertEqual(report['requested_model'], 'gpt-4.1')
            self.assertEqual(len(report['attempts']), 3)
            self.assertTrue(all(a['response_model'] == 'gpt-4.1-MOCK' for a in report['attempts']))
            for draft in report['drafts'][1:]:
                self.assertIn('lost_linktexts', draft['rejection_reasons'])
                self.assertFalse(draft['draft_updated'])
            self.assertEqual((folder / 'REJECTED_BEST.txt').read_text(encoding='utf-8'), source)
            self.assertIn('nicht zur Veröffentlichung', (folder / 'REJECTED_BEST.html').read_text(encoding='utf-8'))
            for file in folder.iterdir():
                self.assertNotIn(secret, file.read_text(encoding='utf-8'))
                self.assertNotIn('OPENAI_API_KEY', file.read_text(encoding='utf-8'))

    def test_api_error_saves_best_without_sdk_error_text_or_fallback(self):
        source, _ = synthetic_article(MISSING)
        secret = 'LOCAL_SECRET_SENTINEL_DO_NOT_SAVE'
        req = httpx.Request('POST', 'https://api.openai.com/v1/chat/completions')
        error = RateLimitError('SDK error containing ' + secret, response=httpx.Response(429, request=req),
                               body={'code': 'insufficient_quota'})
        client = client_for(response(source), error)
        data = dict(site=POHLMANN_TEMPLATE, topic='Cybersicherheit', words='700',
                    pairs='\n'.join(f'{k}, {v}' for k, v in PAIRS.items()))
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'OUTPUT_DIR', Path(temp) / 'outputs'), \
                patch.object(module, 'DIAGNOSTIC_DIR', Path(temp) / 'diagnostics'), \
                patch.dict(module.app.config, {'TESTING': True, 'DEMO_MODE': False}), \
                patch.dict(os.environ, {'OPENAI_API_KEY': secret, 'OPENAI_MODEL': 'gpt-4.1'}), \
                patch.object(module, 'OpenAI', return_value=client):
            page = module.app.test_client().post('/', data=data).get_data(as_text=True)
            self.assertIn('API-Guthaben ist aufgebraucht', page)
            self.assertIn('Fehlende Linktexte:', page)
            report_file = next((Path(temp) / 'diagnostics').glob('*/report.json'))
            report = json.loads(report_file.read_text(encoding='utf-8'))
            self.assertEqual(report['best_draft']['text'], source)
            self.assertEqual(report['failure']['type'], 'RateLimitError')
            self.assertNotIn(secret, report_file.read_text(encoding='utf-8'))
            self.assertNotIn('SDK error containing', report_file.read_text(encoding='utf-8'))
            self.assertEqual(client.chat.completions.create.call_count, 2)
            self.assertTrue(all(c.kwargs['model'] == 'gpt-4.1' for c in client.chat.completions.create.call_args_list))

    def test_diagnostic_redacts_key_in_draft_and_urls_and_reports_write_failure(self):
        secret = 'LOCAL_SECRET_SENTINEL_DO_NOT_SAVE'
        pairs = {'Risiko': 'https://example.org/?token=' + secret, 'RSA': 'https://example.org/rsa'}
        draft = assess_article('Ein Risiko. ' + secret, pairs)
        error = ArticleGenerationError('Mock failure', draft)
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'DIAGNOSTIC_DIR', Path(temp)):
            folder = module.save_generation_failure({'pairs': 'Risiko, ' + pairs['Risiko']}, pairs, 'mock-model',
                                                     [], [], error, secret)
            for file in folder.iterdir():
                self.assertNotIn(secret, file.read_text(encoding='utf-8'))
            self.assertIn('[REDACTED_API_KEY]', (folder / 'REJECTED_BEST.txt').read_text(encoding='utf-8'))
        source, _ = synthetic_article(MISSING)
        _, options = replacement_for(source)
        unchanged = '\n\n'.join(source.split('\n\n')[o['paragraph_index']] for o in options)
        client = client_for(response(source), response(unchanged), response(unchanged))
        data = dict(site=POHLMANN_TEMPLATE, topic='Cybersicherheit', words='700',
                    pairs='\n'.join(f'{k}, {v}' for k, v in PAIRS.items()))
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'OUTPUT_DIR', Path(temp)), \
                patch.dict(module.app.config, {'TESTING': True, 'DEMO_MODE': False}), \
                patch.dict(os.environ, {'OPENAI_API_KEY': secret}), \
                patch.object(module, 'OpenAI', return_value=client), \
                patch.object(module, 'save_generation_failure', side_effect=PermissionError('mock read-only folder')):
            page = module.app.test_client().post('/', data=data).get_data(as_text=True)
            self.assertIn('Fehlende Linktexte:', page)
            self.assertIn('Die lokale Diagnose konnte nicht gespeichert werden', page)
            self.assertEqual(len(list(Path(temp).glob('UNVOLLSTAENDIGER_ENTWURF_*'))), 2)


if __name__ == '__main__':
    unittest.main()
