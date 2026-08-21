from __future__ import annotations


class ModelsNamespace:
    def __init__(self, **kwargs):
        self._models = kwargs

    def __getattr__(self, name: str):
        if name in self._models:
            return self._models[name]
        raise AttributeError(f"Model '{name}' not found in the namespace.")
