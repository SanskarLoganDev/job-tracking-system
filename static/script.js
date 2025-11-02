// SPA navigation (adds a view-enter animation class for transitions)
document.querySelectorAll('.icon-btn[data-view]').forEach(btn => {
  btn.addEventListener('click', () => {
    const view = btn.getAttribute('data-view');
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(`view-${view}`);
    if (!target) return;
    target.classList.add('active', 'view-enter');
    // remove the enter class after the animation completes
    target.addEventListener('animationend', () => target.classList.remove('view-enter'), { once: true });
    snack(`Switched to ${view}`);
    // re-apply stagger to any newly visible fade-up elements
    staggerFadeUps(target);
  });
});

// Ripple coordinates
document.querySelectorAll('.ripple').forEach(el => {
  el.addEventListener('pointerdown', (e) => {
    const rect = el.getBoundingClientRect();
    el.style.setProperty('--x', (e.clientX - rect.left) + 'px');
    el.style.setProperty('--y', (e.clientY - rect.top) + 'px');
  });
});

// Progress bar
const topProgress = document.getElementById('topProgress');
function prog(on){ topProgress.classList.toggle('active', !!on); }

// Snackbar
const sb = document.getElementById('snackbar');
function snack(msg){ sb.textContent = msg; sb.classList.add('show'); setTimeout(()=>sb.classList.remove('show'), 1800); }

// Sign in (demo)
const signInBtn = document.getElementById('signInBtn');
signInBtn.addEventListener('click', () => {
  prog(true);
  setTimeout(()=>{
    prog(false);
    snack('Signed in (demo)');
  }, 800);
});

// Company form submit (localStorage demo)
document.getElementById('companyForm').addEventListener('submit', (e) => {
  e.preventDefault();
  prog(true);
  const payload = {
    name: document.getElementById('company').value,
    post_days: +document.getElementById('postdays').value || 14,
    careers_url: document.getElementById('careers').value,
    keywords: document.getElementById('keywords').value,
    location: document.getElementById('location').value,
    email: document.getElementById('contactEmail').value || null,
    created_at: new Date().toISOString()
  };
  const list = JSON.parse(localStorage.getItem('hustlehub_companies') || '[]');
  list.push(payload);
  localStorage.setItem('hustlehub_companies', JSON.stringify(list));
  setTimeout(()=>{ prog(false); snack('Company saved (local demo)'); renderCompanies(); }, 700);
});

// Example filler
document.getElementById('loadExample').addEventListener('click', () => {
  document.getElementById('company').value = 'Google';
  document.getElementById('postdays').value = 14;
  document.getElementById('careers').value = 'https://careers.google.com/jobs/results/';
  document.getElementById('keywords').value = 'software, backend, cloud';
  document.getElementById('location').value = 'US-Remote';
  document.getElementById('contactEmail').value = 'you@example.com';
  snack('Example filled');
});

// Filters (demo only)
document.getElementById('applyFilters').addEventListener('click', () => snack('Filters applied (demo)'));
document.getElementById('clearFilters').addEventListener('click', () => {
  ['fltRole','fltLoc','fltAge'].forEach(id => document.getElementById(id).value='');
  snack('Filters cleared');
});

// Dark mode toggle
const darkToggle = document.getElementById('darkModeToggle');
if (darkToggle) darkToggle.addEventListener('change', (e)=>{
  document.body.classList.toggle('dark', e.target.checked);
});

// Load jobs from static jobs.json or demo
async function loadJobs(){
  const container = document.getElementById('jobsList');
  container.innerHTML = '';
  try{
    const res = await fetch('./jobs.json', {cache:'no-cache'});
    if(res.ok){
      const data = await res.json();
      (data.jobs || []).forEach(addJobCard);
      snack(`Loaded ${data.count||data.jobs.length} jobs.json item(s)`);
      // stagger fade-up animations for the newly inserted job cards
      staggerFadeUps(container);
      return;
    }
    throw new Error('no jobs.json');
  }catch{
    [
      {title:'Software Engineer', company:'Acme', location:'Remote', link:'#', posted_text:'2d ago'},
      {title:'Cloud DevOps Engineer', company:'Globex', location:'Austin, TX', link:'#', posted_text:'1d ago'},
      {title:'Data Analyst', company:'Initech', location:'NYC', link:'#', posted_text:'3d ago'}
    ].forEach(addJobCard);
    snack('Showing demo jobs');
    // apply stagger for demo jobs
    staggerFadeUps(container);
  }

  function addJobCard(j){
    const card = document.createElement('div');
    card.className = 'job-card fade-up';
    card.innerHTML = `
      <div style="font-weight:600">${j.title}</div>
      <div class="meta">${j.company} • ${j.location || '—'}</div>
      <a href="${j.link}" target="_blank" rel="noopener">Open ↗</a>
      <div class="meta">${j.posted_text || ''}</div>`;
    container.appendChild(card);
  }
}

// Render companies
function renderCompanies(){
  const mount = document.getElementById('companiesList');
  if(!mount) return;
  const data = JSON.parse(localStorage.getItem('hustlehub_companies') || '[]');
  if(!data.length){ mount.innerHTML = '<div class="hint">No companies yet.</div>'; return; }
  const rows = data.map(c => `
    <div class="row">
      <div>${c.name}</div>
      <div>${c.location||'—'}</div>
      <div>${c.post_days}d</div>
      <div><a href="${c.careers_url}" target="_blank">Careers ↗</a></div>
    </div>`).join('');
  mount.innerHTML = `
    <div class="tbl">
      <div class="row head"><div>Name</div><div>Location</div><div>Post Age</div><div>Link</div></div>
      ${rows}
    </div>`;
}

// Inject minimal table styles
const style = document.createElement('style');
style.textContent = `.tbl{display:grid;gap:6px}
.row{display:grid;grid-template-columns:2fr 1.2fr .8fr 1fr;gap:10px;border:1px solid var(--g-border);border-radius:10px;padding:10px;background:#fff}
.row.head{background:#eef3fd;border-color:#c9d7ff;font-weight:600}`;
document.head.appendChild(style);

// Init
document.addEventListener('DOMContentLoaded', ()=>{ loadJobs(); renderCompanies(); });

/* --- Animation helpers --- */
// Stagger visible .fade-up elements. If root is provided, only items inside are used.
function staggerFadeUps(root=document, baseDelay=0){
  const nodes = Array.from(root.querySelectorAll('.fade-up'))
    .filter(n => n.offsetParent !== null); // visible
  nodes.forEach((el, i) => {
    el.style.animationDelay = `${baseDelay + i*80}ms`;
  });
}

// Animate brand letters on first load
function animateBrand(){
  const letters = Array.from(document.querySelectorAll('.brand span'));
  letters.forEach((el, i) => {
    el.style.animation = `brandPop .45s cubic-bezier(.2,.9,.2,1) forwards`;
    el.style.animationDelay = `${i*70}ms`;
  });
}

// run small page intro animations when DOM ready
document.addEventListener('DOMContentLoaded', ()=>{
  // small timeout so layout is stable
  requestAnimationFrame(()=>{
    animateBrand();
    staggerFadeUps();
  });
});
