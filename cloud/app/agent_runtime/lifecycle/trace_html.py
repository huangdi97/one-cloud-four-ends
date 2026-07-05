"""Trace HTML 渲染器 — 生成 Dashboard 和 Agent 状态页面。"""
# ruff: noqa: E501

from __future__ import annotations

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Trace Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f7fa;color:#333;padding:24px}
h1{font-size:24px;margin-bottom:20px;color:#1a1a2e}
.cards{display:flex;gap:16px;margin-bottom:24px}
.card{flex:1;background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.card .label{font-size:13px;color:#888;margin-bottom:6px}
.card .value{font-size:28px;font-weight:700;color:#1a1a2e}
.filters{margin-bottom:16px;display:flex;gap:12px;align-items:center}
.filters select{padding:8px 12px;border:1px solid #ddd;border-radius:6px;font-size:14px;background:#fff}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}
th{background:#f0f2f5;text-align:left;padding:12px 16px;font-size:13px;font-weight:600;color:#666}
td{padding:12px 16px;border-top:1px solid #eee;font-size:14px}
tr{cursor:pointer;transition:background .15s}
tr:hover{background:#f8f9ff}
.detail-row{display:none}
.detail-row.active{display:table-row}
.detail-cell{padding:16px 24px;background:#fafbff;border-top:2px solid #e8eaff}
.step{border-left:3px solid;padding:8px 12px;margin:6px 0;background:#fff;border-radius:4px;font-size:13px}
.step.success{border-color:#2ecc71} .step.error{border-color:#e74c3c} .step.warning{border-color:#f39c12}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600}
.badge.success{background:#d4edda;color:#155724} .badge.error{background:#f8d7da;color:#721c24}
.badge.warning{background:#fff3cd;color:#856404}
.loading{text-align:center;padding:60px;color:#999;font-size:16px}
</style>
</head>
<body>
<h1>Agent Trace Dashboard</h1>
<div class="cards" id="cards">
  <div class="card"><div class="label">Total Requests</div><div class="value" id="total-requests">-</div></div>
  <div class="card"><div class="label">Error Rate</div><div class="value" id="error-rate">-</div></div>
  <div class="card"><div class="label">Active Agents</div><div class="value" id="active-agents">-</div></div>
</div>
<div class="nav" style="margin-bottom:16px">
  <a href="/agent/traces/ui">Trace Dashboard</a>
  <a href="/agent/traces/ui/agents">Agent Status</a>
  <a href="/agent/chat/ui">Chat with Agent</a>
</div>
<div class="filters">
  <label>Agent:</label>
  <select id="agent-filter" onchange="loadTraces()">
    <option value="">All Agents</option>
  </select>
</div>
<div id="table-container"><div class="loading">Loading...</div></div>
<script>
async function loadSummary(){try{const r=await fetch('/agent/metrics/summary');const d=await r.json();const data=d.data||{};document.getElementById('total-requests').textContent=data.total_requests??(data.total_runs??'-');document.getElementById('error-rate').textContent=data.error_rate!=null?(data.error_rate+'%'):(data.success_rate!=null?((100-data.success_rate)+'%'):'-');document.getElementById('active-agents').textContent=data.active_agents??'-'}catch(e){document.getElementById('total-requests').textContent='ERR'}}
async function loadAgentFilter(){try{const r=await fetch('/agent/traces/ui/agents');const text=await r.text();const sel=document.getElementById('agent-filter');const parser=new DOMParser();const doc=parser.parseFromString(text,'text/html');const rows=doc.querySelectorAll('table tbody tr');rows.forEach(row=>{const cells=row.querySelectorAll('td');if(cells.length>0){const name=cells[0].textContent.trim();if(name){const opt=document.createElement('option');opt.value=name;opt.textContent=name;sel.appendChild(opt)}}})}catch(e){console.error('Failed to load agents',e)}}
async function loadTraces(){try{const agent=document.getElementById('agent-filter').value;let url='/agent/traces?page_size=20';if(agent)url+='&agent_name='+encodeURIComponent(agent);const r=await fetch(url);const d=await r.json();const traces=d.data?.items||d.data||[];let html='<table><thead><tr><th>Agent</th><th>Status</th><th>Duration</th><th>Time</th></tr></thead><tbody>';traces.forEach((t,i)=>{const sc=t.status==='success'?'success':t.status==='error'?'error':'warning';html+='<tr onclick="toggleDetail('+i+')"><td>'+(t.agent_name||t.agent||'-')+'</td><td><span class="badge '+sc+'\">'+(t.status||'unknown')+'</span></td><td>'+(t.duration_ms||t.total_duration_ms?((t.duration_ms||t.total_duration_ms)+'ms'):'-')+'</td><td>'+(t.created_at||t.started_at||t.timestamp||'-')+'</td></tr>';html+='<tr class="detail-row" id="detail-'+i+'"><td colspan="4"><div class="detail-cell" id="detail-content-'+i+'">Loading...</div></td></tr>'});html+='</tbody></table>';document.getElementById('table-container').innerHTML=html}catch(e){document.getElementById('table-container').innerHTML='Error: '+e.message}}
async function toggleDetail(i){const row=document.getElementById('detail-'+i);const active=row.classList.contains('active');document.querySelectorAll('.detail-row.active').forEach(r=>r.classList.remove('active'));if(active)return;row.classList.add('active');const el=document.getElementById('detail-content-'+i);if(el.dataset.loaded)return;el.dataset.loaded='true';try{const agent=document.getElementById('agent-filter').value;let url='/agent/traces?page_size=20';if(agent)url+='&agent_name='+encodeURIComponent(agent);const t=await(await fetch(url)).json();const items=t.data?.items||t.data||[];const item=items[i];if(!item){el.innerHTML='No data';return}const tr=await(await fetch('/agent/traces/'+(item.trace_id||item.id))).json();const trace=tr.data||tr;let s='';(trace.steps||trace.execution_steps||[]).forEach(st=>{s+='<div class="step '+(st.status==='success'?'success':'error')+'">'+ (st.tool||st.action||st.name||'step')+'</div>'});el.innerHTML=s||'No step details'}catch(e){el.innerHTML='Error loading'}}
loadSummary();loadAgentFilter();loadTraces();
</script>
</body>
</html>"""

AGENTS_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Status Overview</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f7fa;color:#333;padding:24px}}
h1{{font-size:24px;margin-bottom:20px;color:#1a1a2e}}
.nav{{margin-bottom:16px;display:flex;gap:12px}}
.nav a{{color:#4a6cf7;text-decoration:none;font-size:14px;padding:6px 12px;border-radius:6px;background:#fff;border:1px solid #e0e0e0}}
.nav a:hover{{background:#f0f2ff}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
th{{background:#f0f2f5;text-align:left;padding:12px 16px;font-size:13px;font-weight:600;color:#666}}
td{{padding:12px 16px;border-top:1px solid #eee;font-size:14px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600}}
.badge.success{{background:#d4edda;color:#155724}} .badge.error{{background:#f8d7da;color:#721c24}}
.badge.warning{{background:#fff3cd;color:#856404}}
</style>
</head>
<body>
<h1>Agent Status Overview</h1>
<div class="nav">
  <a href="/agent/traces/ui">Trace Dashboard</a>
  <a href="/agent/traces/ui/agents">Agent Status</a>
  <a href="/agent/chat/ui">Chat with Agent</a>
</div>
<table>
<thead><tr><th>Name</th><th>Role</th><th>Status</th><th>Last Active</th><th>Last Result</th><th>Success Rate</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
</body>
</html>"""


class TraceHTMLRenderer:
    @staticmethod
    def render_dashboard() -> str:
        """Return the HTML for the agent trace dashboard page."""
        return DASHBOARD_HTML

    @staticmethod
    def render_agents_page(rows_html: str) -> str:
        """Return the HTML for the agent status overview page with the given rows."""
        return AGENTS_PAGE_HTML.format(rows_html=rows_html)
