"""Import preguiçoso: o módulo pesado só é carregado no primeiro uso (reduz o tempo de abertura do programa)."""
import importlib.util
import sys


def lazy_import(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise ImportError(name)
    spec.loader = importlib.util.LazyLoader(spec.loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
