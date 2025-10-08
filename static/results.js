async function refreshResults(){
  const res = await fetch('/targets/');
  const rows = await res.json();
  const tb = document.querySelector('#res tbody');
  tb.innerHTML = '';
  rows.forEach(r=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${r.domain}</td>
      <td>${r.brand || ''}</td>
      <td>${r.is_verified}</td>
      <td>${r.is_active}</td>
      <td>
        <a href="/reports/targets/${r.id}/html" target="_blank" class="btn">View</a>
        <a href="/reports/targets/${r.id}/download" class="btn" style="margin-left:6px;">⬇ HTML</a>
        <a href="/reports/targets/${r.id}/pdf" class="btn" style="margin-left:6px;">📄 PDF</a>
      </td>`;
    tb.appendChild(tr);
  });
}

setInterval(refreshResults, 10000);
refreshResults();