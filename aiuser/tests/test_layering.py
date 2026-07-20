"""Enforces the one-way import layering of the aiuser cog.

A module may only import aiuser modules from its own layer or below.
``if TYPE_CHECKING:`` imports are exempt (annotations only).
"""

import ast
from pathlib import Path

AIUSER_ROOT = Path(__file__).parent.parent

# package -> layer; lower layers must not import higher ones
LAYERS = {
    "config": 0,
    "types": 1,
    "utils": 1,
    "consent": 2,
    "providers": 2,  # llm/speech/vectorstore backend clients
    "functions": 3,
    "context": 4,
    "response": 5,
    "settings": 6,
    "dashboard": 6,
    "core": 7,  # composition root: builds services and attaches the UI mixins
}


def _iter_module_files():
    for path in sorted(AIUSER_ROOT.rglob("*.py")):
        relative = path.relative_to(AIUSER_ROOT)
        top = relative.parts[0]
        if top in ("tests", "__init__.py"):
            continue
        if top not in LAYERS:
            raise AssertionError(
                f"New top-level package {top!r} is not assigned a layer in "
                "tests/test_layering.py — add it to LAYERS."
            )
        yield top, path


def _runtime_aiuser_imports(tree: ast.Module):
    """Top-of-tree aiuser imports, skipping `if TYPE_CHECKING:` blocks."""

    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If):
                test = child.test
                is_type_checking = (
                    isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
                ) or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
                if is_type_checking:
                    # only walk the else-branch
                    for else_node in child.orelse:
                        yield from walk(else_node)
                    continue
            if isinstance(child, ast.ImportFrom) and child.module:
                if child.module == "aiuser" or child.module.startswith("aiuser."):
                    yield child.module, child.lineno
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    if alias.name == "aiuser" or alias.name.startswith("aiuser."):
                        yield alias.name, child.lineno
            yield from walk(child)

    yield from walk(tree)


def test_layering():
    violations = []

    for package, path in _iter_module_files():
        layer = LAYERS[package]
        tree = ast.parse(path.read_text(), filename=str(path))

        for module, lineno in _runtime_aiuser_imports(tree):
            parts = module.split(".")
            if len(parts) < 2:
                continue
            imported_package = parts[1]
            imported_layer = LAYERS.get(imported_package)
            if imported_layer is None:
                violations.append(
                    f"{path.relative_to(AIUSER_ROOT)}:{lineno} imports unknown "
                    f"package {module}"
                )
                continue
            if imported_layer > layer:
                violations.append(
                    f"{path.relative_to(AIUSER_ROOT)}:{lineno} "
                    f"[{package} L{layer}] imports {module} "
                    f"[L{imported_layer}] — imports must point downward"
                )

    assert not violations, "Layering violations:\n" + "\n".join(violations)
