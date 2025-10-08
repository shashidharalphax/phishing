async function refreshTargets(){
  const res = await fetch('/targets/');
  const rows = await res.json();
  const tb = document.querySelector('#targets tbody');
  tb.innerHTML = '';
  rows.sort((a,b)=>a.id-b.id);
  rows.forEach(r=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${r.domain}</td>
      <td>${r.brand||''}</td>
      <td>${r.status}</td>
      <td>${r.is_verified}</td>
      <td>${r.is_active}</td>
      <td>${r.scan_interval_minutes||5}</td>
      <td><a href="/reports/targets/${r.id}/html" target="_blank" class="btn">Report</a></td>`;
    tb.appendChild(tr);
  });
}

document.getElementById('startBtn').onclick = async ()=>{
  const res = await fetch('/targets/start', {method:'POST'});
  const data = await res.json();
  alert('Sequential scan started for '+data.domains+' domains.');
};

document.getElementById('stopBtn').onclick = async ()=>{
  await fetch('/targets/stop', {method:'POST'});
  alert('Scanning stopped.');
};

// ---------------- New status display ----------------
async function refreshStatus(){
  try{
    const r = await fetch('/targets/status');
    const s = await r.json();
    let el = document.getElementById('scanStatus');
    if(!el){
      el = document.createElement('p');
      el.id = 'scanStatus';
      el.style = 'font-weight:bold; color:darkblue;';
      document.body.insertBefore(el, document.getElementById('targets'));
    }
    if(s.running){
      el.textContent = `🔍 Scanning… currently processing: ${s.current_target}`;
    }else if(s.stopped){
      el.textContent = `⏹️ Scanning stopped`;
    }else{
      el.textContent = `✅ Idle — no scans in progress`;
    }
  }catch(e){ console.error(e); }
}
// ----------------------------------------------------

function setupDnD(){
  const drop=document.getElementById('drop');
  const file=document.getElementById('file');
  const msg=document.getElementById('msg');
  const upload=async(f)=>{
    const fd=new FormData();
    fd.append('file',f);
    const res=await fetch('/targets/bulk',{method:'POST',body:fd});
    const data=await res.json();
    msg.innerText=JSON.stringify(data);
    refreshTargets();
  };
  drop.ondragover=e=>{e.preventDefault();drop.style.background='#f5f5f5';};
  drop.ondragleave=e=>{drop.style.background='white';};
  drop.ondrop=e=>{e.preventDefault();drop.style.background='white';if(e.dataTransfer.files.length)upload(e.dataTransfer.files[0]);};
  file.onchange=()=>{if(file.files.length)upload(file.files[0]);};
}

setupDnD();
refreshTargets();
setInterval(refreshTargets,15000);
setInterval(refreshStatus,5000);
refreshStatus();