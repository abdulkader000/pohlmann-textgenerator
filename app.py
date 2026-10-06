import argparse
import datetime
import json
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

from text_engine import generate_article, parse_pairs, render_text, word_count

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
load_dotenv(APP_DIR / '.env')
OUTPUT_DIR = APP_DIR / 'outputs'
site_data = json.loads((RESOURCE_DIR / 'site_data.json').read_text(encoding='utf-8'))
app = Flask(__name__, template_folder=str(RESOURCE_DIR / 'templates'))
app.config['MAX_CONTENT_LENGTH'] = 100_000
app.config['DEMO_MODE'] = False
app.config['SHUTDOWN_TOKEN'] = uuid.uuid4().hex


def demo_article(pairs, target):
    intro = 'DEMO – Dies ist ein lokaler Funktionstest, kein KI-generierter Artikel.\n\n' + '. '.join(pairs) + '.\n\n'
    sentence = 'Informationssicherheit braucht klare Verantwortlichkeiten, praktische Schulungen und regelmäßig überprüfte Schutzmaßnahmen im betrieblichen Alltag. '
    return intro + ' '.join((sentence * target).split()[:max(0, target - word_count(intro))])


@app.route('/', methods=['GET', 'POST'])
def index():
    state = dict(site='custom', custom_site_name='', topic='Cybersicherheit', words='800', pairs='')
    result, filename, count, error = None, None, None, None
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
                result, text, count = generate_article(client, os.getenv('OPENAI_MODEL', 'gpt-4'), pairs, state['topic'].strip(), target)
            label = state['custom_site_name'] if state['site'] == 'custom' else state['site']
            label = re.sub(r'[^\w-]+', '_', label or 'Artikel')[:70]
            suffix = datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
            filename = ('DEMO_' if app.config['DEMO_MODE'] else '') + f'{label}_{suffix}.html'
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            document = '<!doctype html><html lang="de"><meta charset="utf-8"><title>Artikel</title><body>' + result + '</body></html>'
            (OUTPUT_DIR / filename).write_text(document, encoding='utf-8')
            (OUTPUT_DIR / filename.replace('.html', '.txt')).write_text(text, encoding='utf-8')
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
            result, filename = None, None
    return render_template('index.html', state=state, sites=site_data, site_data=site_data,
                           result=result, filename=filename, count=count, error=error, demo=app.config['DEMO_MODE'], shutdown_token=app.config['SHUTDOWN_TOKEN'])


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
