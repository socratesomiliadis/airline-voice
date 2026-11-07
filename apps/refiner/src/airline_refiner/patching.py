"""Locate diagnosed Python functions and constrain edits to those functions."""

import ast
from typing import cast


def find_function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def visit(node: ast.AST, scope: str = "") -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = f"{scope}.{node.name}" if scope else node.name
            if scope == name and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                matches.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree)
    if len(matches) != 1:
        raise ValueError(f"Function {name} must identify exactly one existing function")
    return matches[0]


def function_bounds(source: str, name: str) -> tuple[int, int]:
    node = find_function(ast.parse(source), name)
    lines = source.splitlines(keepends=True)
    start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
    return sum(map(len, lines[: start - 1])), sum(map(len, lines[: node.end_lineno]))


def validate_function_changes(original: str, candidate: str, names: set[str]) -> None:
    """Mask diagnosed definitions and reject any other structural change in the file."""

    def surrounding_structure(source: str) -> str:
        tree = ast.parse(source)
        targets = {id(find_function(tree, name)) for name in names}

        class Mask(ast.NodeTransformer):
            def visit(self, node: ast.AST) -> ast.AST:
                if id(node) in targets:
                    return ast.Pass()
                return cast(ast.AST, super().visit(node))

        return ast.dump(Mask().visit(tree), include_attributes=False)

    if surrounding_structure(original) != surrounding_structure(candidate):
        raise ValueError("Patch changes code outside the diagnosed functions")
