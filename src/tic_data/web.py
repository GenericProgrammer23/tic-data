from __future__ import annotations

HTML_PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>TIC data</title>
  <style>
    :root { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #18212f; background:#f5f7fa; }
    * { box-sizing: border-box; }
    body { margin:0; }
    main { max-width:1180px; margin:0 auto; padding:32px 20px 64px; }
    h1 { margin:0 0 6px; font-size:32px; }
    h2 { margin:0 0 14px; font-size:20px; }
    p { line-height:1.5; }
    .muted { color:#64748b; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; }
    .card { background:white; border:1px solid #dbe2ea; border-radius:12px; padding:18px; margin-top:18px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
    label { display:block; font-size:13px; font-weight:650; margin:12px 0 5px; }
    input, select, textarea, button { width:100%; font:inherit; }
    input, select, textarea { border:1px solid #cbd5e1; border-radius:8px; padding:10px 11px; background:white; }
    textarea { min-height:80px; resize:vertical; }
    button { border:0; border-radius:8px; padding:11px 14px; background:#0f172a; color:white; font-weight:650; cursor:pointer; }
    button.secondary { background:#e2e8f0; color:#0f172a; }
    button:disabled { opacity:.5; cursor:not-allowed; }
    .row { display:flex; gap:10px; align-items:end; }
    .row > * { flex:1; }
    .status { margin-top:12px; padding:10px 12px; border-radius:8px; background:#f1f5f9; white-space:pre-wrap; font-size:13px; }
    .error { background:#fee2e2; color:#991b1b; }
    .success { background:#dcfce7; color:#166534; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { text-align:left; border-bottom:1px solid #e2e8f0; padding:9px 8px; vertical-align:top; }
    th { position:sticky; top:0; background:white; }
    .table-wrap { max-height:520px; overflow:auto; border:1px solid #e2e8f0; border-radius:8px; margin-top:12px; }
    .pill { display:inline-block; padding:2px 7px; border-radius:999px; background:#e2e8f0; margin:1px 3px 1px 0; font-size:11px; }
    .hidden { display:none; }
    code { background:#f1f5f9; padding:1px 4px; border-radius:4px; }
  </style>
</head>
<body>
<main>
  <h1>TIC data</h1>
  <p class="muted">Map Transparency in Coverage indexes to rate files, then find negotiated rates for a provider organization.</p>

  <section class="card">
    <h2>1. Load a payer index</h2>
    <div class="grid">
      <div>
        <label>Upload Table-of-Contents / index JSON</label>
        <input id="indexFile" type="file" accept=".json,.gz,.zip,application/json" />
        <button id="loadUpload" style="margin-top:10px">Load uploaded index</button>
      </div>
      <div>
        <label>Or paste an index URL</label>
        <input id="indexUrl" placeholder="https://payer.example/index.json" />
        <button id="loadUrl" style="margin-top:10px">Load index URL</button>
      </div>
    </div>
    <div id="indexStatus" class="status">No index loaded.</div>
  </section>

  <section id="networkCard" class="card hidden">
    <h2>2. Choose the rate file / network</h2>
    <div class="grid">
      <div>
        <label>Plan type filter</label>
        <input id="planFilter" placeholder="e.g. OAP, Local Plus, HMO" />
      </div>
      <div>
        <label>Network/file search</label>
        <input id="networkFilter" placeholder="e.g. National OAP, Arizona" />
      </div>
    </div>
    <label>Network</label>
    <select id="networkSelect"></select>
    <div id="networkDetail" class="status"></div>
  </section>

  <section class="card">
    <h2>3. Provider organization and codes</h2>
    <div class="grid">
      <div>
        <label>TIN / EIN</label>
        <input id="tin" placeholder="XX-XXXXXXX" />
      </div>
      <div>
        <label>Type 2 or Type 1 NPI</label>
        <input id="npi" placeholder="1234567890" />
      </div>
      <div>
        <label>Business name (optional)</label>
        <input id="businessName" placeholder="Provider organization name" />
      </div>
    </div>
    <div class="grid">
      <div>
        <label>Billing codes</label>
        <textarea id="codes" placeholder="97110\n97112\n97140\n97530"></textarea>
      </div>
      <div>
        <label>Billing code type</label>
        <input id="codeType" value="CPT" />
        <label>Billing class</label>
        <select id="billingClass"><option value="professional" selected>professional</option><option value="">any</option><option value="institutional">institutional</option><option value="both">both</option></select>
      </div>
    </div>
    <button id="findRates" style="margin-top:12px">Find negotiated rates</button>
    <div id="rateStatus" class="status">Load an index and choose a network, or use the direct-file section below.</div>
  </section>

  <section class="card">
    <h2>Direct rate-file upload</h2>
    <p class="muted">If you already have the actual in-network file, upload <code>.json</code>, <code>.json.gz</code>, or <code>.zip</code> here and use the provider/code fields above.</p>
    <input id="rateFile" type="file" accept=".json,.gz,.zip" />
    <button id="findUploadedRates" style="margin-top:10px">Search uploaded rate file</button>
  </section>

  <section id="resultsCard" class="card hidden">
    <div class="row"><h2>Results</h2><button id="downloadCsv" class="secondary" style="max-width:180px">Download CSV</button></div>
    <div id="resultSummary" class="status"></div>
    <div class="table-wrap"><table><thead><tr><th>Code</th><th>Rate</th><th>Type</th><th>Billing class</th><th>POS</th><th>Expiration</th><th>Description</th></tr></thead><tbody id="resultsBody"></tbody></table></div>
  </section>
</main>
<script>
let catalog = [];
let lastRates = [];
const $ = id => document.getElementById(id);
const splitValues = value => value.split(/[\n,;\s]+/).map(v => v.trim()).filter(Boolean);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function setStatus(id, text, kind='') { const e=$(id); e.textContent=text; e.className='status '+kind; }
function providerPayload() {
  const tins=splitValues($('tin').value), npis=splitValues($('npi').value), names=$('businessName').value.trim() ? [$('businessName').value.trim()] : [];
  if (!tins.length && !npis.length && !names.length) throw new Error('Enter at least one TIN, NPI, or business name.');
  return {tins, npis, business_names:names};
}
function filtersPayload() {
  return {billing_codes:splitValues($('codes').value), billing_code_types:splitValues($('codeType').value), service_codes:[], billing_classes:$('billingClass').value ? [$('billingClass').value] : [], negotiated_types:[], limit:5000};
}
async function parseResponse(response) { const data=await response.json(); if(!response.ok) throw new Error(data.detail || JSON.stringify(data)); return data; }
function renderCatalog() {
  const plan=$('planFilter').value.trim().toLowerCase(), search=$('networkFilter').value.trim().toLowerCase();
  const rows=catalog.filter(r => (!plan || r.plan_names.some(x=>x.toLowerCase().includes(plan))) && (!search || (r.network+' '+r.description+' '+r.source).toLowerCase().includes(search)));
  $('networkSelect').innerHTML=rows.map(r=>`<option value="${esc(r.location)}">${esc(r.network)} — ${esc(r.source)} — ${esc(r.file_format)} (${r.plan_sponsor_count} sponsors)</option>`).join('');
  $('networkCard').classList.remove('hidden'); updateNetworkDetail();
}
function selectedNetwork() { return catalog.find(r=>r.location === $('networkSelect').value); }
function updateNetworkDetail() { const r=selectedNetwork(); if(!r){ $('networkDetail').textContent='No matching networks.'; return; } $('networkDetail').textContent=`${r.description}\nPlan types: ${r.plan_names.join(', ') || 'n/a'}\nReferenced by ${r.plan_sponsor_count} plan sponsors. Format: ${r.file_format}.`; }
async function loadCatalogFromUpload() {
  const file=$('indexFile').files[0]; if(!file) return setStatus('indexStatus','Choose an index file first.','error');
  setStatus('indexStatus','Reading and normalizing index…'); const form=new FormData(); form.append('file',file);
  try { const data=await parseResponse(await fetch('/catalog/upload',{method:'POST',body:form})); catalog=data.files; setStatus('indexStatus',`${data.metadata.reporting_entity_name || 'Payer'} — ${data.file_count} unique in-network files.`, 'success'); renderCatalog(); }
  catch(e){ setStatus('indexStatus',e.message,'error'); }
}
async function loadCatalogFromUrl() {
  const url=$('indexUrl').value.trim(); if(!url) return setStatus('indexStatus','Paste an index URL first.','error');
  setStatus('indexStatus','Downloading and normalizing index…');
  try { const data=await parseResponse(await fetch('/catalog/url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})})); catalog=data.files; setStatus('indexStatus',`${data.metadata.reporting_entity_name || 'Payer'} — ${data.file_count} unique in-network files.`, 'success'); renderCatalog(); }
  catch(e){ setStatus('indexStatus',e.message,'error'); }
}
async function findRatesFromUrl() {
  const network=selectedNetwork(); if(!network) return setStatus('rateStatus','Load an index and choose a network first.','error');
  try { const body={url:network.location,organization:providerPayload(),filters:filtersPayload()}; setStatus('rateStatus',`Downloading/searching ${network.network}. Large national files can take substantial time and disk space…`); const data=await parseResponse(await fetch('/extract/url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})); renderRates(data,network.network); }
  catch(e){ setStatus('rateStatus',e.message,'error'); }
}
async function findRatesFromUpload() {
  const file=$('rateFile').files[0]; if(!file) return setStatus('rateStatus','Choose a rate file first.','error');
  try { const form=new FormData(); form.append('file',file); form.append('organization_json',JSON.stringify(providerPayload())); form.append('filters_json',JSON.stringify(filtersPayload())); setStatus('rateStatus','Searching uploaded rate file…'); const data=await parseResponse(await fetch('/extract/upload',{method:'POST',body:form})); renderRates(data,file.name); }
  catch(e){ setStatus('rateStatus',e.message,'error'); }
}
function renderRates(data,label) {
  lastRates=data.rates || []; $('resultsCard').classList.remove('hidden'); $('resultsBody').innerHTML=lastRates.map(r=>`<tr><td>${esc(r.billing_code)}</td><td>${esc(r.negotiated_rate)}</td><td>${esc(r.negotiated_type)}</td><td>${esc(r.billing_class)}</td><td>${esc((r.service_code||[]).join(', '))}</td><td>${esc(r.expiration_date)}</td><td>${esc(r.description || r.name)}</td></tr>`).join('');
  const summary=`${label}: ${data.rate_count} rate rows; ${data.matched_providers.length} matching provider records${data.truncated ? '; results truncated at limit' : ''}.`; setStatus('rateStatus',summary,'success'); setStatus('resultSummary',summary); $('resultsCard').scrollIntoView({behavior:'smooth'});
}
function downloadCsv() { if(!lastRates.length) return; const cols=['billing_code_type','billing_code','negotiated_rate','negotiated_type','billing_class','service_code','expiration_date','description','name']; const quote=v=>'"'+String(Array.isArray(v)?v.join('|'):(v??'')).replaceAll('"','""')+'"'; const csv=[cols.join(','),...lastRates.map(r=>cols.map(c=>quote(r[c])).join(','))].join('\r\n'); const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'})); a.download='tic-rates.csv'; a.click(); URL.revokeObjectURL(a.href); }
$('loadUpload').onclick=loadCatalogFromUpload; $('loadUrl').onclick=loadCatalogFromUrl; $('planFilter').oninput=renderCatalog; $('networkFilter').oninput=renderCatalog; $('networkSelect').onchange=updateNetworkDetail; $('findRates').onclick=findRatesFromUrl; $('findUploadedRates').onclick=findRatesFromUpload; $('downloadCsv').onclick=downloadCsv;
</script>
</body>
</html>'''
