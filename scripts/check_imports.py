import ast
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / 'seekquel_sync'

FORBIDDEN = (
    'calibre.gui2.ui',
    'calibre.gui2.preferences',
    'calibre.library',
    'calibre.db',
)

NESTED = (ast.FunctionDef, ast.AsyncFunctionDef)

BRANCHES = ('body', 'orelse', 'finalbody', 'handlers')


def is_forbidden(name):
    return any(name == prefix or name.startswith(prefix + '.') for prefix in FORBIDDEN)


def imported_names(node):
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    if node.level:
        return []

    return [node.module or '']


def module_scope_imports(tree):
    pending = list(tree.body)

    while pending:
        node = pending.pop()

        if isinstance(node, NESTED):
            continue

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node

        for branch in BRANCHES:
            pending.extend(getattr(node, branch, None) or [])


def failures():
    for path in sorted(SOURCE.rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

        for node in module_scope_imports(tree):
            for name in imported_names(node):
                if is_forbidden(name):
                    yield f'{path.relative_to(SOURCE.parent)}:{node.lineno}: {name}'


def main():
    found = sorted(failures())

    if not found:
        print('No module-scope imports of Calibre internals.')

        return 0

    print('Import these inside the function that needs them, never at module scope:')

    for failure in found:
        print(f'  {failure}')

    return 1


if __name__ == '__main__':
    sys.exit(main())
