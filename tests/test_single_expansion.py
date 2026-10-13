"""Single bounded expansion; synthetic additions check mechanics, not prose quality."""
import json
from pathlib import Path
import re
import tempfile
import unittest

import test_advisory_generation as advisory
from test_advisory_generation import sample
from test_engine_acceptance import SMALL, fake_client, paragraph, reply
from text_engine import (ArticleGenerationError, _repair_options, article_plan,
                         assess_article, generate_article, render_text, word_count)

FIXTURES = Path(__file__).resolve().parents[1] / 'outputs/single-expansion-review-20261013/real-fixtures'


def simulated_expansion(source, pairs, target=800, site=None, *, extra=None):
    blocks, options, insert = _repair_options(assess_article(source, pairs), pairs, target,
                                            article_plan(pairs, 'Cybersicherheit', target, template=site), expand=True)
    replacements = []
    for option in options:
        old = '' if insert else blocks[option['paragraph_index']]
        # Deliberately synthetic: never save this as evidence of language/content quality.
        count = option['expansion_target_words'] if extra is None else word_count(old) + extra
        replacements.append(paragraph(old, count).strip())
    return '\n\n'.join(replacements), options, insert


class SingleExpansionTests(unittest.TestCase):
    def test_threshold_other_goals_and_long_texts(self):
        for target, words, expands in ((800, 699, True), (800, 700, False), (800, 935, False),
                                      (800, 1000, False), (801, 700, True), (801, 701, False),
                                      (1200, 1049, True), (1200, 1050, False)):
            with self.subTest(target=target, words=words):
                source = sample(SMALL, 'custom', words)
                replacement, options, _ = simulated_expansion(source, SMALL, target)
                client, calls = fake_client([reply(source), reply(replacement)])
                _, text, count = generate_article(client, 'gpt-4.1', SMALL, 'Cybersicherheit', target)
                self.assertEqual(len(calls), 2 if expands else 1)
                self.assertEqual(count, target if expands else words)
                self.assertEqual(render_text(text, SMALL)[1], [])
                if expands:
                    self.assertGreaterEqual(len(options), 2)
                    prompt = calls[1]['messages'][-1]['content']
                    for instruction in ('einzige Erweiterungsanfrage', 'klar hypothetische Beispiele',
                                        'Alle übrigen Absätze bleiben unverändert', 'keine angehängte Linkliste'):
                        self.assertIn(instruction, prompt)
                else:
                    self.assertEqual(text, source)

    def test_second_expansion_never_sent_even_if_still_short(self):
        source = sample(SMALL, 'custom', 600)
        replacement, _, _ = simulated_expansion(source, SMALL, extra=1)
        client, calls = fake_client([reply(source), reply(replacement)])
        _, text, count = generate_article(client, 'gpt-4.1', SMALL, 'Cybersicherheit', 800)
        self.assertLess(count, 700)
        self.assertGreater(count, 600)
        self.assertEqual(len(calls), 2)
        self.assertEqual(render_text(text, SMALL)[1], [])

    def test_expansion_and_missing_links_share_one_request_then_links_only(self):
        source = sample(SMALL, 'custom', 600, ('Backup',))
        replacement, _, _ = simulated_expansion(source, SMALL)
        # Merge without inserting the missing link, so the third request repairs only that link.
        from text_engine import _merge_paragraph_patch
        draft = assess_article(source, SMALL)
        _, options, insert = _repair_options(draft, SMALL, 800, expand=True)
        intermediate, _ = _merge_paragraph_patch(replacement, draft, SMALL, options, insert)
        blocks, repairs, _ = _repair_options(assess_article(intermediate, SMALL), SMALL, 800)
        repair = '\n\n'.join(blocks[o['paragraph_index']] + ' Backup.' for o in repairs)
        client, calls = fake_client([reply(source), reply(replacement), reply(repair)])
        attempts = []
        _, text, _ = generate_article(client, 'gpt-4.1', SMALL, 'Cybersicherheit', 800, on_attempt=attempts.append)
        self.assertEqual(len(calls), 3)
        self.assertEqual([a['operation'] for a in attempts],
                         ['complete_article', 'expand_and_repair_paragraphs', 'repair_paragraph'])
        self.assertEqual(render_text(text, SMALL)[1], [])
        self.assertNotIn('Erweiterungsziel', calls[2]['messages'][-1]['content'])

    def test_combined_request_can_finish_both_length_and_links(self):
        source = sample(SMALL, 'custom', 600, ('Backup',))
        replacement, _, _ = simulated_expansion(source, SMALL)
        client, calls = fake_client([reply(source), reply(replacement + ' Backup.')])
        _, text, count = generate_article(client, 'gpt-4.1', SMALL, 'Cybersicherheit', 800)
        self.assertEqual(len(calls), 2)
        self.assertEqual(count, 801)
        self.assertEqual(render_text(text, SMALL)[1], [])

    def test_failed_expansions_keep_complete_original_and_download_warning(self):
        source = sample(SMALL, 'custom', 600)
        replacement, _, _ = simulated_expansion(source, SMALL)
        for bad in (replacement.replace('Backup', 'Kopie'), '{invalid JSON}',
                    replacement.replace('Prüfung', 'Abschließend lässt sich sagen, dass Sicherheit gilt.', 1)):
            with self.subTest(bad=bad[:20]), tempfile.TemporaryDirectory() as temp:
                helper = advisory.AdvisoryGenerationTests()
                page, files, calls = helper.post(temp, SMALL, 'custom', [reply(source), reply(bad)])
                self.assertEqual(len(calls), 2)
                self.assertIn('kürzer als gewünscht', page)
                self.assertIn('alle eingegebenen Linktexte verlinkt', page)
                self.assertNotIn('Unvollständiger Entwurf', page)
                self.assertEqual(next(p for p in files if p.suffix == '.txt').read_text(encoding='utf-8'), source)

    def test_api_error_stops_and_preserves_complete_original_download(self):
        from test_engine_acceptance import httpx
        from openai import RateLimitError
        source = sample(SMALL, 'custom', 600)
        error = RateLimitError('mock quota', response=httpx.Response(429, request=httpx.Request('POST', 'https://example.org')),
                               body={'code': 'insufficient_quota'})
        with tempfile.TemporaryDirectory() as temp:
            page, files, calls = advisory.AdvisoryGenerationTests().post(temp, SMALL, 'custom', [reply(source), error])
            self.assertEqual(len(calls), 2)
            self.assertIn('API-Guthaben', page)
            self.assertIn('kürzer als gewünscht', page)
            self.assertNotIn('Unvollständiger Entwurf', page)
            self.assertEqual(next(p for p in files if p.suffix == '.txt').read_text(encoding='utf-8'), source)


@unittest.skipUnless(FIXTURES.exists(), 'Private saved Windows articles remain local only.')
class SavedWindowsExpansionTests(unittest.TestCase):
    def test_saved_articles_expand_or_skip_and_preserve_every_url_and_protected_paragraph(self):
        results = []
        self.assertEqual(len(list(FIXTURES.glob('*.json'))), 6)
        for path in sorted(FIXTURES.glob('*.json')):
            data = json.loads(path.read_text())
            source, pairs = data['text'], data['pairs']
            replacement, options, insert = simulated_expansion(source, pairs, site=data['site'])
            self.assertFalse(insert)
            expands = data['words'] < 700
            client, calls = fake_client([reply(source), reply(replacement)])
            _, final, words = generate_article(client, 'gpt-4.1', pairs, data['topic'], 800, template=data['site'])
            self.assertEqual(len(calls), 2 if expands else 1)
            self.assertEqual(words, 800 if expands else data['words'])
            self.assertEqual(render_text(final, pairs)[1], [])
            before, after = re.split(r'(\n\s*\n)', source), re.split(r'(\n\s*\n)', final)
            selected = {o['paragraph_index'] for o in options} if expands else set()
            self.assertEqual(len(before), len(after))
            for i, old in enumerate(before):
                if i % 2 or i // 2 not in selected:
                    self.assertEqual(after[i], old)
            with tempfile.TemporaryDirectory() as temp:
                page, files, web_calls = advisory.AdvisoryGenerationTests().post(temp, pairs, data['site'],
                                                                       [reply(source), reply(replacement)])
                self.assertEqual(len(web_calls), len(calls))
                self.assertNotIn('kürzer als gewünscht', page)
                self.assertEqual(next(p for p in files if p.suffix == '.txt').read_bytes().decode('utf-8'), final)
            results.append({'name':data['name'],'original_words':data['words'],'simulated_final_words':words,
                            'coverage':f'{len(pairs)}/{len(pairs)}','calls_simulated':len(calls),
                            'expanded_paragraphs':[i+1 for i in sorted(selected)],
                            'protected_text_and_urls':'preserved','downloads':'HTTP 200, exact saved bytes'})
        (FIXTURES.parent/'simulation-results.json').write_text(json.dumps(
            {'scope':'OFFLINE_SIMULATION_NOT_NEW_GENERATION_OR_CONTENT_APPROVAL','results':results},ensure_ascii=False,indent=2))

    def test_all_short_saved_articles_keep_original_after_rejected_expansion(self):
        for path in sorted(FIXTURES.glob('*.json')):
            data = json.loads(path.read_text())
            if data['words'] >= 700: continue
            source, pairs = data['text'], data['pairs']
            replacement, options, _ = simulated_expansion(source, pairs, site=data['site'])
            # Remove every approved occurrence of one existing URL in editable passages.
            # Choose an URL not repeated in protected text, to exercise actual coverage loss.
            from text_engine import _link_pattern
            pattern, keys = _link_pattern(pairs)
            protected = '\n\n'.join(p for i,p in enumerate(re.split(r'\n\s*\n',source))
                                    if i not in {o['paragraph_index'] for o in options})
            covered_protected = set(pairs)-set(render_text(protected,pairs)[1])
            editable_only = [key for o in options for key in o['existing'] if key not in covered_protected]
            if editable_only:
                lost = editable_only[0]
                bad = pattern.sub(lambda m: 'SIMULIERTER_LINKVERLUST' if keys[int(m.lastgroup[4:])]==lost else m.group(), replacement)
                reason = 'lost_linktexts'
            else:
                # All URLs also survive in protected text: exercise malformed expansion instead.
                bad, reason = '{invalid expansion}', 'invalid_plain_text_patch'
            records = []
            client, calls = fake_client([reply(source), reply(bad)])
            _, final, words = generate_article(client,'gpt-4.1',pairs,data['topic'],800,
                                              template=data['site'],on_draft=records.append)
            self.assertEqual((final, words), (source, data['words']))
            self.assertEqual(len(calls), 2)
            self.assertEqual(records[-1]['rejection_reasons'], [reason])
            with tempfile.TemporaryDirectory() as temp:
                page, files, _ = advisory.AdvisoryGenerationTests().post(temp,pairs,data['site'],[reply(source),reply(bad)])
                self.assertIn('kürzer als gewünscht', page)
                self.assertEqual(next(p for p in files if p.suffix=='.txt').read_bytes().decode('utf-8'), source)
