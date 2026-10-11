from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import build_windows as build


class WindowsBuildTests(unittest.TestCase):
    def test_package_ignores_local_configuration_and_stale_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'dist').mkdir()
            # Fixture with an MZ header, not a compiled or runnable EXE.
            executable = b'MZ-test-fixture'
            (root / 'dist' / 'TextGenerator.exe').write_bytes(executable)
            (root / 'ANLEITUNG.txt').write_text('Vorläufige Lieferung', encoding='utf-8')
            for name in ('.env', '.env.example'):
                (root / name).write_text('OPENAI_API_KEY=NOT_A_REAL_KEY\n')
            release = root / 'release' / 'TextGenerator'
            release.mkdir(parents=True)
            (release / '.env').write_text('OPENAI_API_KEY=NOT_A_REAL_KEY\n')
            (release / 'old-output.html').write_text('old result')
            (release / 'source.py').write_text('old source')
            with patch.object(build, 'ROOT', root):
                archive = build.package_release()
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(z.namelist(), list(build.RELEASE_FILES))
                self.assertEqual(z.read('.env').decode(), build.RELEASE_ENV)
                self.assertIn('OPENAI_MODEL=gpt-4.1\n', z.read('.env').decode())
                self.assertEqual(z.read('TextGenerator.exe'), executable)

    def test_validator_rejects_extra_files_configuration_and_non_exe(self):
        cases = (
            {'source.py': b'print("unexpected")'},
            {'.env': b'OPENAI_API_KEY=NOT_A_REAL_KEY\n'},
            {'TextGenerator.exe': b'not an executable'},
        )
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'test.zip'
            for replacements in cases:
                with self.subTest(replacements=list(replacements)):
                    contents = {
                        'TextGenerator.exe': b'MZ-test-fixture',
                        '.env': build.RELEASE_ENV.encode(),
                        'ANLEITUNG.txt': b'provisional',
                    }
                    contents.update(replacements)
                    with zipfile.ZipFile(archive, 'w') as z:
                        for name, content in contents.items():
                            z.writestr(name, content)
                    with self.assertRaises(ValueError):
                        build.validate_archive(archive)

    def test_install_test_or_build_failure_prevents_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / '.build-venv' / 'Scripts'
            scripts.mkdir(parents=True)
            (scripts / 'python.exe').touch()
            for failed_step in range(3):
                outcomes = [None] * failed_step + [subprocess.CalledProcessError(1, 'simulated')]
                with self.subTest(failed_step=failed_step), \
                        patch.object(build, 'ROOT', root), \
                        patch.object(build.sys, 'platform', 'win32'), \
                        patch.object(build.sys, 'version_info', (3, 12, 0)), \
                        patch.object(build.os, 'chdir'), \
                        patch.object(build.subprocess, 'run', side_effect=outcomes) as run, \
                        patch.object(build, 'package_release') as package:
                    with self.assertRaises(subprocess.CalledProcessError):
                        build.main()
                    package.assert_not_called()
                    self.assertEqual(run.call_count, failed_step + 1)
                    self.assertTrue(all(call.kwargs['check'] for call in run.call_args_list))
                    self.assertFalse((root / 'release').exists())


if __name__ == '__main__':
    unittest.main()
