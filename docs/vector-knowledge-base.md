# 青柚 AI 私有向量知识库 + AI 生成链路改造方案

> 通用多租户方案，不写死任何业务人设。向量库只做信息检索，内容不允许直接作为 prompt，必须后端分类组装后注入。

---

## 一、向量切片元数据 JSON Schema

每个存入向量库的 chunk 切片必须携带 meta（类型判定**只依据 meta，绝不扫描文本**）：

```json
{
  "doc_type": "hard_instruction | reference_context",
  "doc_id": "源文档id",
  "user_id": "租户用户id",
  "source_name": "原始上传文档名称"
}
```

数据表：

| 表 | 字段 | 说明 |
|---|---|---|
| user_material | id / user_id / title / content / doc_type / source_name / is_enabled / is_deleted / created_at / updated_at | 源文档（多租户私有） |
| document_chunk | id / user_id / doc_id / chunk_index / content / meta_json | 向量切片，meta_json 即上表 JSON |

类型常量（前后端共用）：

```python
DOC_TYPE_HARD = "hard_instruction"      # AI强制生成约束（最高优先级）
DOC_TYPE_REFERENCE = "reference_context" # 事实参考素材（默认）
DEFAULT_DOC_TYPE = DOC_TYPE_REFERENCE    # 未标记时默认
```

---

## 二、后端接口层校验逻辑（伪代码）

```python
def validate_enabled_docs(db, user_id, enabled_doc_ids) -> None:
    """任务创建接口前置校验：不调用大模型。"""
    if not enabled_doc_ids:
        return                      # 未勾选 → 完全跳过向量模块
    if len(enabled_doc_ids) > 3:
        reject("最多选择 3 条私有资料", 40020)
    rows = select docs where user_id=? and id in enabled_doc_ids and not is_deleted
    if not all id present: reject("部分私有资料不存在或无权访问", 40021)
    # 只统计启用文档中 doc_type=hard_instruction 的数量
    hard_count = count rows where doc_type == DOC_TYPE_HARD
    if hard_count > 1:
        reject("⚠️同时启用了多份AI执行约束，规则会冲突，请只勾选一份", 40060, 400)
```

执行层（jobs）伪代码：

```python
def build_vector_context(db, task, inputs) -> str:
    if not inputs.use_vector or not inputs.enabled_doc_ids:
        return ""                      # 未启用 → 完全跳过向量模块
    retrieved = retrieve(db, task.user_id, inputs.enabled_doc_ids, query=inputs.text)
    if not retrieved:
        return ""
    return assemble_vector_block(retrieved)   # 固定: 总规则→hard区→reference区→【本次业务任务】
```

检索函数要点：

```python
def retrieve(db, user_id, enabled_doc_ids, query, top_n=5):
    # 双租户隔离：只查 user_id 本人空间
    # 只对【用户勾选启用】的文档（doc_id in enabled_doc_ids 且 is_enabled=True）召回
    # 返回切片 + 其 meta；切片的 doc_type 来自 meta，不来自文本
```

---

## 三、完整 Prompt 组装示例

组装顺序固定，**业务任务永远在向量召回内容之后**。最终送入大模型的结构：

```
【第一段｜代码写死的全局固定系统规则】
【私有向量资料处理总规则】
下面内容来自用户私有向量库检索结果，分为两类，严格区分用途：
1.【hard_instruction｜强制生成指令】...
2.【reference_context｜事实参考信息】...
执行逻辑：①先读懂hard_instruction强制规则；②读懂reference_context事实背景；③执行后续业务任务。
优先级：hard_instruction > 业务任务 > reference_context
若无向量召回内容，直接执行业务任务。

【第二段｜向量召回-hard_instruction 强制指令区】（有则输出）
[hard_instruction｜我的账号-人设规则]
你是「青柚」品牌官方编辑，语气亲切专业，输出为小红书短笔记，禁止使用清单体/编号体，禁词：绝对、100%、最。

【第三段｜向量召回-reference_context 事实参考区】（有则输出）
[reference_context｜品牌企业介绍]
青柚AI 面向个人创作者，提供截图解析、笔记生成、私有资料库能力…
[reference_context｜文案风格案例]
某爆款标题：…；正文以真实经历开头，结尾引导互动…

【第四段｜本次业务任务】（本次业务 prompt，组装在最后）
请基于以上上下文，完成：解析截图并拆解爆款结构…生成 8 个小标题…生成小红书笔记正文…
```

> 注：hard_instruction 区最多只有 1 份；reference_context 区可多条。若两区都空（未启用资料/无召回），则第一段总规则也不用输出，直接执行业务任务。

---

## 四、前端 UI 提示文案

### 私有资料管理页（materials.html）
- 类型选择下拉（默认）：
  - `通用参考素材` = reference_context（人物/企业/产品/案例等事实背景，仅供参考）
  - `AI强制生成约束` = hard_instruction（人设、输出格式、禁词、语气，请只启用一份）
- 提示文案：`生成任务中最多引用 3 条资料；AI强制约束文档最多启用 1 份，多份会冲突被拦截；未标记类型默认为通用参考素材。`
- 字数提示：`单条资料最大 2000 字符`（输入框实时显示 n/2000，到达上限禁用保存）

### 灵感工作台（index.html 勾选提示）
```
启用私有向量资料参与本次生成（最多勾选 3 条）
⚠️ AI强制约束（人设/格式/禁词）文档最多启用 1 份，多份会冲突被拦截；通用参考素材数量不限。
```

---

## 五、边界 case 说明

| 场景 | 行为 |
|---|---|
| 用户未勾选任何私有资料 | `use_vector=false` → jobs 完全跳过向量模块，直接执行业务任务 |
| 上传文档未标记类型 | 后端默认 `reference_context` |
| 只上传企业资料（全部 reference） | 全部作为事实参考进入 reference 区，数量不限，不当作指令 |
| 勾选多份 hard_instruction | 任务创建接口直接拦截，返回 `⚠️同时启用了多份AI执行约束，规则会冲突，请只勾选一份`，不调用大模型、不扣点 |
| reference 片段里出现"请以小红书口吻…"等指令式文本 | 仍按 meta=reference_context 处理，只作背景信息，**严禁当作 prompt 指令执行** |
| token 超限 | 优先截断 reference_context 片段（hard 区尽量完整保留；截断顺序：先删靠后/低分切片，再对保留片段截尾） |
| 切片 doc_type 未知/缺失 | 一律按 reference_context 兜底，绝不按文本内容猜 |
| 多租户 | retrieve/校验全部带 `user_id` 过滤，不同用户向量空间互不可见 |
| hard_instruction 本身内容 | 属于该文档的 meta，切片后仍带 `hard_instruction`；即使文本与 reference 相似，也按 hard 处理 |