
    function esc(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }

    const MAX_CHARS = 2000;
    const contentArea = document.getElementById("mContentArea");
    const contentCounter = document.getElementById("contentCounter");
    const submitText = document.getElementById("submitText");

    function refreshCounter() {
      const len = contentArea.value.length;
      contentCounter.textContent = `${len} / ${MAX_CHARS}`;
      contentCounter.className = len >= MAX_CHARS
        ? "text-xs text-red-500 text-right"
        : "text-xs text-gray-400 text-right";
      // 到达上限：禁用保存按钮
      if (len >= MAX_CHARS) {
        submitText.disabled = true;
        submitText.classList.add("opacity-50", "cursor-not-allowed");
      } else {
        submitText.disabled = false;
        submitText.classList.remove("opacity-50", "cursor-not-allowed");
      }
    }

    contentArea.addEventListener("input", () => {
      refreshCounter();
      if (contentArea.value.length >= MAX_CHARS) {
        toast("单条资料最大2000字符，请删减内容", "err");
      }
    });

    async function load() {
      const rows = await Api.get("/materials");
      const box = document.getElementById("list");
      box.innerHTML = "";
      rows.forEach((r) => {
        const card = document.createElement("div");
        card.className = "bg-white rounded-2xl p-5 shadow-sm";
        card.innerHTML = `
          <div class="flex items-center justify-between mb-2">
            <div>
              <h3 class="font-medium text-gray-800">${esc(r.title)}</h3>
              <span class="text-xs text-gray-400">id:${r.id} · ${String(r.created_at).slice(0,10)}</span>
            </div>
            <div class="flex gap-2">
              <button class="editBtn px-3 py-1 rounded-lg text-xs bg-gray-100 hover:bg-gray-200">编辑</button>
              <button class="delBtn px-3 py-1 rounded-lg text-xs bg-red-50 text-red-500 hover:bg-red-100">删除</button>
            </div>
          </div>
          <p class="text-sm text-gray-600 whitespace-pre-wrap">${esc(r.content)}</p>`;
        card.querySelector(".editBtn").onclick = () => { editing = r.id; document.getElementById("mTitle").value = r.title; document.getElementById("mContentArea").value = r.content; document.getElementById("submitText").textContent = "更新资料"; };
        card.querySelector(".delBtn").onclick = async () => { if (!confirm("确认删除该资料？")) return; await Api.del(`/materials/${r.id}`); toast("已删除"); load(); };
        box.appendChild(card);
      });
    }
    let editing = null;
    document.getElementById("createForm").onsubmit = async (e) => {
      e.preventDefault();
      const title = document.getElementById("mTitle").value.trim();
      const content = document.getElementById("mContentArea").value.trim();
      try {
        if (editing) { await Api.put(`/materials/${editing}`, { title, content }); toast("已更新"); editing = null; }
        else { await Api.post("/materials", { title, content }); toast("已保存"); }
        document.getElementById("submitText").textContent = "保存资料";
        document.getElementById("createForm").reset();
        load();
      } catch (err) { toast(err.message, "err"); }
    };
    if (!Api.requireAuth()) {}
    load();
  