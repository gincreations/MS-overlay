"""Keep Python3.10 source contracts comparable on newer AST schemas."""
import ast
import copy

def legacy_dump(node):
    node=copy.deepcopy(node)
    for child in ast.walk(node):
        if hasattr(child,'type_params'):
            if child.type_params:
                raise AssertionError('New generic type parameters require explicit contract review')
            child._fields=tuple(f for f in child._fields if f!='type_params')
    try:
        return ast.dump(node,show_empty=True)
    except TypeError:
        return ast.dump(node)
