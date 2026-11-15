"""Download official SDK packages into this project, verifying published SHA-1."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent / 'tools'
PACKAGES = [
    ('platform-35_r02.zip', '0bb560a90a7a2cbd0dd8348224d518b638fe7949'),
    ('build-tools_r35_windows.zip', 'af059bb67cf7786f45ee0db85e2d24985df1b4b6'),
]


def download(item):
    name, digest = item
    ROOT.mkdir(exist_ok=True)
    with urlopen('https://dl.google.com/android/repository/' + name, timeout=60) as response:
        data = response.read()
    if hashlib.sha1(data).hexdigest() != digest:
        raise ValueError('Checksum inválido: ' + name)
    archive = ROOT / name
    archive.write_bytes(data)
    with ZipFile(archive) as package:
        for info in package.infolist():
            if not (ROOT / info.filename).resolve().is_relative_to(ROOT.resolve()):
                raise ValueError('Ruta no válida en el paquete SDK')
        package.extractall(ROOT)
    print('Verificado:', name)


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download, PACKAGES))
