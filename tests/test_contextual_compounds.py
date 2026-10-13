"""Explicit observed compounds, unchanged visible text and independent URL ownership."""
from html.parser import HTMLParser
import unittest
from text_engine import article_plan, generation_prompt, render_text, writing_link_forms


class Content(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.text = ''
        self.feed(source)

    def handle_data(self, data):
        self.text += data


class ContextualCompoundTests(unittest.TestCase):
    def test_base_only_links_preserve_visible_compounds(self):
        pairs = {key: 'https://example.org/' + key for key in ('eIDAS', 'Malware', 'TLS')}
        source = 'Die eIDAS-Verordnung, ein Malware-Anhang und TLS-geschützte Kanäle.'
        rendered, missing = render_text(source, pairs)
        self.assertEqual(missing, [])
        self.assertEqual(Content(rendered).text, source)
        for base, suffix in [('eIDAS', '-Verordnung'), ('Malware', '-Anhang'), ('TLS', '-geschützte')]:
            self.assertIn(f'<a href="{pairs[base]}">{base}</a>{suffix}', rendered)
        self.assertEqual(render_text(source.swapcase(), pairs)[1], [])

    def test_reject_arbitrary_prefixes_suffixes_and_compounds(self):
        for base, texts in {
            'eIDAS': ['XeIDAS-Verordnung', 'eIDAS-Verordnungsentwurf', 'eIDAS-Verordnung-Text', 'eIDAS-Vertrag'],
            'Malware': ['Antimalware-Anhang', 'Malware-Anhangdatei', 'Malware-Anhang-Test', 'Malware-Scanner'],
            'TLS': ['XTLS-geschützte', 'TLS-geschütztes', 'TLS-geschützteNetze', 'TLS-geschützte-Netze', 'TLS-Verbindung'],
        }.items():
            for source in texts:
                with self.subTest(source=source):
                    rendered, missing = render_text(source, {base: 'https://example.org/base'})
                    self.assertEqual(missing, [base])
                    self.assertNotIn('<a ', rendered)

    def test_longer_and_separately_entered_labels_own_their_urls(self):
        for base, phrase in [('eIDAS', 'eIDAS-Verordnung'), ('Malware', 'Malware-Anhang'),
                             ('TLS', 'TLS-geschützte Kanäle')]:
            pairs = {base: 'https://example.org/base', phrase: 'https://example.org/long'}
            rendered, missing = render_text(phrase, pairs)
            self.assertEqual(missing, [base])
            self.assertEqual(rendered, f'<p><a href="{pairs[phrase]}">{phrase}</a></p>')
            rendered, missing = render_text(phrase + '; ' + base + '.', pairs)
            self.assertEqual(missing, [])
            self.assertEqual(rendered.count('href="https://example.org/base"'), 1)

    def test_recognition_does_not_add_writing_choices(self):
        pairs = {key: 'https://example.org/' + key for key in ('eIDAS', 'Malware', 'TLS', 'DORA', 'DSA')}
        forms = writing_link_forms(pairs)
        self.assertEqual({key: forms[key] for key in ('eIDAS', 'Malware', 'TLS')},
                         {'eIDAS': ('eIDAS',), 'Malware': ('Malware',), 'TLS': ('TLS',)})
        prompt = generation_prompt(pairs, 'Cybersicherheit', 800, article_plan(pairs, 'Cybersicherheit', 800))
        for compound in ('eIDAS-Verordnung', 'Malware-Anhang', 'TLS-geschützte'):
            self.assertNotIn(compound, prompt)
        rendered, missing = render_text('DORA- und DSA-Vorgaben', pairs)
        self.assertNotIn('DORA', missing)
        self.assertNotIn('DSA', missing)
        self.assertIn('>DORA-</a>', rendered)
