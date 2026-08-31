"""Skill 配置存储：配置驱动，新增业务能力只需往 skills/config/ 增加 JSON 配置。

字段：skill_id / name / desc / access_level / cost_point / system_prompt /
      output_json_schema / model_params / ui_meta。
"""

import json
from pathlib import Path

from app.core.errors import BizError

DEFAULT_SKILL_ID = "screenshot_xhs_analyze"

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "config"


def _all_configs() -> dict[str, dict]:
    configs: dict[str, dict] = {}
    if not _CONFIG_DIR.exists():
        return configs
    for f in sorted(_CONFIG_DIR.glob("*.json")):
        try:
            data = json.loads((f.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            continue
        skill_id = data.get("skill_id")
        if skill_id and isinstance(data, dict):
            configs[skill_id] = data
    return configs


def load_config(skill_id: str) -> dict:
    cfg = _all_configs().get(skill_id)
    if cfg is None:
        raise BizError(f"Skill 不存在: {skill_id}", code=40400, status_code=404)
    return cfg


def list_skills() -> list[dict]:
    return [
        {
            "skill_id": c["skill_id"],
            "name": c.get("name", c["skill_id"]),
            "desc": c.get("desc", ""),
            "access_level": int(c.get("access_level") or 0),
            "cost_point": int(c.get("cost_point") or 0),
        }
        for c in sorted(_all_configs().values(), key=lambda x: x.get("skill_id", ""))
    ]


def get_detail(skill_id: str) -> dict:
    cfg = load_config(skill_id)
    return {
        "skill_id": cfg["skill_id"],
        "name": cfg.get("name", ""),
        "desc": cfg.get("desc", ""),
        "access_level": int(cfg.get("access_level") or 0),
        "cost_point": int(cfg.get("cost_point") or 0),
        "model_params": cfg.get("model_params") or {},
        "ui_meta": cfg.get("ui_meta") or {},
    }


def task_cost(skill_id: str, draw_image: bool = False) -> int:
    cfg = load_config(skill_id)
    total = int(cfg.get("cost_point") or 0)
    if draw_image:
        from app.services.skills import get_meta

        draw_meta = get_meta("skill_ai_draw") or {}
        total += int(draw_meta.get("cost_point") or 0)
    return total