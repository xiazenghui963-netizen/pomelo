from app.core.errors import BizError
from skills import REGISTRY, get_skill, load_skills


def ensure_loaded() -> None:
    if not REGISTRY:
        load_skills()


def get_meta(name: str) -> dict | None:
    ensure_loaded()
    entry = get_skill(name)
    return entry.get("meta") if entry else None


def skill_names() -> list[str]:
    ensure_loaded()
    return list(REGISTRY.keys())


def pipeline_steps(task_type: str, has_image: bool, draw_image: bool) -> list[str]:
    steps: list[str] = []
    if task_type == "create_content":
        if has_image:
            steps.append("skill_vlm_parse_image")
        steps += ["skill_decompose_post", "skill_generate_title", "skill_generate_note", "skill_gen_tags"]
        if draw_image:
            steps.append("skill_ai_draw")
    elif task_type == "rewrite":
        steps = ["skill_human_rewrite"]
    return steps


def member_cost_map() -> dict[str, int]:
    ensure_loaded()
    return {
        name: entry["meta"]["cost_point"]
        for name, entry in REGISTRY.items()
        if entry["meta"].get("access_level") == 1
    }


def pipeline_cost(task_type: str, has_image: bool, draw_image: bool) -> int:
    total = 0
    for name in pipeline_steps(task_type, has_image, draw_image):
        meta = get_meta(name)
        if meta:
            total += meta.get("cost_point", 0)
    return total


def member_access_required(task_type: str, has_image: bool, draw_image: bool) -> list[str]:
    member_names = set(member_cost_map().keys())
    return [n for n in pipeline_steps(task_type, has_image, draw_image) if n in member_names]


def validate_member_access(task_type: str, has_image: bool, draw_image: bool, is_member: bool) -> None:
    locked = member_access_required(task_type, has_image, draw_image)
    if locked and not is_member:
        raise BizError("该功能为会员专属，请先开通会员", code=40301, status_code=403)


def execute_skill(name: str, params: dict, llm_client) -> dict:
    ensure_loaded()
    entry = get_skill(name)
    if entry is None:
        raise BizError(f"Skill 不存在: {name}", code=40400, status_code=404)
    return entry["module"].execute(params, llm_client)