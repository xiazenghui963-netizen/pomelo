from fastapi import APIRouter

from app.api import admin, auth, content, llm_config, materials, member, points, skills_api, tasks, upload

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(upload.router)
api_router.include_router(materials.router)
api_router.include_router(tasks.router)
api_router.include_router(points.router)
api_router.include_router(content.router)
api_router.include_router(member.router)
api_router.include_router(admin.router)
api_router.include_router(llm_config.router)
api_router.include_router(skills_api.router)