"""Build and package the Windows executable; never copy a real API key."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv
import zipfile

ROOT = Path(__file__).resolve().parent
RELEASE_FILES = ('TextGenerator.exe', '.env', 'ANLEITUNG.txt')
# Fixed public configuration: never copy .env or an edited .env.example.
RELEASE_ENV = 'OPENAI_API_KEY=YOUR_API_KEY_HERE\nOPENAI_MODEL=gpt-4\n'


def validate_archive(archive):
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(RELEASE_FILES) or set(names) != set(RELEASE_FILES):
            raise ValueError('Die Liefer-ZIP muss ausschließlich die drei vorgesehenen Dateien enthalten.')
        if z.testzip() is not None:
            raise ValueError('Die Liefer-ZIP ist beschädigt.')
        if z.read('.env') != RELEASE_ENV.encode('utf-8'):
            raise ValueError('Die Liefer-ZIP darf nur die feste Platzhalter-Konfiguration enthalten.')
        with z.open('TextGenerator.exe') as executable:
            if executable.read(2) != b'MZ':
                raise ValueError('Die Liefer-ZIP enthält keine Windows-EXE.')


def package_release():
    release = ROOT / 'release' / 'TextGenerator'
    release.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'dist' / 'TextGenerator.exe', release / 'TextGenerator.exe')
    (release / '.env').write_text(RELEASE_ENV, encoding='utf-8', newline='\n')
    shutil.copy2(ROOT / 'ANLEITUNG.txt', release / 'ANLEITUNG.txt')
    archive = ROOT / 'release' / 'TextGenerator_Windows.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in RELEASE_FILES:
            z.write(release / name, name)
    validate_archive(archive)
    return archive


def main():
    if sys.platform != 'win32':
        raise SystemExit('Die Windows-EXE muss auf Windows gebaut werden.')
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 oder neuer installieren und erneut starten.')
    os.chdir(ROOT)
    env = ROOT / '.build-venv'
    if not (env / 'Scripts' / 'python.exe').exists():
        venv.EnvBuilder(with_pip=True).create(env)
    python = str(env / 'Scripts' / 'python.exe')
    subprocess.run([python, '-m', 'pip', 'install', '-r', 'requirements.txt', 'pyinstaller'], check=True)
    subprocess.run([python, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], check=True)
    subprocess.run([python, '-m', 'PyInstaller', '--noconfirm', '--clean', 'app.spec'], check=True)
    archive = package_release()
    print('Fertig:', archive)
    print('Die ZIP enthält einen Platzhalter-Schlüssel. Die zuständige Person konfiguriert .env nur lokal neben der entpackten EXE. Keine konfigurierte .env in das Liefer-Archiv übernehmen.')
    print('Vorläufige Lieferung: Windows-EXE einschließlich Browserstart, Demo, Downloads, Beenden und Neustart prüfen. Echten Live-Test mit zwei Artikeln erst nach verfügbarem API-Guthaben durchführen.')

if __name__ == '__main__':
    main()
