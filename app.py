import argparse
import datetime
from dataclasses import asdict
import json
import html
import math
import os
from pathlib import Path
import re
import sys
import threading
import uuid
import webbrowser

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_from_directory, abort
from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError, APIError
from werkzeug.serving import make_server

from text_engine import (ArticleDraft, ArticleGenerationError, generate_article, parse_pairs,
                         render_text, word_count, pending_link_issues)

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
load_dotenv(APP_DIR / '.env')
OUTPUT_DIR = APP_DIR / 'outputs'
DIAGNOSTIC_DIR = APP_DIR / 'diagnostics'
site_data = json.loads((RESOURCE_DIR / 'site_data.json').read_text(encoding='utf-8'))
app = Flask(__name__, template_folder=str(RESOURCE_DIR / 'templates'))
app.config['MAX_CONTENT_LENGTH'] = 100_000
app.config['DEMO_MODE'] = False
app.config['SHUTDOWN_TOKEN'] = uuid.uuid4().hex


def demo_article(pairs, target):
    intro = 'DEMO – Dies ist ein lokaler Funktionstest, kein KI-generierter Artikel.\n\n' + '. '.join(pairs) + '.\n\n'
    sentence = 'Informationssicherheit braucht klare Verantwortlichkeiten, praktische Schulungen und regelmäßig überprüfte Schutzmaßnahmen im betrieblichen Alltag. '
    return intro + ' '.join((sentence * target).split()[:max(0, target - word_count(intro))])


def save_generation_failure(state, pairs, model, drafts, attempts, error, key):
    """Local failure evidence only: explicit fields, no environment or SDK exception dump."""
    best = getattr(error, 'best_draft', None) or (drafts[-1]['best'] if drafts else None)
    report = {
        'status': 'REJECTED_PENDING_REVIEW', 'inputs': dict(state), 'pairs': dict(pairs),
        'requested_model': model, 'attempts': attempts,
        'failure': {'type': type(error).__name__, 'status_code': getattr(error, 'status_code', None),
                    'message': str(error) if isinstance(error, ArticleGenerationError) else 'API request failed'},
        'best_draft': asdict(best) if best is not None else None,
        'drafts': [{name: asdict(value) if isinstance(value, ArticleDraft) else value
                    for name, value in record.items()} for record in drafts],
    }

    def redact(value):
        if isinstance(value, str):
            return value.replace(key, '[REDACTED_API_KEY]') if key else value
        if isinstance(value, dict):
            return {redact(name): redact(item) for name, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [redact(item) for item in value]
        return value

    folder = DIAGNOSTIC_DIR / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'report.json').write_text(json.dumps(redact(report), ensure_ascii=False, indent=2), encoding='utf-8')
    if best is not None:
        (folder / 'REJECTED_BEST.txt').write_text(redact(best.text), encoding='utf-8')
        document = ('<!doctype html><html lang="de"><meta charset="utf-8"><title>Abgelehnter Entwurf</title>'
                    '<body><p>Abgelehnter Entwurf – unvollständig, nicht zur Veröffentlichung freigegeben.</p>'
                    '<article>' + best.rendered + '</article></body></html>')
        (folder / 'REJECTED_BEST.html').write_text(redact(document), encoding='utf-8')
    return folder


@app.route('/', methods=['GET', 'POST'])
def index():
    state = dict(site='custom', custom_site_name='', topic='Cybersicherheit', words='800', pairs='')
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1')
    result, text, filename, count, error = None, None, None, None, None
    incomplete, missing, length_notice, format_notice = False, [], None, None
    pending = {}
    diagnostic_folder, diagnostic_error, failed_best = None, False, None
    if request.method == 'POST':
        state.update({key: request.form.get(key, state[key]) for key in state})
        try:
            target = int(state['words'])
            if not 200 <= target <= 2000:
                raise ValueError('Die Zielwortzahl muss zwischen 200 und 2000 liegen.')
            if not state['topic'].strip() or len(state['topic']) > 300:
                raise ValueError('Bitte ein Thema mit maximal 300 Zeichen eingeben.')
            # The visible textarea is authoritative: removed preset links stay removed.
            pairs = parse_pairs(state['pairs'])
            pending = pending_link_issues(pairs)
            if app.config['DEMO_MODE']:
                text = demo_article(pairs, target)
                result, missing = render_text(text, pairs)
                if missing:
                    raise ValueError('Demo: überlappende Linktexte bitte separat eingeben.')
                count = word_count(text)
            else:
                key = os.getenv('OPENAI_API_KEY', '').strip()
                if not key or key == 'YOUR_API_KEY_HERE':
                    raise ValueError('Der Zugang ist noch nicht eingerichtet. Bitte die zuständige Person bitten, den API-Schlüssel in der Konfigurationsdatei neben dem Programm einzutragen.')
                client = OpenAI(api_key=key, timeout=120, max_retries=0)
                drafts, attempts = [], []

                def observe(record):
                    attempts.append(record)
                    observer = app.config.get('GENERATION_OBSERVER')
                    if observer is not None:
                        observer(record)

                try:
                    result, text, count = generate_article(
                        client, model, pairs, state['topic'].strip(), target,
                        template=state['site'], on_attempt=observe, on_draft=drafts.append)
                except (ValueError, APIError) as exc:
                    failed_best = getattr(exc, 'best_draft', None) or (drafts[-1]['best'] if drafts else None)
                    try:
                        diagnostic_folder = save_generation_failure(state, pairs, model, drafts, attempts, exc, key)
                    except OSError:
                        diagnostic_error = True
                    raise
        except ValueError as exc:
            error = str(exc)
            result, filename = None, None
        except AuthenticationError:
            error = 'Der API-Schlüssel wurde abgelehnt. Bitte einen gültigen Schlüssel konfigurieren.'
        except RateLimitError as exc:
            body = exc.body if isinstance(exc.body, dict) else {}
            detail = body.get('error', body)
            detail = detail if isinstance(detail, dict) else {}
            if detail.get('code') in ('credit_balance_exhausted', 'insufficient_quota') or detail.get('type') == 'insufficient_quota':
                error = 'Das API-Guthaben ist aufgebraucht oder das Nutzungslimit erreicht. Bitte die zuständige Person bitten, das API-Konto aufzuladen bzw. das Limit zu prüfen. Danach erneut versuchen. Ihre Eingaben bleiben hier erhalten.'
            else:
                error = 'Zurzeit werden zu viele Anfragen gestellt. Bitte kurz warten und erneut versuchen. Ihre Eingaben bleiben hier erhalten.'
        except APIConnectionError:
            error = 'Die API ist nicht erreichbar oder hat zu lange gebraucht. Bitte die Verbindung prüfen.'
        except APIError as exc:
            if getattr(exc, 'status_code', None) == 404:
                error = 'Das konfigurierte KI-Modell ist nicht verfügbar. Bitte die zuständige Person bitten, Modellname und Zugriffsrechte zu prüfen.'
            else:
                error = 'Der KI-Dienst konnte die Anfrage nicht bearbeiten. Bitte erneut versuchen; bei wiederholtem Fehler die zuständige Person informieren.'
        except OSError:
            error = 'Die Ergebnisdateien konnten nicht gespeichert werden. Bitte Schreibrechte im Programmordner prüfen.'
        if error:
            if failed_best is not None and failed_best.missing and 'Fehlende Linktexte:' not in error:
                error += ' Fehlende Linktexte: ' + ', '.join(failed_best.missing) + '.'
            if diagnostic_folder is not None:
                error += ' Diagnose lokal gespeichert: diagnostics/' + diagnostic_folder.name + '.'
            elif diagnostic_error:
                error += ' Die lokale Diagnose konnte nicht gespeichert werden; Schreibrechte prüfen.'
            if failed_best is not None:
                result, text, count = failed_best.rendered, failed_best.text, failed_best.words
                incomplete, missing = bool(failed_best.missing), list(failed_best.missing)
        if result is not None and text is not None:
            if count < math.ceil(target * .875):
                length_notice = (f'Der Entwurf ist kürzer als gewünscht: {count} Wörter bei einem ungefähren Ziel von {target}. '
                                 'Der gesamte vorhandene Text bleibt herunterladbar; es wird nichts abgeschnitten.')
            best = failed_best or (drafts[-1]['best'] if not app.config['DEMO_MODE'] and drafts else None)
            if best is not None and best.problems:
                format_notice = 'Ausgabehinweise: ' + ', '.join(best.problems) + '. Text und Aufbau vor Verwendung prüfen.'
            label = state['custom_site_name'] if state['site'] == 'custom' else state['site']
            label = re.sub(r'[^\w-]+', '_', label or 'Artikel')[:70]
            suffix = datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
            status = 'Unvollständiger Entwurf' if incomplete else 'Artikelentwurf'
            prefix = 'DEMO_' if app.config['DEMO_MODE'] else 'UNVOLLSTAENDIGER_ENTWURF_' if incomplete else 'ENTWURF_'
            filename = prefix + f'{label}_{suffix}.html'
            notices = [] if app.config['DEMO_MODE'] else ['Entwurf – Inhalt und Sprache vor Veröffentlichung prüfen. Keine automatische Inhaltsfreigabe.']
            if incomplete:
                notices.insert(0, 'Unvollständiger Entwurf – nicht als vollständig freigegeben.')
                if missing:
                    notices.append('Fehlende Linktexte: ' + ', '.join(missing) + '.')
            notices.extend(note for note in (length_notice, format_notice) if note)
            document = ('<!doctype html><html lang="de"><meta charset="utf-8"><title>' + status + '</title><body>' +
                        ''.join('<p>' + html.escape(note) + '</p>' for note in notices) +
                        '<article>' + result + '</article></body></html>')
            # Complete TXT stays plain text; incomplete TXT carries a visible status header.
            saved_text = ('\n'.join(notices) + '\n\n' if incomplete else '') + text
            try:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                (OUTPUT_DIR / filename).write_text(document, encoding='utf-8')
                (OUTPUT_DIR / filename.replace('.html', '.txt')).write_text(saved_text, encoding='utf-8')
            except OSError:
                error = (error + ' ' if error else '') + 'Die Ergebnisdateien konnten nicht gespeichert werden. Bitte Schreibrechte prüfen.'
                filename = None
    return render_template('index.html', state=state, sites=site_data, site_data=site_data,
                           pending_issues=pending, incomplete=incomplete, missing=missing,
                           length_notice=length_notice, format_notice=format_notice,
                           result=result, filename=filename, count=count, error=error, demo=app.config['DEMO_MODE'], configured_model=model, shutdown_token=app.config['SHUTDOWN_TOKEN'])


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(str(OUTPUT_DIR), filename, as_attachment=True)


@app.route('/stop', methods=['POST'])
def stop():
    if request.form.get('token') != app.config['SHUTDOWN_TOKEN']:
        abort(403)
    shutdown = app.config.get('SHUTDOWN_CALLBACK')
    if shutdown:
        threading.Timer(.3, shutdown).start()
    return '<!doctype html><html lang="de"><meta charset="utf-8"><title>Textgenerator beendet</title><p>Das Programm wurde beendet. Sie können dieses Fenster schließen.</p></html>'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', help='Offline-Funktionstest ohne API-Aufrufe')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    app.config['DEMO_MODE'] = args.demo
    server = make_server('127.0.0.1', args.port, app, threaded=True)
    app.config['SHUTDOWN_CALLBACK'] = server.shutdown
    url = f'http://127.0.0.1:{server.server_port}'
    if sys.stdout is not None:
        print(f'Textgenerator: {url}', flush=True)
    if not args.no_browser:
        threading.Timer(.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        if sys.platform == 'win32' and getattr(sys, 'frozen', False):
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'Das Programm konnte nicht gestartet werden. Bitte vollständig entpacken und aus einem beschreibbaren Ordner starten. Bei wiederholtem Fehler die zuständige Person informieren.', 'Textgenerator', 0x10)
        else:
            raise
