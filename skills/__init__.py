import importlib
import pkgutil

REGISTRY: dict[str, dict] = {}


def load_skills(package: str = "skills"):
    pkg = importlib.import_module(package)
    found = {}
    for modinfo in pkgutil.iter_modules(pkg.__path__):
        if modinfo.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{package}.{modinfo.name}")
        meta = getattr(mod, "skill_meta", None)
        if meta and isinstance(meta, dict) and meta.get("name"):
            found[meta["name"]] = {"meta": meta, "module": mod}
    REGISTRY.clear()
    REGISTRY.update(found)
    return REGISTRY


def get_skill(name: str) -> dict | None:
    if not REGISTRY:
        load_skills()
    return REGISTRY.get(name)