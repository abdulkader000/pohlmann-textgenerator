"""Self-contained offline regressions; synthetic inputs, no saved responses or API."""
import copy
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
from text_engine import (ArticleGenerationError, _repair_options, approved_link_forms,
                         article_plan, assess_article, generation_prompt, generate_article,
                         render_text, word_count, writing_link_forms)

TEMPLATE = module.site_data['Marktplatz IT-Sicherheit']
SMALL = {k: TEMPLATE[k] for k in ('IT-Sicherheit', 'Backup', 'E-Mail-Sicherheit')}


def paragraph(start, words):
    # Deliberate padding checks mechanics only, never prose quality.
    return start + ' ' + 'Prüfung ' * (words - word_count(start))


def short_article():
    beginnings = ('IT-Sicherheit.', 'Ein Backup hilft.', 'E-Mail-Sicherheit.',
                  'Zuständigkeiten.', 'Überprüfung.', 'Zusammenwirken.', 'Vertiefung.', 'Schluss.')
    counts = (91, 116, 99, 89, 87, 87, 90, 56)
    return '\n\n'.join(paragraph(s, n).strip() for s, n in zip(beginnings, counts))


def full_article(missing=None):
    plan = article_plan(TEMPLATE, 'Cybersicherheit', 800)
    blocks = []
    for i, section in enumerate(plan):
        keys = [k for k in section['keys'] if k != missing]
        start = '; '.join(keys) + '.' if keys else 'Schluss.'
        blocks.append(paragraph(start, section['words'] - (40 if i == 7 else 0)).strip())
    return '\n\n'.join(blocks)


def reply(text, finish='stop'):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text),
                                                   finish_reason=finish)],
                           model='MOCK_ONLY', usage=None)


def fake_client(responses):
    calls = []
    responses = iter(responses)

    def create(**request):
        calls.append(copy.deepcopy(request))
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=create))))
    return client, calls


class EngineAcceptanceTests(unittest.TestCase):
    def test_template_and_dynamic_plan_cover_actual_inputs(self):
        self.assertEqual(len(TEMPLATE), 32)
        self.assertNotIn('IT-Sicherheitszahler', TEMPLATE)
        self.assertEqual(TEMPLATE['IT-Sicherheitszahlen'],
                         'https://it-sicherheit.de/ratgeber/it-sicherheitszahlen/')
        for pairs, topic in ((TEMPLATE, 'Cybersicherheit'), (SMALL, 'Cybersicherheit'),
                             ({'Kaffee': 'https://example.com/a', 'Mühle': 'https://example.com/b'}, 'Kaffee')):
            plan = article_plan(pairs, topic, 800)
            self.assertEqual(sum(s['words'] for s in plan), 800)
            self.assertCountEqual([k for s in plan for k in s['keys']], list(pairs))
            prompt = generation_prompt(pairs, topic, 800, plan)
            self.assertIn(f'alle {len(pairs)} geklärten Pflichtbegriffe', prompt)
            if topic == 'Kaffee':
                self.assertNotIn('Cybersicherheit', prompt)

    def test_explicit_forms_boundaries_overlap_and_correct_urls(self):
        pairs = {k: TEMPLATE[k] for k in ('DORA', 'DSA', 'Datenschutz', 'Datenschutzbeauftragter',
                                         'Penetrationstest', 'Hardware-Sicherheitsmodul')}
        text = ('DORA-Rahmenwerk und DSA-Vorgaben. DORA- und DSA-Vorgaben. '
                'Datenschutz sowie der Datenschutzbeauftragte. Penetrationstests und Hardware-Sicherheitsmodule.')
        html, missing = render_text(text, pairs)
        self.assertEqual(missing, [])
        for url in pairs.values():
            self.assertIn(f'href="{url}"', html)
        for text, key in (('DORAX DORA-Fantasie', 'DORA'), ('Datenschutzrichtlinien', 'Datenschutz'),
                          ('Hardware-Sicherheitsmodulbau', 'Hardware-Sicherheitsmodul')):
            self.assertEqual(render_text(text, {key: pairs[key]})[1], [key])
        _, missing = render_text('der Datenschutzbeauftragte', pairs)
        self.assertIn('Datenschutz', missing)
        self.assertNotIn('Datenschutzbeauftragter', missing)

    def test_context_only_variants_are_not_writing_options(self):
        self.assertIn('DORA-', approved_link_forms(TEMPLATE)['DORA'])
        self.assertNotIn('DORA-', writing_link_forms(TEMPLATE)['DORA'])

    def test_715_expansion_is_distributed_and_preserves_protected_text(self):
        source = short_article()
        self.assertEqual(word_count(source), 715)
        blocks, options, insert = _repair_options(assess_article(source, SMALL), SMALL, 720, 880, 800,
                                                  article_plan(SMALL, 'Cybersicherheit', 800))
        self.assertFalse(insert)
        self.assertEqual([o['paragraph_index'] + 1 for o in options], [3, 4, 5, 6, 7])
        self.assertEqual([o['replacement_target_words'] - o['current_words'] for o in options],
                         [10, 18, 20, 20, 17])
        replacement = '\n\n'.join(paragraph(blocks[o['paragraph_index']], o['replacement_target_words']).strip()
                                   for o in options)
        client, calls = fake_client([reply(source), reply(replacement)])
        html, merged, count = generate_article(client, 'gpt-4.1', SMALL, 'Cybersicherheit', 800)
        self.assertEqual(count, 800)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c['model'] == 'gpt-4.1' for c in calls))
        self.assertIn('Korrigiere ausschließlich Absatz 3, 4, 5, 6, 7', calls[1]['messages'][-1]['content'])
        before, after = re.split(r'(\n\s*\n)', source), re.split(r'(\n\s*\n)', merged)
        for i in (0, 1, 7):
            self.assertEqual(before[i * 2], after[i * 2])
        self.assertEqual(before[1::2], after[1::2])
        self.assertEqual(render_text(merged, SMALL)[1], [])
        for url in SMALL.values():
            self.assertIn(f'href="{url}"', html)

    def test_in_range_missing_phrase_repairs_only_matching_paragraph(self):
        source = full_article('Datenschutz')
        draft = assess_article(source, TEMPLATE)
        self.assertEqual((draft.words, draft.missing), (760, ('Datenschutz',)))
        blocks, options, _ = _repair_options(draft, TEMPLATE, 720, 880, 800)
        self.assertEqual([o['paragraph_index'] for o in options], [4])
        replacement = blocks[4].replace('Prüfung', 'Datenschutz', 1)
        client, calls = fake_client([reply(source), reply(replacement)])
        _, merged, count = generate_article(client, 'gpt-4.1', TEMPLATE, 'Cybersicherheit', 800)
        self.assertEqual(count, 760)
        for i in (0, 1, 2, 3, 5, 6, 7):
            self.assertEqual(merged.split('\n\n')[i], blocks[i])
        self.assertEqual(len(calls), 2)

    def test_worse_short_patch_cannot_replace_760_word_best(self):
        source = full_article('Datenschutz')
        section = article_plan(TEMPLATE, 'Cybersicherheit', 800)[4]
        patch_text = '; '.join(k for k in section['keys'] if k != 'Datenschutz') + '.'
        client, calls = fake_client([reply(source), reply(patch_text)])
        drafts = []
        with self.assertRaises(ArticleGenerationError) as caught:
            generate_article(client, 'gpt-4.1', TEMPLATE, 'Cybersicherheit', 800,
                             max_attempts=2, on_draft=drafts.append)
        self.assertEqual(caught.exception.best_draft.text, source)
        self.assertIn('worse_word_range', drafts[-1]['rejection_reasons'])
        self.assertFalse(drafts[-1]['draft_updated'])
        self.assertEqual(len(calls), 2)

    def test_body_conclusion_numbering_and_invalid_json_are_rejected(self):
        source = full_article('Datenschutz')
        blocks = source.split('\n\n')
        for prefix in ('Abschließend lässt sich sagen, dass alles geschützt ist. ',
                       'Erstens behandeln wir Datenschutz. ', '{"paragraph": '):
            with self.subTest(prefix=prefix):
                client, _ = fake_client([reply(source), reply(prefix + blocks[4])])
                with self.assertRaises(ArticleGenerationError) as caught:
                    generate_article(client, 'gpt-4.1', TEMPLATE, 'Cybersicherheit', 800, max_attempts=2)
                self.assertEqual(caught.exception.best_draft.text, source)

    def test_api_error_stops_without_retry_or_model_fallback(self):
        source = short_article()
        request = httpx.Request('POST', 'https://api.openai.com/v1/chat/completions')
        error = RateLimitError('mock quota', response=httpx.Response(429, request=request),
                               body={'code': 'insufficient_quota'})
        client, calls = fake_client([reply(source), error])
        with self.assertRaises(RateLimitError) as caught:
            generate_article(client, 'gpt-4.1', SMALL, 'Cybersicherheit', 800)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c['model'] == 'gpt-4.1' for c in calls))
        self.assertEqual(caught.exception.best_draft.text, source)

    def test_app_labels_draft_and_downloads_plain_article(self):
        source = full_article()
        client, _ = fake_client([reply(source)])
        data = dict(site='custom', custom_site_name='Offline', topic='Cybersicherheit', words='800',
                    pairs='\n'.join(f'{k}, {v}' for k, v in TEMPLATE.items()))
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'OUTPUT_DIR', Path(temp)), \
                patch.dict(module.app.config, {'TESTING': True, 'DEMO_MODE': False}), \
                patch.dict(os.environ, {'OPENAI_API_KEY': 'mock-only', 'OPENAI_MODEL': 'gpt-4.1'}), \
                patch.object(module, 'OpenAI', return_value=client) as sdk:
            web = module.app.test_client()
            page = web.post('/', data=data).get_data(as_text=True)
            self.assertIn('Artikelentwurf', page)
            self.assertIn('keine automatische Inhaltsfreigabe', page)
            self.assertIn('Konfiguriertes Modell: gpt-4.1', page)
            files = list(Path(temp).iterdir())
            self.assertEqual(len(files), 2)
            for file in files:
                self.assertTrue(file.name.startswith('ENTWURF_'))
                with web.get('/download/' + file.name) as download:
                    self.assertEqual(download.status_code, 200)
                    self.assertIn('attachment;', download.headers['Content-Disposition'])
                    self.assertEqual(download.data, file.read_bytes())
                if file.suffix == '.txt':
                    self.assertEqual(file.read_text(encoding='utf-8'), source)
                else:
                    self.assertIn('Keine automatische Inhaltsfreigabe', file.read_text(encoding='utf-8'))
            self.assertEqual(sdk.call_args.kwargs['max_retries'], 0)


if __name__ == '__main__':
    unittest.main()
