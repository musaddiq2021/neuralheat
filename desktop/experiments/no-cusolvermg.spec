# -*- mode: python ; coding: utf-8 -*-
"""Historical isolated adapter; production now shares the validated Mg-free policy."""
from pathlib import Path

experiment_root = Path(SPECPATH).parents[1]
production = experiment_root / "desktop/NeuralHeat Studio.spec"
recipe = production.read_text(encoding="utf-8")
expected = "root = Path(SPECPATH).parent"
if recipe.count(expected) != 1:
    raise RuntimeError("Production recipe changed; review experimental path adaptation")
recipe = recipe.replace(expected, "root = Path(SPECPATH).parents[1]")
exec(compile(recipe, str(production), "exec"), globals())
