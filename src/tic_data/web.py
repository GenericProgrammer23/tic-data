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
    .warning { background:#fef3c7; color:#92400e; }
    .field-hint { color:#64748b; font-size:12px; margin-top:5px; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { text-align:left; border-bottom:1px solid #e2e8f0; padding:9px 8px; vertical-align:top; }
    th { position:sticky; top:0; background:white; }
    .table-wrap { max-height:520px; overflow:auto; border:1px solid #e2e8f0; border-radius:8px; margin-top:12px; }
    .pill { display:inline-block; padding:2px 7px; border-radius:999px; background:#e2e8f0; margin:1px 3px 1px 0; font-size:11px; }
    .chip-wrap { display:flex; flex-wrap:wrap; gap:7px; margin-top:8px; min-height:28px; }
    .code-chip { display:inline-flex; align-items:center; gap:6px; background:#e2e8f0; color:#0f172a; border-radius:7px; padding:5px 7px 5px 9px; font-size:13px; font-weight:650; }
    .code-chip button { width:auto; padding:0 3px; background:transparent; color:#64748b; font-size:16px; line-height:1; }
    details.diagnostics { margin-top:12px; border:1px solid #dbe2ea; border-radius:8px; padding:10px 12px; background:#fff; }
    details.diagnostics summary { cursor:pointer; font-weight:650; font-size:13px; }
    .diagnostic-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:8px; margin-top:10px; }
    .diagnostic-item { padding:8px 10px; background:#f8fafc; border-radius:7px; font-size:12px; }
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
        <input id="tin" placeholder="12-3456789 or 123456789" inputmode="numeric" />
        <div id="tinHint" class="field-hint">Both XX-XXXXXXX and XXXXXXXXX formats are accepted.</div>
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
        <input id="codeInput" placeholder="Type 97110, then comma" autocomplete="off" />
        <div class="field-hint">Type a code followed by a comma or Enter. Each recorded code appears below.</div>
        <div id="codeChips" class="chip-wrap"></div>
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
    <details id="diagnosticsPanel" class="diagnostics hidden">
      <summary>Troubleshooting details</summary>
      <div id="diagnosticMessage" class="status"></div>
      <div id="diagnosticGrid" class="diagnostic-grid"></div>
    </details>
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
let billingCodes = [];
const $ = id => document.getElementById(id);
const splitValues = value => value.split(/[\n,;\s]+/).map(v => v.trim()).filter(Boolean);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalizeIdentifier = value => String(value || '').replace(/[^0-9A-Za-z]/g,'').toLowerCase();
function setStatus(id, text, kind='') { const e=$(id); e.textContent=text; e.className='status '+kind; }

function updateTinHint() {
  const raw=$('tin').value.trim(), normalized=normalizeIdentifier(raw);
  if(!raw) { $('tinHint').textContent='Both XX-XXXXXXX and XXXXXXXXX formats are accepted.'; return; }
  if(/^\d{9}$/.test(normalized)) $('tinHint').textContent=`Will search as ${normalized}. Dashes/spaces are ignored.`;
  else $('tinHint').textContent=`Will search as ${normalized || '(empty)'}. A standard EIN/TIN is normally 9 digits.`;
}

function addBillingCodes(raw) {
  const values=String(raw || '').split(/[\n,;\s]+/).map(v=>v.trim().toUpperCase()).filter(Boolean);
  for(const value of values) if(!billingCodes.includes(value)) billingCodes.push(value);
  renderBillingCodes();
}
function renderBillingCodes() {
  $('codeChips').innerHTML=billingCodes.map((code,index)=>`<span class="code-chip">${esc(code)}<button type="button" data-index="${index}" title="Remove ${esc(code)}">×</button></span>`).join('');
  $('codeChips').querySelectorAll('button').forEach(button=>button.onclick=()=>{ billingCodes.splice(Number(button.dataset.index),1); renderBillingCodes(); });
}
function commitCodeInput() {
  const input=$('codeInput');
  if(input.value.trim()) addBillingCodes(input.value);
  input.value='';
}

function providerPayload() {
  const tins=splitValues($('tin').value), npis=splitValues($('npi').value), names=$('businessName').value.trim() ? [$('businessName').value.trim()] : [];
  if (!tins.length && !npis.length && !names.length) throw new Error('Enter at least one TIN, NPI, or business name.');
  return {tins, npis, business_names:names};
}
function filtersPayload() {
  commitCodeInput();
  return {billing_codes:[...billingCodes], billing_code_types:splitValues($('codeType').value), service_codes:[], billing_classes:$('billingClass').value ? [$('billingClass').value] : [], negotiated_types:[], limit:5000};
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

function troubleshootingMessage(data) {
  const d=data.diagnostics || {}, requested=((d.requested_filters||{}).billing_codes||[]), seen=d.requested_billing_codes_seen||[];
  if(data.rate_count) return 'Rates were found. These counters are available if you need to validate how the match was made.';
  if(requested.length && !seen.length) return `None of the requested billing codes (${requested.join(', ')}) were found in this rate file. This usually means the wrong network/file was selected, or the file uses a different billing-code type.`;
  if((d.provider_groups_matched||0)===0 && (d.embedded_provider_groups_matched||0)===0) return `The requested code(s) exist, but no provider group matched the TIN/NPI/business name. Confirm the identifier and try the organization's Type 2 NPI or business name. If those also fail, this provider may not be represented in the selected network file.`;
  if((d.service_items_matched_filters||0)===0) return `The code exists, but the service filters excluded it. Code type(s) seen for the requested code: ${(d.billing_code_types_seen_for_requested_codes||[]).join(', ') || 'unknown'}. Try clearing or changing Billing code type.`;
  if((d.negotiated_rate_groups_linked_to_provider||0)===0) return 'The provider and requested service were both found, but this file did not link that provider group to a negotiated-rate record for the requested service. This often points to the wrong network variant.';
  if((d.negotiated_prices_matched_filters||0)===0) return `A negotiated-rate record was linked to the provider, but the price filters removed it. Billing class(es) actually present: ${(d.billing_classes_seen_for_linked_rates||[]).join(', ') || 'unknown'}. Try setting Billing class to “any”.`;
  return 'The file was scanned but returned no final rate rows. Expand the counters below and compare the normalized identifiers and filters.';
}
function renderDiagnostics(data) {
  const d=data.diagnostics || {};
  $('diagnosticsPanel').classList.remove('hidden');
  const message=troubleshootingMessage(data);
  setStatus('diagnosticMessage',message,data.rate_count ? 'success' : 'warning');
  const normalized=d.normalized_organization || {}, requested=d.requested_filters || {};
  const items=[
    ['Normalized TIN(s)',(normalized.tins||[]).join(', ') || 'none'],
    ['Normalized NPI(s)',(normalized.npis||[]).join(', ') || 'none'],
    ['Requested codes',(requested.billing_codes||[]).join(', ') || 'all'],
    ['Requested codes seen',(d.requested_billing_codes_seen||[]).join(', ') || 'none'],
    ['Code types seen',(d.billing_code_types_seen_for_requested_codes||[]).join(', ') || 'none'],
    ['Provider groups scanned',d.provider_groups_scanned ?? 0],
    ['Provider groups matched',d.provider_groups_matched ?? 0],
    ['Provider group IDs matched',d.matched_provider_group_id_count ?? 0],
    ['Service rows scanned',d.in_network_items_scanned ?? 0],
    ['Service rows after filters',d.service_items_matched_filters ?? 0],
    ['Rate groups linked to provider',d.negotiated_rate_groups_linked_to_provider ?? 0],
    ['Price rows after filters',d.negotiated_prices_matched_filters ?? 0],
    ['Billing classes present',(d.billing_classes_seen_for_linked_rates||[]).join(', ') || 'none'],
  ];
  $('diagnosticGrid').innerHTML=items.map(([label,value])=>`<div class="diagnostic-item"><strong>${esc(label)}</strong><br>${esc(value)}</div>`).join('');
  if(!data.rate_count) $('diagnosticsPanel').open=true;
}
function renderRates(data,label) {
  lastRates=data.rates || []; $('resultsCard').classList.remove('hidden'); $('resultsBody').innerHTML=lastRates.map(r=>`<tr><td>${esc(r.billing_code)}</td><td>${esc(r.negotiated_rate)}</td><td>${esc(r.negotiated_type)}</td><td>${esc(r.billing_class)}</td><td>${esc((r.service_code||[]).join(', '))}</td><td>${esc(r.expiration_date)}</td><td>${esc(r.description || r.name)}</td></tr>`).join('');
  const summary=`${label}: ${data.rate_count} rate rows; ${data.matched_providers.length} matching provider records${data.truncated ? '; results truncated at limit' : ''}.`; setStatus('rateStatus',summary,data.rate_count ? 'success' : 'warning'); setStatus('resultSummary',summary); renderDiagnostics(data); $('resultsCard').scrollIntoView({behavior:'smooth'});
}
function downloadCsv() { if(!lastRates.length) return; const cols=['billing_code_type','billing_code','negotiated_rate','negotiated_type','billing_class','service_code','expiration_date','description','name']; const quote=v=>'"'+String(Array.isArray(v)?v.join('|'):(v??'')).replaceAll('"','""')+'"'; const csv=[cols.join(','),...lastRates.map(r=>cols.map(c=>quote(r[c])).join(','))].join('\r\n'); const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'})); a.download='tic-rates.csv'; a.click(); URL.revokeObjectURL(a.href); }

$('tin').oninput=updateTinHint;
$('codeInput').addEventListener('keydown',event=>{ if(event.key===',' || event.key==='Enter'){ event.preventDefault(); commitCodeInput(); } });
$('codeInput').addEventListener('input',event=>{ if(event.target.value.includes(',')){ const parts=event.target.value.split(','); addBillingCodes(parts.slice(0,-1).join(',')); event.target.value=parts.at(-1); } });
$('codeInput').addEventListener('blur',commitCodeInput);
$('loadUpload').onclick=loadCatalogFromUpload; $('loadUrl').onclick=loadCatalogFromUrl; $('planFilter').oninput=renderCatalog; $('networkFilter').oninput=renderCatalog; $('networkSelect').onchange=updateNetworkDetail; $('findRates').onclick=findRatesFromUrl; $('findUploadedRates').onclick=findRatesFromUpload; $('downloadCsv').onclick=downloadCsv;
</script>
</body>
</html>'''
