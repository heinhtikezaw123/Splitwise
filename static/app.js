/* ══════════════════════════════════════════════
   SplitWise — app.js
   Minimal JS: modals, accordion, payer rows.
   ALL logic lives in Python (app.py).
   ══════════════════════════════════════════════ */

// ── Modal helpers ─────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add('open');
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// Close modal when clicking the backdrop
document.querySelectorAll('.modal-bg').forEach(bg => {
  bg.addEventListener('click', e => {
    if (e.target === bg) bg.classList.remove('open');
  });
});

// ── Accordion toggle ──────────────────────────
function toggleCard(bodyId) {
  const body = document.getElementById(bodyId);
  if (!body) return;
  const isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : 'block';

  // Rotate arrow
  const card = body.closest('.event-card, .sub-item');
  if (card) card.classList.toggle('open', !isOpen);
}

// ── Sub-activity modal ────────────────────────
function openSubModal(evId) {
  const form = document.getElementById('form-add-sub');
  form.action = `/events/${evId}/sub/add`;
  openModal('modal-add-sub');
  setTimeout(() => form.querySelector('input[name="name"]').focus(), 100);
}

// ── Expense modal ─────────────────────────────
// Stores context for the current expense form
let _expEvId  = '';
let _expSubId = '';
let _expMembers = [];   // [{id, name, color, initials}]
let _payerRows = [];
let _excludes  = new Set();

function openExpenseModal(evId, subId) {
  _expEvId  = evId;
  _expSubId = subId;
  _payerRows = [];
  _excludes  = new Set();

  // Set form action
  document.getElementById('form-add-expense').action = `/events/${evId}/sub/${subId}/expense/add`;

  // Gather participant data from DOM (chips already rendered server-side)
  // We read them from the sub-body that is currently open
  const subBody = document.getElementById('sub-' + subId);
  _expMembers = [];

  if (subBody) {
    subBody.querySelectorAll('.chip-btn').forEach(btn => {
      // Only included members (not already excluded at sub level)
      if (!btn.classList.contains('chip-excluded')) {
        const av   = btn.querySelector('.av');
        const color    = av ? av.style.background : '#7c6dfa';
        const initials = av ? av.textContent.trim() : '?';
        // Extract name: full text minus the initials text minus emoji
        const fullText = btn.textContent.trim().replace(/🚫/g,'').trim();
        const name = fullText.replace(initials,'').trim();
        // Get person id from form action in parent
        const form = btn.closest('form');
        const action = form ? form.action : '';
        const parts  = action.split('/');
        const pid = parts[parts.length - 1];
        _expMembers.push({ id: pid, name, color, initials });
      }
    });
  }

  renderExpParticipants();
  renderExpPayerSelect();
  renderExpPayerRows();
  openModal('modal-add-expense');
  setTimeout(() => document.querySelector('#modal-add-expense input[name="desc"]').focus(), 100);
}

function renderExpParticipants() {
  const wrap = document.getElementById('exp-participant-list');
  wrap.innerHTML = _expMembers.map(m => {
    const excl = _excludes.has(m.id);
    return `<div class="chip toggle-chip ${excl ? '' : 'selected'}"
                 id="eptog-${m.id}"
                 onclick="toggleExpExclude('${m.id}')"
                 style="${excl ? 'opacity:.5;border-color:var(--danger)' : 'border-color:var(--accent3);background:rgba(109,250,188,.08)'}">
      <div class="av sm" style="background:${m.color}">${m.initials}</div>
      ${m.name}${excl ? ' 🚫' : ''}
    </div>`;
  }).join('');
  syncHiddenExcludes();
}

function toggleExpExclude(id) {
  if (_excludes.has(id)) {
    _excludes.delete(id);
  } else {
    _excludes.add(id);
    // Remove from payer rows if excluded
    _payerRows = _payerRows.filter(r => r.id !== id);
    renderExpPayerRows();
  }
  renderExpParticipants();
  renderExpPayerSelect();
}

function syncHiddenExcludes() {
  // Write exclude values as hidden inputs so Flask gets them
  const container = document.getElementById('exp-hidden-fields');
  const existing  = container.querySelectorAll('input[name="excludes"]');
  existing.forEach(el => el.remove());
  _excludes.forEach(id => {
    const inp = document.createElement('input');
    inp.type  = 'hidden';
    inp.name  = 'excludes';
    inp.value = id;
    container.appendChild(inp);
  });
}

function renderExpPayerSelect() {
  const sel = document.getElementById('exp-payer-select');
  sel.innerHTML = '<option value="">— add a payer —</option>';
  _expMembers.forEach(m => {
    if (!_excludes.has(m.id)) {
      sel.innerHTML += `<option value="${m.id}">${m.name}</option>`;
    }
  });
}

function addPayerRow() {
  const sel = document.getElementById('exp-payer-select');
  const id  = sel.value;
  if (!id) return;
  if (_payerRows.some(r => r.id === id)) {
    alert('Already added'); return;
  }
  const member = _expMembers.find(m => m.id === id);
  if (!member) return;
  _payerRows.push({ id, name: member.name, color: member.color, initials: member.initials, amount: 0 });
  sel.value = '';
  renderExpPayerRows();
}

function renderExpPayerRows() {
  const wrap = document.getElementById('exp-payer-rows');
  const hiddenWrap = document.getElementById('exp-hidden-fields');

  // Remove old payer hidden inputs
  hiddenWrap.querySelectorAll('input[data-payer]').forEach(el => el.remove());

  if (!_payerRows.length) {
    wrap.innerHTML = '<div style="color:var(--muted);font-size:12px;margin-bottom:6px">No payers yet</div>';
    document.getElementById('exp-payer-total').textContent = '';
    return;
  }

  wrap.innerHTML = _payerRows.map((r, i) => `
    <div class="payer-row">
      <div class="av sm" style="background:${r.color};width:28px;height:28px;font-size:11px">${r.initials}</div>
      <div class="p-name">${r.name}</div>
      <input type="text" inputmode="decimal" placeholder="$0.00"
             value="${r.amount || ''}"
             oninput="updatePayerAmt(${i}, this.value)"
             style="width:100px;text-align:right">
      <button type="button" class="btn btn-danger" onclick="removePayerRow(${i})" style="padding:4px 8px">✕</button>
    </div>
  `).join('');

  // Write hidden fields for Flask
  _payerRows.forEach((r, i) => {
    const idInp  = document.createElement('input');
    idInp.type   = 'hidden';
    idInp.name   = `payer_id_${i}`;
    idInp.value  = r.id;
    idInp.setAttribute('data-payer','1');

    const amtInp = document.createElement('input');
    amtInp.type  = 'hidden';
    amtInp.name  = `payer_amt_${i}`;
    amtInp.value = r.amount || 0;
    amtInp.id    = `hamt_${i}`;
    amtInp.setAttribute('data-payer','1');

    hiddenWrap.appendChild(idInp);
    hiddenWrap.appendChild(amtInp);
  });

  updatePayerTotal();
}

function updatePayerAmt(idx, val) {
  _payerRows[idx].amount = parseFloat(val) || 0;
  const hid = document.getElementById(`hamt_${idx}`);
  if (hid) hid.value = _payerRows[idx].amount;
  updatePayerTotal();
}

function removePayerRow(idx) {
  _payerRows.splice(idx, 1);
  renderExpPayerRows();
}

function updatePayerTotal() {
  const total = _payerRows.reduce((a, r) => a + (r.amount || 0), 0);
  const el = document.getElementById('exp-payer-total');
  el.textContent = total > 0 ? `Total: $${total.toFixed(2)}` : '';
}

// ── Member picker in Add Event modal ─────────
function filterModalPeople(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('#modal-people-list .chip-label').forEach(label => {
    const name = label.dataset.name || '';
    label.style.display = name.includes(q) ? '' : 'none';
  });
}

function toggleChipLabel(checkbox) {
  const chip = document.getElementById('chip-' + checkbox.value);
  if (chip) chip.classList.toggle('selected', checkbox.checked);
}

// ── Auto-open accordions from URL params ─────
(function() {
  const params = new URLSearchParams(window.location.search);
  const openEv  = params.get('open');
  const openSub = params.get('open_sub');
  if (openEv) {
    const el = document.getElementById('ev-' + openEv);
    if (el) {
      el.style.display = 'block';
      const card = el.closest('.event-card');
      if (card) card.classList.add('open');
    }
  }
  if (openSub) {
    const el = document.getElementById('sub-' + openSub);
    if (el) {
      el.style.display = 'block';
      const item = el.closest('.sub-item');
      if (item) item.classList.add('open');
    }
  }
})();
