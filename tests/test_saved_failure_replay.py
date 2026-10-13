"""Local replay of supplied responses; absent private fixtures are skipped in CI."""
import json
import os
from pathlib import Path
import re
import tempfile
from unittest.mock import Mock, patch
from types import SimpleNamespace
import unittest

import app as module
from test_engine_acceptance import reply
from text_engine import (_merge_paragraph_patch, assess_article, render_text)

FIXTURES = Path(__file__).resolve().parents[1] / 'outputs/length-guidance-review-20261013/real-fixtures'


@unittest.skipUnless(FIXTURES.exists(), 'Private real diagnostics are local only, not shipped.')
class SavedFailureReplayTests(unittest.TestCase):
    def test_compound_recognition_changes_only_observed_coverage(self):
        for path in sorted(FIXTURES.glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            norbert = data['inputs']['site'] == 'Webseite Norbert Pohlmann'
            record = data['drafts'][1] if norbert else data['drafts'][0]
            with patch.dict('text_engine.LINK_COMPOUND_SUFFIXES', {}, clear=True):
                before = assess_article(record['raw_response'], data['pairs'])
            after = assess_article(record['raw_response'], data['pairs'])
            self.assertEqual(set(before.missing) - set(after.missing),
                             {'Malware', 'TLS'} if norbert else {'eIDAS'})
            self.assertEqual(before.text, after.text)
            if norbert:
                self.assertIn('RSA', after.missing)
                self.assertIn('Zero Trust', after.missing)

    @patch.dict('text_engine.LINK_COMPOUND_SUFFIXES', {}, clear=True)
    def test_historical_rejection_reasons_reproduced_without_length_checks(self):
        rejected = 0
        for path in sorted(FIXTURES.glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            for record, attempt in zip(data['drafts'][1:], data['attempts'][1:]):
                prior = data['drafts'][record['attempt'] - 2]['best']
                draft = assess_article(prior['text'], data['pairs'], prior['finish_reason'])
                options = [{'paragraph_index': i, 'one_paragraph': True} for i in attempt['paragraph_indices']]
                if 'paragraph_lost_linktexts' in record['rejection_reasons']:
                    # Reproduce the historical per-paragraph guard from the recorded passages.
                    old = re.split(r'\n\s*\n', prior['text'])
                    new = re.split(r'\n\s*\n', record['raw_response'])
                    losses = [set(render_text(patch, data['pairs'])[1]) -
                              set(render_text(old[index], data['pairs'])[1])
                              for index, patch in zip(attempt['paragraph_indices'], new)]
                    self.assertTrue(any(losses))
                    rejected += 1
                    if data['inputs']['site'] == 'Webseite Norbert Pohlmann':
                        with self.assertRaisesRegex(ValueError, '^lost_linktexts$'):
                            _merge_paragraph_patch(record['raw_response'], draft, data['pairs'], options, False)
                    else:
                        merged, _ = _merge_paragraph_patch(record['raw_response'], draft, data['pairs'], options, False)
                        self.assertEqual(assess_article(merged, data['pairs']).missing, draft.missing)
                else:
                    merged, _ = _merge_paragraph_patch(record['raw_response'], draft, data['pairs'], options, False)
                    assessed = assess_article(merged, data['pairs'])
                    self.assertEqual(assessed.words, 935)
                    self.assertEqual(assessed.missing, ('eIDAS',))
        self.assertEqual(rejected, 3)

    def test_real_response_passages_replayed_through_current_app_downloads(self):
        for path in sorted(FIXTURES.glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            count, attempts = 0, []

            def create(**request):
                nonlocal count
                count += 1
                self.assertLessEqual(count, 3)
                if count == 1:
                    return reply(data['drafts'][0]['raw_response'])
                # Select untouched saved passages for the NEW narrower request.
                # This is a local replay adapter, never a generated/edited article.
                command = request['messages'][-1]['content']
                match = re.search(r'Korrigiere ausschließlich Absatz ([\d, ]+)', command)
                indices = [int(value.strip()) - 1 for value in match[1].strip().split(',')]
                original = data['attempts'][count - 1]['paragraph_indices']
                passages = re.split(r'\n\s*\n', data['drafts'][count - 1]['raw_response'])
                mapping = dict(zip(original, passages))
                return reply('\n\n'.join(mapping[index] for index in indices))

            sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=create))))
            with self.subTest(run=path.stem), tempfile.TemporaryDirectory() as temp, \
                    patch.object(module, 'OUTPUT_DIR', Path(temp) / 'outputs'), \
                    patch.object(module, 'DIAGNOSTIC_DIR', Path(temp) / 'diagnostics'), \
                    patch.dict(module.app.config, {'TESTING': True, 'DEMO_MODE': False,
                                                   'GENERATION_OBSERVER': attempts.append}), \
                    patch.dict(os.environ, {'OPENAI_API_KEY': 'mock-only', 'OPENAI_MODEL': data['requested_model']}), \
                    patch.object(module, 'OpenAI', return_value=sdk):
                web = module.app.test_client()
                page = web.post('/', data=data['inputs']).get_data(as_text=True)
                self.assertEqual(count, 3)
                norbert = data['inputs']['site'] == 'Webseite Norbert Pohlmann'
                if norbert:
                    self.assertIn('Unvollständiger Entwurf', page)
                    self.assertNotIn('alle eingegebenen Linktexte verlinkt', page)
                else:
                    self.assertNotIn('Unvollständiger Entwurf', page)
                    self.assertIn('alle eingegebenen Linktexte verlinkt', page)
                for file in (Path(temp) / 'outputs').iterdir():
                    with web.get('/download/' + file.name) as download:
                        self.assertEqual(download.status_code, 200)
                        self.assertEqual(download.data, file.read_bytes())
                best = attempts[-1]
                if norbert:
                    report = json.loads(next((Path(temp) / 'diagnostics').glob('*/report.json')).read_text(encoding='utf-8'))
                    self.assertEqual(report['best_draft']['text'], data['best_draft']['text'])
                    self.assertTrue(all(a['rejection_reasons'] == ['lost_linktexts'] for a in attempts[1:]))
                    self.assertEqual(best['best_missing'], ['Grundschutz', 'Passwörter', 'Phishing',
                                                          'Schwachstellenmanagement', 'Social Engineering', 'Zero Trust'])
                else:
                    self.assertEqual(best['best_missing'], [])
                    self.assertFalse((Path(temp) / 'diagnostics').exists())
                    text = next((Path(temp) / 'outputs').glob('*.txt')).read_text(encoding='utf-8')
                    self.assertEqual(render_text(text, data['pairs'])[1], [])
                summary = {'scope': 'OFFLINE_REPLAY_NOT_NEW_GENERATION', 'run': path.stem,
                           'requests_simulated': count, 'best_words': best['best_words'],
                           'missing': best['best_missing'], 'attempts': attempts,
                           'downloads': 'HTTP 200, exact saved bytes',
                           'status': 'INCOMPLETE_NOT_APPROVED' if norbert else 'LINKS_COMPLETE_HUMAN_REVIEW_REQUIRED'}
                (FIXTURES.parent / ('replay_' + path.stem + '.json')).write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
