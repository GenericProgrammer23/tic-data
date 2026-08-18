from __future__ import annotations

HTML_PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>TIC data</title>
  <style>
    :root { font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:#18212f; background:#f5f7fa; }
    * { box-sizing:border-box; }
    body { margin:0; }
    main { max-width:1180px; margin:0 auto; padding:32px 20px 64px; }
    h1 { margin:0 0 6px; font-size:32px; }
    h2 { margin:0 0 14px; font-size:20px; }
    p { line-height:1.5; }
    .muted,.field-hint { color:#64748b; }
    .field-hint { font-size:12px; margin-top:5px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; }
    .card { background:white; border:1px solid #dbe2ea; border-radius:12px; padding:18px; margin-top:18px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
    label { display:block; font-size:13px; font-weight:650; margin:12px 0 5px; }
    input,select,button { width:100%; font:inherit; }
    input,select { border:1px solid #cbd5e1; border-radius:8px; padding:10px 11px; background:white; }
    button { border:0; border-radius:8px; padding:11px 14px; background:#0f172a; color:white; font-weight:650; cursor:pointer; }
    button.secondary { background:#e2e8f0; color:#0f172a; }
    button:disabled { opacity:.5; cursor:not-allowed; }
    .row { display:flex; gap:10px; align-items:end; }
    .row > * { flex:1; }
    .status { margin-top:12px; padding:10px 12px; border-radius:8px; background:#f1f5f9; white-space:pre-wrap; font-size:13px; }
    .error { background:#fee2e2; color:#991b1b; }
    .success { background:#dcfce7; color:#166534; }
    .warning { background:#fef3c7; color:#92400e; }
    .hidden { display:none !important; }
    .chip-wrap { display:flex; flex-wrap:wrap; gap:7px; margin-top:8px; min-height:28px; }
    .code-chip { display:inline-flex; align-items:center; gap:6px; background:#e2e8f0; border-radius:7px; padding:5px 7px 5px 9px; font-size:13px; font-weight:650; }
    .code-chip button { width:auto; padding:0 3px; background:transparent; color:#64748b; font-size:16px; line-height:1; }
    .progress-card { margin-top:12px; border:1px solid #cbd5e1; border-radius:10px; padding:14px; background:#f8fafc; }
    .progress-head { display:flex; justify-content:space-between; gap:12px; align-items:center; }
    .progress-stage { font-weight:700; }
    .progress-percent { font-variant-numeric:tabular-nums; font-weight:700; }
    .progress-track { height:14px; border-radius:999px; background:#e2e8f0; overflow:hidden; margin:10px 0 12px; }
    .progress-fill { height:100%; width:0%; background:#0f172a; transition:width .35s ease; }
    .steps { display:grid; grid-template-columns:repeat(4,1fr); gap:7px; margin-top:10px; }
    .step { border:1px solid #dbe2ea; border-radius:8px; padding:8px; font-size:12px; background:white; }
    .step.active { border-color:#0f172a; font-weight:700; }
    .step.done { background:#e2e8f0; }
    .progress-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; margin-top:10px; }
    .metric { background:white; border:1px solid #e2e8f0; border-radius:7px; padding:8px 10px; font-size:12px; }
    .metric b { display:block; font-size:14px; margin-top:2px; }
    details.diagnostics { margin-top:12px; border:1px solid #dbe2ea; border-radius:8px; padding:10px 12px; background:#fff; }
    details.diagnostics summary { cursor:pointer; font-weight:650; font-size:13px; }
    .diagnostic-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:8px; margin-top:10px; }
    .diagnostic-item { padding:8px 10px; background:#f8fafc; border-radius:7px; font-size:12px; overflow-wrap:anywhere; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th,td { text-align:left; border-bottom:1px solid #e2e8f0; padding:9px 8px; vertical-align:top; }
    th { position:sticky; top:0; background:white; }
    .table-wrap { max-height:520px; overflow:auto; border:1px solid #e2e8f0; border-radius:8px; margin-top:12px; }
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
      <div><label>Plan type filter</label><input id="planFilter" placeholder="e.g. OAP, PPO, HMO" /></div>
      <div><label>Network/file search</label><input id="networkFilter" placeholder="e.g. National OAP, National PPO" /></div>
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
        <div id="tinHint" class="field-hint">Both XX-XXXXXXX and XXXXXXXXX formats are accepted. TIN matching uses <code>tin.type = ein</code> when supplied by the payer.</div>
      </div>
      <div><label>Type 2 or Type 1 NPI</label><input id="npi" placeholder="1234567890" /></div>
      <div><label>Business name (optional)</label><input id="businessName" placeholder="Provider organization name" /></div>
    </div>
    <div class="grid">
      <div>
        <label>Billing codes</label>
        <input id="codeInput" placeholder="Type 97110, then comma" autocomplete="off" />
        <div class="field-hint">Type a code followed by a comma or Enter. Each recorded code appears below.</div>
        <div id="codeChips" class="chip-wrap"></div>
      </div>
      <div>
        <label>Billing code type</label><input id="codeType" value="CPT" />
        <label>Billing class</label>
        <select id="billingClass"><option value="professional" selected>professional</option><option value="">any</option><option value="institutional">institutional</option><option value="both">both</option></select>
      </div>
    </div>
    <button id="findRates" style="margin-top:12px">Find negotiated rates</button>
    <div id="rateStatus" class="status">Load an index and choose a network, or use the direct-file section below.</div>

    <div id="progressPanel" class="progress-card hidden">
      <div class="progress-head">
        <div><div id="progressStage" class="progress-stage">Queued</div><div id="progressMessage" class="field-hint"></div></div>
        <div id="progressPercent" class="progress-percent">0%</div>
      </div>
      <div class="progress-track"><div id="progressFill" class="progress-fill"></div></div>
      <div class="steps">
        <div id="step1" class="step">1. Download file</div>
        <div id="step2" class="step">2. Match provider groups</div>
        <div id="step3" class="step">3. Scan negotiated rates</div>
        <div id="step4" class="step">4. Complete</div>
      </div>
      <div class="progress-grid">
        <div class="metric">Elapsed<b id="elapsedMetric">0s</b></div>
        <div class="metric">Downloaded<b id="downloadMetric">—</b></div>
        <div class="metric">Download speed<b id="speedMetric">—</b></div>
        <div class="metric">Download ETA<b id="etaMetric">—</b></div>
        <div class="metric">Provider groups matched<b id="providerMetric">—</b></div>
        <div class="metric">In-network rows scanned<b id="scanMetric">—</b></div>
        <div class="metric">Requested codes seen<b id="codesSeenMetric">—</b></div>
        <div class="metric">Rate rows found<b id="ratesMetric">—</b></div>
      </div>
    </div>

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
let catalog=[];
let lastRates=[];
let billingCodes=[];
let activeJob=null;
const $=id=>document.getElementById(id);
const splitValues=value=>value.split(/[\n,;\s]+/).map(v=>v.trim()).filter(Boolean);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalizeIdentifier=value=>String(value||'').replace(/[^0-9A-Za-z]/g,'').toLowerCase();
function setStatus(id,text,kind=''){const e=$(id);e.textContent=text;e.className='status '+kind;}
function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
function formatBytes(value){if(value===null||value===undefined)return '—';let n=Number(value),units=['B','KB','MB','GB','TB'],i=0;while(n>=1024&&i<units.length-1){n/=1024;i++;}return `${n.toFixed(i?1:0)} ${units[i]}`;}
function formatDuration(seconds){if(seconds===null||seconds===undefined||!Number.isFinite(Number(seconds)))return '—';let s=Math.max(0,Math.round(Number(seconds)));if(s<60)return `${s}s`;const m=Math.floor(s/60),r=s%60;if(m<60)return `${m}m ${r}s`;const h=Math.floor(m/60);return `${h}h ${m%60}m`;}

function updateTinHint(){const raw=$('tin').value.trim(),normalized=normalizeIdentifier(raw);if(!raw){$('tinHint').innerHTML='Both XX-XXXXXXX and XXXXXXXXX formats are accepted. TIN matching uses <code>tin.type = ein</code> when supplied by the payer.';return;}if(/^\d{9}$/.test(normalized))$('tinHint').textContent=`Will search as ${normalized}. Dashes/spaces are ignored.`;else $('tinHint').textContent=`Will search as ${normalized||'(empty)'}. A standard EIN/TIN is normally 9 digits.`;}
function addBillingCodes(raw){const values=String(raw||'').split(/[\n,;\s]+/).map(v=>v.trim().toUpperCase()).filter(Boolean);for(const value of values)if(!billingCodes.includes(value))billingCodes.push(value);renderBillingCodes();}
function renderBillingCodes(){$('codeChips').innerHTML=billingCodes.map((code,index)=>`<span class="code-chip">${esc(code)}<button type="button" data-index="${index}" title="Remove ${esc(code)}">×</button></span>`).join('');$('codeChips').querySelectorAll('button').forEach(button=>button.onclick=()=>{billingCodes.splice(Number(button.dataset.index),1);renderBillingCodes();});}
function commitCodeInput(){const input=$('codeInput');if(input.value.trim())addBillingCodes(input.value);input.value='';}
function providerPayload(){const tins=splitValues($('tin').value),npis=splitValues($('npi').value),names=$('businessName').value.trim()?[$('businessName').value.trim()]:[];if(!tins.length&&!npis.length&&!names.length)throw new Error('Enter at least one TIN, NPI, or business name.');return {tins,npis,business_names:names};}
function filtersPayload(){commitCodeInput();return {billing_codes:[...billingCodes],billing_code_types:splitValues($('codeType').value),service_codes:[],billing_classes:$('billingClass').value?[$('billingClass').value]:[],negotiated_types:[],limit:5000};}
async function parseResponse(response){const data=await response.json();if(!response.ok)throw new Error(data.detail||JSON.stringify(data));return data;}

function renderCatalog(){const plan=$('planFilter').value.trim().toLowerCase(),search=$('networkFilter').value.trim().toLowerCase();const rows=catalog.filter(r=>(!plan||r.plan_names.some(x=>x.toLowerCase().includes(plan)))&&(!search||(r.network+' '+r.description+' '+r.source).toLowerCase().includes(search)));$('networkSelect').innerHTML='<option value="">-- Select a network intentionally --</option>'+rows.map(r=>`<option value="${esc(r.location)}">${esc(r.network)} — ${esc(r.source)} — ${esc(r.file_format)} (${r.plan_sponsor_count} sponsors)</option>`).join('');if(rows.length===1)$('networkSelect').value=rows[0].location;$('networkCard').classList.remove('hidden');updateNetworkDetail();}
function selectedNetwork(){const value=$('networkSelect').value;return value?catalog.find(r=>r.location===value):null;}
function updateNetworkDetail(){const r=selectedNetwork();if(!r){$('networkDetail').textContent='Select the specific network you want to search.';return;}$('networkDetail').textContent=`${r.description}\nSource: ${r.source}\nPlan types: ${r.plan_names.join(', ')||'n/a'}\nReferenced by ${r.plan_sponsor_count} plan sponsors. Format: ${r.file_format}.`;}
async function loadCatalogFromUpload(){const file=$('indexFile').files[0];if(!file)return setStatus('indexStatus','Choose an index file first.','error');setStatus('indexStatus','Reading and normalizing index…');const form=new FormData();form.append('file',file);try{const data=await parseResponse(await fetch('/catalog/upload',{method:'POST',body:form}));catalog=data.files;setStatus('indexStatus',`${data.metadata.reporting_entity_name||'Payer'} — ${data.file_count} unique in-network files.`,'success');renderCatalog();}catch(e){setStatus('indexStatus',e.message,'error');}}
async function loadCatalogFromUrl(){const url=$('indexUrl').value.trim();if(!url)return setStatus('indexStatus','Paste an index URL first.','error');setStatus('indexStatus','Downloading and normalizing index…');try{const data=await parseResponse(await fetch('/catalog/url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})}));catalog=data.files;setStatus('indexStatus',`${data.metadata.reporting_entity_name||'Payer'} — ${data.file_count} unique in-network files.`,'success');renderCatalog();}catch(e){setStatus('indexStatus',e.message,'error');}}

function resetProgress(){$('progressPanel').classList.remove('hidden');$('progressFill').style.width='0%';$('progressPercent').textContent='0%';$('progressStage').textContent='Queued';$('progressMessage').textContent='';['elapsedMetric','downloadMetric','speedMetric','etaMetric','providerMetric','scanMetric','codesSeenMetric','ratesMetric'].forEach(id=>$(id).textContent='—');for(let i=1;i<=4;i++)$('step'+i).className='step';}
function updateProgress(job){const pct=Math.max(0,Math.min(100,Number(job.percent||0)));$('progressFill').style.width=pct+'%';$('progressPercent').textContent=Math.round(pct)+'%';$('progressStage').textContent=`Step ${job.step||0}/${job.step_count||4}: ${job.stage||'Working'}`;$('progressMessage').textContent=job.message||'';$('elapsedMetric').textContent=formatDuration(job.elapsed_seconds);$('downloadMetric').textContent=job.downloaded_bytes?`${formatBytes(job.downloaded_bytes)}${job.total_bytes?' / '+formatBytes(job.total_bytes):''}`:'—';$('speedMetric').textContent=job.download_speed_bytes_per_second?formatBytes(job.download_speed_bytes_per_second)+'/s':'—';$('etaMetric').textContent=job.download_eta_seconds!==null?formatDuration(job.download_eta_seconds):'—';const d=job.details||{};$('providerMetric').textContent=d.provider_groups_matched??d.matched_provider_group_id_count??'—';$('scanMetric').textContent=d.in_network_items_scanned??'—';$('codesSeenMetric').textContent=(d.requested_billing_codes_seen||[]).join(', ')||'—';$('ratesMetric').textContent=d.rate_count??d.negotiated_prices_matched_filters??'—';for(let i=1;i<=4;i++){$('step'+i).className='step'+(i<job.step?' done':i===job.step?' active':'');}}
async function pollJob(jobId,label){activeJob=jobId;while(activeJob===jobId){const job=await parseResponse(await fetch(`/extract/jobs/${jobId}`));updateProgress(job);if(job.status==='complete'){activeJob=null;renderRates(job.result,label);return;}if(job.status==='error'){activeJob=null;setStatus('rateStatus',job.error||job.message||'Search failed.','error');$('findRates').disabled=false;return;}await sleep(1000);}}
async function findRatesFromUrl(){const network=selectedNetwork();if(!network)return setStatus('rateStatus','Choose a specific network/rate file first.','error');try{$('findRates').disabled=true;resetProgress();setStatus('rateStatus',`Starting ${network.network} search…`);const body={url:network.location,organization:providerPayload(),filters:filtersPayload()};const created=await parseResponse(await fetch('/extract/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}));await pollJob(created.job_id,network.network);}catch(e){activeJob=null;$('findRates').disabled=false;setStatus('rateStatus',e.message,'error');}}
async function findRatesFromUpload(){const file=$('rateFile').files[0];if(!file)return setStatus('rateStatus','Choose a rate file first.','error');try{const form=new FormData();form.append('file',file);form.append('organization_json',JSON.stringify(providerPayload()));form.append('filters_json',JSON.stringify(filtersPayload()));setStatus('rateStatus','Searching uploaded rate file…');const data=await parseResponse(await fetch('/extract/upload',{method:'POST',body:form}));renderRates(data,file.name);}catch(e){setStatus('rateStatus',e.message,'error');}}

function troubleshootingMessage(data){const d=data.diagnostics||{},requested=((d.requested_filters||{}).billing_codes||[]),seen=d.requested_billing_codes_seen||[];if(data.rate_count)return 'Rates were found. These counters show how the TIN → provider group → provider_references → negotiated price join resolved.';if(requested.length&&!seen.length)return 'None of the requested billing codes were seen in this rate file.';if((d.provider_groups_matched||0)===0&&(d.embedded_provider_groups_matched||0)===0)return 'No provider group matched the entered TIN/NPI. Check the Provider Groups structure and tin.type/tin.value.';if((d.negotiated_rate_groups_linked_to_provider||0)===0)return 'The provider group was found, but no negotiated-rate record for the requested service filters referenced one of the matched provider group IDs.';if((d.negotiated_prices_scanned_for_linked_groups||0)>0&&(d.negotiated_prices_matched_filters||0)===0)return `The provider/code join succeeded, but price filters removed the remaining rows. Billing classes present: ${(d.billing_classes_seen_for_linked_rates||[]).join(', ')||'unknown'}.`;return 'No final rate rows were returned. Review the counters below to see where matching stopped.';}
function renderDiagnostics(data){const d=data.diagnostics||{};$('diagnosticsPanel').classList.remove('hidden');$('diagnosticsPanel').open=!data.rate_count;setStatus('diagnosticMessage',troubleshootingMessage(data),data.rate_count?'success':'warning');const fields=[['Normalized TIN(s)',((d.normalized_organization||{}).tins||[]).join(', ')||'—'],['Matched provider group IDs',(d.matched_provider_group_ids||data.matched_provider_group_ids||[]).join(', ')||'—'],['Provider references scanned',d.provider_references_scanned??'—'],['Provider groups scanned',d.provider_groups_scanned??'—'],['Provider groups matched',d.provider_groups_matched??'—'],['Requested codes',((d.requested_filters||{}).billing_codes||[]).join(', ')||'—'],['Requested codes seen',(d.requested_billing_codes_seen||[]).join(', ')||'—'],['In-network rows scanned',d.in_network_items_scanned??'—'],['Service rows after filters',d.service_items_matched_filters??'—'],['Rate groups scanned',d.negotiated_rate_groups_scanned??'—'],['Rate groups linked to provider',d.negotiated_rate_groups_linked_to_provider??'—'],['Price rows after filters',d.negotiated_prices_matched_filters??'—'],['Billing classes present',(d.billing_classes_seen_for_linked_rates||[]).join(', ')||'—']];$('diagnosticGrid').innerHTML=fields.map(([label,value])=>`<div class="diagnostic-item"><b>${esc(label)}</b><br>${esc(value)}</div>`).join('');}
function renderRates(data,label){lastRates=data.rates||[];$('findRates').disabled=false;$('resultsCard').classList.remove('hidden');$('resultsBody').innerHTML=lastRates.map(r=>`<tr><td>${esc(r.billing_code)}</td><td>${esc(r.negotiated_rate)}</td><td>${esc(r.negotiated_type)}</td><td>${esc(r.billing_class)}</td><td>${esc((r.service_code||[]).join(', '))}</td><td>${esc(r.expiration_date)}</td><td>${esc(r.description||r.name)}</td></tr>`).join('');const groups=(data.matched_provider_group_ids||[]).length;const summary=`${label}: ${data.rate_count} rate row(s); ${groups} matched provider group ID(s)${data.truncated?'; results truncated at limit':''}.`;setStatus('rateStatus',summary,data.rate_count?'success':'warning');setStatus('resultSummary',summary);renderDiagnostics(data);$('resultsCard').scrollIntoView({behavior:'smooth'});}
function downloadCsv(){if(!lastRates.length)return;const cols=['billing_code_type','billing_code','negotiated_rate','negotiated_type','billing_class','service_code','expiration_date','description','name'];const quote=v=>'"'+String(Array.isArray(v)?v.join('|'):(v??'')).replaceAll('"','""')+'"';const csv=[cols.join(','),...lastRates.map(r=>cols.map(c=>quote(r[c])).join(','))].join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='tic-rates.csv';a.click();URL.revokeObjectURL(a.href);}

$('loadUpload').onclick=loadCatalogFromUpload;
$('loadUrl').onclick=loadCatalogFromUrl;
$('planFilter').oninput=renderCatalog;
$('networkFilter').oninput=renderCatalog;
$('networkSelect').onchange=updateNetworkDetail;
$('findRates').onclick=findRatesFromUrl;
$('findUploadedRates').onclick=findRatesFromUpload;
$('downloadCsv').onclick=downloadCsv;
$('tin').oninput=updateTinHint;
$('codeInput').addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===','){event.preventDefault();commitCodeInput();}});
$('codeInput').addEventListener('input',()=>{if($('codeInput').value.includes(',')){addBillingCodes($('codeInput').value);$('codeInput').value='';}});
</script>
</body>
</html>'''
