import zipfile
from pathlib import Path

SOURCE = Path('seekquel_sync')
OUTPUT = Path('dist') / 'Seekquel Sync.zip'
SKIP_DIRS = {'__pycache__'}
SKIP_SUFFIXES = {'.pyc'}


def files():
    for path in sorted(SOURCE.rglob('*')):
        if not path.is_file():
            continue

        if SKIP_DIRS.intersection(path.parts):
            continue

        if path.suffix in SKIP_SUFFIXES:
            continue

        yield path


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files():
            archive.write(path, path.relative_to(SOURCE).as_posix())

    print(f'Wrote {OUTPUT}')


if __name__ == '__main__':
    main()
