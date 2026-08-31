# 青柚 AI（pomelo-ai）

网页版自媒体 AI 灵感工具：截图解析爆款内容做创作灵感 + 用户私有资料空间。
先做网页版，后端按 API 设计，后续可直接复用对接微信小程序。

## 定位与边界

- 支持的输入：上传截图（OCR/VLM 解析）、手动输入选题文本、引用私有资料
- 明确不做：链接爬取解析、网页抓取、批量采集、自动发布
- 全部能力直接调用 Skill，无复杂 Agent 多轮循环
- **不存储任何图片**：上传的截图仅在内存中暂存，交给 OCR/VLM 识别完成后立即丢弃；不写服务器磁盘、不上传任何云存储
- AI 绘图直接使用大模型返回的第三方图片链接，我方后端不下载、不保存该图片
- 用户数据按 `user_id` 严格隔离，后端统一做权限校验，不信任前端参数
- 会员与支付为模拟实现，不接入真实支付接口

## 技术栈

- 后端：Python FastAPI + SQLite
- 前端：HTML + TailwindCSS（CDN）+ 原生 JS
- 存储：仅 SQLite（无对象存储、无 COS）
- 任务：后端异步执行，前端轮询结果
- 技能：插件化 Skill 架构（`./skills/` 目录）

## 项目结构

```
app/
  main.py             FastAPI 入口（路由挂载、静态托管、启动生命周期）
  config.py           环境变量配置
  database.py         SQLAlchemy + SQLite 初始化
  models.py           数据模型（users/user_points/user_material/tasks/skill_call_log）
  schemas.py          请求/响应 Pydantic 模型
  deps.py             依赖：JWT 鉴权、管理员校验
  core/
    security.py       JWT 签发/校验、bcrypt 密码哈希
    errors.py         业务错误
    limiter.py        接口限流
    tasks.py          异步任务队列与 worker
  services/
    session_images.py 上传截图内存暂存区（识别后立即丢弃，不落盘、不存云）
    llm.py            LLM/VLM/OCR/绘图/相似度客户端（未配置时自动降级走 mock）
    points.py         点数：初始化、每日赠送、扣减/退款、流水线成本计算
    materials.py      私有资料校验与拼接（≤3 条、单条 ≤2000 字）
    skills.py         Skill 注册表访问与流水线编排
    jobs.py           异步任务执行器（生成/改写流水线，写入 skill_call_log）
    seed.py           种子管理员
  api/                auth / upload / materials / tasks / points / content / member / admin
skills/               插件化 Skill（每文件含 skill_meta + execute(params, llm_client)）
frontend/             登录/工作台/私有资料/任务结果/历史任务/用户中心
tests/                端到端冒烟测试
```

## 数据库表

| 表 | 说明 |
|---|---|
| users | 账号密码（bcrypt）、角色 |
| user_points | 点数余额、会员标记、每日赠送记录 |
| user_material | 私有资料（title/content，软删除） |
| tasks | 任务（类型/状态/输入/结果/扣点数/资料id，**无图片字段**） |
| skill_call_log | 全链路日志：user_id、OCR文本、prompt、模型输出、相似度、使用的资料id |
| user_llm_models | 用户多模型配置：type(text/image)、config_name、model_name、base_url、api_key（加密存储）、is_default、update_time |

## 依赖清单

```
fastapi  uvicorn[standard]  python-multipart
sqlalchemy  pydantic  pydantic-settings
PyJWT  bcrypt  httpx
tencentcloud-sdk-python-ocr   # 腾讯云 OCR（可选，未配置密钥时自动降级）
pytest
```

安装：

```bash
pip install -r requirements.txt
```

## 本地启动步骤

1. 复制环境变量示例并填写：

```bash
cp .env.example .env
```

最小可跑：只需设置 `SECRET_KEY`；未配置 LLM/OCR 时系统自动降级为 mock 输出。

2. 启动：

```bash
uvicorn app.main:app --reload --port 8000
```

3. 打开浏览器访问 `http://localhost:8000`（先注册/登录）。
默认种子管理员：`admin / admin123456`。管理员可在后端调用：

```
POST /api/admin/member   body: {"username": "xxx", "is_member": true}
```

## 环境变量说明（.env）

| 变量 | 说明 |
|---|---|
| SECRET_KEY | JWT 签名密钥，必填，务必替换 |
| TOKEN_EXPIRE_DAYS | token 有效期（天） |
| DATABASE_URL | 默认 `sqlite:///./pomelo.db` |
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | OpenAI 兼容大模型（全局默认，仅在用户未配置对应类型默认模型时使用） |
| VLM_BASE_URL / VLM_API_KEY / VLM_MODEL | 多模态图片理解 VLM（全局默认，图片类型未配置时使用，未配置密钥自动降级 OCR） |
| ENABLE_AI_SIMULATE | 模拟模式（最高优先级）：开启后忽略用户配置与全局默认，所有大模型调用返回模拟数据 |
| OCR_SECRET_ID / OCR_SECRET_KEY / OCR_REGION | 腾讯云 OCR（通用印刷体识别） |
| IMAGE_BASE_URL / IMAGE_API_KEY / IMAGE_MODEL | AI 绘图（OpenAI 兼容 images API，直接返回第三方 url） |
| SESSION_IMAGE_TTL | 上传截图内存暂存最长时间（秒），默认 900 |
| INITIAL_POINTS / FREE_DAILY_POINTS / MEMBER_DAILY_POINTS | 点数策略 |
| SIMILARITY_THRESHOLD | 改写相似度阈值（默认 0.35，超过给提醒） |
| MATERIAL_MAX_SELECT / MATERIAL_MAX_CHARS | 资料引用条数与单条长度上限 |
| TASK_WORKERS | 异步 worker 数 |
| RATE_LIMIT_REQUESTS / RATE_LIMIT_WINDOW | 接口限流 |
| ADMIN_USERNAME / ADMIN_PASSWORD | 种子管理员 |

## Skill 插件规范

每个 Skill 位于 `./skills/` 目录，单个文件包含：

1. `skill_meta`：name、description、access_level（0 免费 / 1 会员）、cost_point、parameters 定义
2. `execute(params, llm_client)`：执行函数，返回 dict

已实现 9 个 Skill：

| Skill | 点数 | 会员 | 说明 |
|---|---|---|---|
| skill_ocr_extract | 0 | 否 | 图片 OCR 提取文本（base64 直传，不存图片） |
| skill_vlm_parse_image | 8 | 否 | VLM 多模态解析；文本不足自动降级 OCR |
| skill_decompose_post | 0 | 否 | 爆款拆解：痛点/选题角度/写作框架 |
| skill_generate_title | 3 | 否 | 生成多组小红书风格标题 |
| skill_generate_note | 5 | 否 | 生成笔记正文 |
| skill_gen_tags | 1 | 否 | 生成话题标签 |
| skill_human_rewrite | 8 | 是 | 正文改写（活人感写作，适配自 human-writing）：防洗稿强制要求、硬禁令检查（冒号/破折号/翻案腔/黑话/名词化）、命中自动修复一轮、改写后相似度校验 |
| skill_similarity_check | 0 | 否 | 文本相似度工具 |
| skill_ai_draw | 10 | 是 | AI 绘图：直接返回第三方图片链接，不下载不保存 |

任务流水线（create_content）：上传截图（内存）→VLM/OCR→爆款拆解→标题→正文→标签→（可选）配图；
rewrite 任务：原文+私有资料→活人感改写（skill_human_rewrite，含防洗稿+硬禁令检查+自动修复）→相似度校验→超过阈值提醒。

说明：skill_human_rewrite 适配自 human-writing（SKILL.md + references 写作规则 + check_prose.py 硬禁令），改写接口统一调用该 skill；旧的 skill_rewrite_note 保留但不再被流水线使用。

## 测试

```bash
pytest tests/ -x -q
```

## 运行说明

- 免费用户每日自动赠送点数（后端结算，先校验后扣减）
- 所有权限/点数扣减均在后端完成，前端只展示
- 上传截图只在当前浏览器会话临时展示，系统不会保存截图；历史记录仅保留文字结果
- 删除任务仅删除数据库任务记录；AI 配图为第三方临时链接，可能过期失效