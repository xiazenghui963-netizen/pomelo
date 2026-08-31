import os

ROOT = r"E:\pomelo-ai"
targets = [
    "_final_smoke.py", "_vec_final.py", "_vec_smoke.py", "_vec_smoke2.py",
    "_run_tests.py", "launcher.py", "stop_server.py", "_tmp_js.js",
    "_materials_check.py", "_vec_check.py",
]
removed = []
for name in targets:
    p = os.path.join(ROOT, name)
    if os.path.exists(p):
        os.remove(p)
        removed.append(name)
print("removed:", ", ".join(removed) if removed else "(none)")
print("remaining _*.py in root:", [f for f in os.listdir(ROOT) if f.startswith("_") and f.endswith(".py")])
print("listener8000:", "no" if not any(
    True for l in os.popen("netstat -ano").readlines()
    if "TCP" in l and ":8000" in l and "LISTENING" in l
) else "yes")