#!/usr/bin/env python3
"""Finish translating remaining Chinese lines in docs (detached from kernel).
Index-line translation, batch=150, gap-retry only."""
import json, os, re, sys, threading, time, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path("/Users/ghb/sales-resource-allocation-framework")
conf = json.load(open(Path.home()/".claude"/"settings.json", encoding="utf-8")).get("env", {})
BASE = os.environ.get("ANTHROPIC_BASE_URL", conf["ANTHROPIC_BASE_URL"]).rstrip("/")
TOK = os.environ.get("ANTHROPIC_AUTH_TOKEN", conf["ANTHROPIC_AUTH_TOKEN"])

GLOSSARY = """Terminology: 世界模型=World Model; 分配智能=Allocation Intelligence; 知识库=Knowledge Base;
决策本体=Decision Ontology; 问题合同=Decision Problem Contract; 编排=Orchestration; 评测=Evaluation;
参考架构=Reference Architecture; 身份解析=Identity Resolution; 围栏=fence; 片区=sub-area;
经销商=dealer; 门店=store; 划转=transfer; 错位/OOF=out-of-fence supply; 缺口=gap; 证据链=evidence chain;
审批=approval; 快照=snapshot; 双时间线=bitemporal; 影响周期=impact horizon; 客情=customer relationship;
业代=field sales rep; 线路=beat route; 直供=direct supply; 二批=sub-distribution; 卖断=outright sell-in;
乡镇=township; 拜访=visit. 广州=Guangzhou 番禺=Panyu 增城=Zengcheng 从化=Conghua 大石=Dashi
海珠=Haizhu; 珠江后航道=Pearl River Back Channel; 美宜佳=Meiyijia; 有限公司=Co., Ltd.
Dealer names romanize (宏历=Hongli etc.)."""

SYS = ("You translate numbered Chinese lines from an SRAF spec into English. LANGUAGE-ONLY, zero "
       "semantic change. For EACH input line output exactly one line: <idx>: <translation>. "
       "Preserve: heading numbers after '#', list markers, table pipes | count, ** spans, "
       "backticked identifiers, §N / 0X §N refs, paths, URLs. Replace 、。（）：；， with , . ( ) : ; ,. "
       "No commentary, no extra lines. " + GLOSSARY)

def has_cjk(s): return bool(re.search(r'[\u4e00-\u9fff]', s))

def chat_gmi(prompt, tries=3):
    import ssl
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl._create_default_https_context
    cfg = json.load(open(Path.home() / ".sraf" / "vision.json", encoding="utf-8"))
    ep = cfg["endpoint"].rstrip("/")
    if not ep.endswith("/chat/completions"):
        ep = ep.replace("/v1", "") + "/v1/chat/completions"
    for a in range(tries):
        try:
            body = json.dumps({"model": cfg.get("model", "MiniMaxAI/MiniMax-M3"),
                               "max_tokens": 12000,
                               "messages": [{"role": "user", "content": SYS + "\n\n" + prompt}]}).encode()
            req = urllib.request.Request(ep, data=body, headers={
                "Authorization": "Bearer " + cfg["api_key"],
                "Content-Type": "application/json",
                "User-Agent": cfg.get("user_agent", "curl/8.6.0")})
            r = json.load(urllib.request.urlopen(req, timeout=300, context=ctx))
            return r["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  gmi retry{a}: {str(e)[:80]}", flush=True)
            time.sleep(6 * (a + 1))
    return ""


def chat(prompt, tries=3):
    if os.environ.get("T_CHANNEL") == "gmi":
        return chat_gmi(prompt, tries)
    for a in range(tries):
        try:
            req = urllib.request.Request(BASE + "/v1/messages",
                data=json.dumps({"model": "MiniMax-M3", "max_tokens": 12000,
                                 "reasoning_effort": "low",
                                 "messages": [{"role": "user", "content": SYS + "\n\n" + prompt}]}).encode(),
                headers={"Authorization": f"Bearer {TOK}", "anthropic-version": "2023-06-01",
                         "content-type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=300))
            return "".join(b.get("text", "") for b in r["content"] if b.get("type") == "text")
        except Exception as e:
            print(f"  api retry{a}: {str(e)[:80]}", flush=True)
            time.sleep(4 * (a + 1))
    return ""

def struct_ok(o, t):
    o, t = o.strip(), t.strip()
    if not t: return False
    om = re.match(r'^#{1,6}\s+\d{1,3}[A-Z]?[\.、]?\d*\.?', o)
    if om and not t.startswith(om.group(0)): return False
    if o.startswith('|') != t.startswith('|'): return False
    if re.match(r'^[-*]\s', o) and not re.match(r'^[-*]\s', t): return False
    if o.count('|') > 1 and t.count('|') != o.count('|'): return False
    return True

def batch(lines, idxs, rounds=3):
    got = {}
    cur = list(idxs)
    for rnd in range(rounds):
        if not cur: break
        num = dict(enumerate(cur, 1))
        inp = "\n".join(f"{n}: {lines[i]}" for n, i in num.items())
        out = chat(SYS + "\n\nTranslate each line:\n\n" + inp)
        for ln in out.splitlines():
            m = re.match(r'^\s*(\d+):\s*(.*)$|^\s*(\d+)\t(.*)$', ln.strip())
            if not m: continue
            n = int(m.group(1) or m.group(3)); txt = (m.group(2) or m.group(4) or "").strip()
            i = num.get(n)
            if i is None or not struct_ok(lines[i], txt) or has_cjk(txt): continue
            got[i] = txt
        cur = [i for i in cur if i not in got]
    return got

def anchors_of(t):
    return sorted(re.findall(r"^#{1,6}\s+\d{1,3}[A-Z]?[\.、]?[\d\.]*", t, re.M))

lock = threading.Lock()
def work(rel):
    p = ROOT / rel
    raw0 = p.read_text(encoding="utf-8")
    lines = raw0.splitlines(); a0 = anchors_of(raw0)
    idxs = [i for i, l in enumerate(lines) if has_cjk(l)]
    if not idxs: return rel, "clean"
    done = {}
    subs = [idxs[a:a+BATCH] for a in range(0, len(idxs), BATCH)]
    with ThreadPoolExecutor(max_workers=int(os.environ.get("T_INNER", "6"))) as bex:
        for r in bex.map(lambda seg: batch(lines, seg), subs):
            done.update(r)
    with lock: print(f"{rel} {len(done)}/{len(idxs)} translated", flush=True)
    for i, tr in done.items(): lines[i] = tr
    new = "\n".join(lines) + "\n"
    if anchors_of(new) != a0: return rel, "ANCHOR DRIFT"
    p.write_text(new, encoding="utf-8")
    left = sum(1 for l in lines if has_cjk(l))
    return rel, f"{len(idxs)}→{len(done)} left {left}"

DEFAULT_FILES = ["docs/01_WORLD_MODEL_SPEC.md", "docs/06_EVALUATION_AND_BENCHMARK.md",
         "docs/07_REFERENCE_ARCHITECTURE.md", "docs/08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md",
         "docs/05_DECISION_ORCHESTRATION.md", "docs/PROPOSAL_v1.3_LAYER_BINDINGS.md",
         "docs/CHANGELOG_v1.2.md", "docs/03_DECISION_PROBLEM_CONTRACTS.md",
         "DESIGN.md"]
if __name__ == "__main__":
    FILES = sys.argv[1:] or DEFAULT_FILES
    BATCH = int(os.environ.get("T_BATCH", "150"))
    ROUNDS = int(os.environ.get("T_ROUNDS", "3"))
    with ThreadPoolExecutor(max_workers=4) as ex:
        for fu in as_completed([ex.submit(work, f) for f in FILES]):
            print(fu.result(), flush=True)
    print("FINISHED", flush=True)
