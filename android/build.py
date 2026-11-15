"""Build a standalone signed APK using the official Android build tools + JDK."""
from pathlib import Path
import json
import os
import secrets
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app'
BUILD = ROOT / 'build'
TOOLS = ROOT / 'tools' / 'android-15'
PLATFORM = ROOT / 'tools' / 'android-35' / 'android.jar'
SIGNING = ROOT / 'signing'


def run(*args, env=None):
    subprocess.run([str(arg) for arg in args], check=True, cwd=ROOT, env=env)


def main():
    for folder in (BUILD, BUILD / 'classes', BUILD / 'dex', APP / 'assets', SIGNING):
        folder.mkdir(parents=True, exist_ok=True)
    web = APP / 'web'
    html = (web / 'index.template.html').read_text(encoding='utf-8')
    data = json.loads((web / 'points.json').read_text(encoding='utf-8'))
    html = html.replace('/*DATA*/', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'))
    html = html.replace('/*CORE*/', (web / 'core.js').read_text(encoding='utf-8'))
    html = html.replace('/*UI*/', (web / 'ui.js').read_text(encoding='utf-8'))
    (APP / 'assets' / 'index.html').write_text(html, encoding='utf-8')
    run(TOOLS / 'aapt2.exe', 'compile', '--dir', APP / 'res', '-o', BUILD / 'resources.zip')
    run(TOOLS / 'aapt2.exe', 'link', '-o', BUILD / 'base.apk', '-I', PLATFORM,
        '--manifest', APP / 'AndroidManifest.xml', '-A', APP / 'assets', BUILD / 'resources.zip')
    source = APP / 'src' / 'ar' / 'com' / 'climaenruta' / 'neuquen' / 'MainActivity.java'
    run('javac', '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-classpath', PLATFORM,
        '-d', BUILD / 'classes', source)
    run('jar', 'cf', BUILD / 'classes.jar', '-C', BUILD / 'classes', '.')
    run('java', '-cp', TOOLS / 'lib' / 'd8.jar', 'com.android.tools.r8.D8', '--release',
        '--min-api', '26', '--lib', PLATFORM, '--output', BUILD / 'dex', BUILD / 'classes.jar')
    unsigned = BUILD / 'unsigned.apk'
    shutil.copyfile(BUILD / 'base.apk', unsigned)
    with zipfile.ZipFile(unsigned, 'a', zipfile.ZIP_DEFLATED) as apk:
        for dex in (BUILD / 'dex').glob('*.dex'):
            apk.write(dex, dex.name)
    run(TOOLS / 'zipalign.exe', '-f', '-p', '4', unsigned, BUILD / 'aligned.apk')
    password_file = SIGNING / 'password.txt'
    if not password_file.exists():
        password_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
    env = dict(os.environ, APK_STORE_PASS=password_file.read_text(encoding='utf-8').strip())
    key = SIGNING / 'clima-en-ruta.jks'
    if not key.exists():
        run('keytool', '-genkeypair', '-keystore', key, '-storetype', 'JKS', '-alias', 'clima-en-ruta',
            '-keyalg', 'RSA', '-keysize', '3072', '-validity', '10000',
            '-dname', 'CN=Clima en Ruta Neuquen', '-storepass:env', 'APK_STORE_PASS',
            '-keypass:env', 'APK_STORE_PASS', '-noprompt', env=env)
    apk = BUILD / 'Clima-en-Ruta-Neuquen-1.0.apk'
    run('java', '-jar', TOOLS / 'lib' / 'apksigner.jar', 'sign', '--ks', key,
        '--ks-key-alias', 'clima-en-ruta', '--ks-pass', 'env:APK_STORE_PASS',
        '--key-pass', 'env:APK_STORE_PASS', '--out', apk, BUILD / 'aligned.apk', env=env)
    run('java', '-jar', TOOLS / 'lib' / 'apksigner.jar', 'verify', '--verbose', apk)
    run(TOOLS / 'zipalign.exe', '-c', '-p', '4', apk)
    print('APK listo:', apk)


if __name__ == '__main__':
    main()
