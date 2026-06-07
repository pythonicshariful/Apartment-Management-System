/**
 * main.js — Apartment Management System
 * Custom modal system (no Bootstrap Modal JS), file previews, toast init
 */

'use strict';

// ── Custom Modal Engine ──────────────────────────────────────────────────────
// Completely bypasses Bootstrap Modal JS to avoid backdrop stacking bugs.

function showModal(id) {
  const overlay = document.getElementById(id);
  if (!overlay) return;
  overlay.classList.add('ams-modal-open');
  document.body.style.overflow = 'hidden';
}

function hideModal(id) {
  const overlay = document.getElementById(id);
  if (!overlay) return;
  overlay.classList.remove('ams-modal-open');
  document.body.style.overflow = '';
}

// Close on backdrop click
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('ams-overlay')) {
    e.target.classList.remove('ams-modal-open');
    document.body.style.overflow = '';
  }
});

// Close on Escape key
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.ams-overlay.ams-modal-open').forEach(el => {
      el.classList.remove('ams-modal-open');
    });
    document.body.style.overflow = '';
  }
});


// ── Toast auto-show ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.toast').forEach(el => {
    const toast = new bootstrap.Toast(el, { delay: 5000 });
    toast.show();
  });

  // Drag & drop for file upload areas
  document.querySelectorAll('.file-upload-area').forEach(area => {
    area.addEventListener('dragover', e => {
      e.preventDefault();
      area.classList.add('drag-over');
    });
    area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
    area.addEventListener('drop', e => {
      e.preventDefault();
      area.classList.remove('drag-over');
      const input = area.querySelector('.file-input');
      if (input && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        input.dispatchEvent(new Event('change'));
      }
    });
  });

  // Submit loading states
  const bookForm = document.getElementById('bookingForm');
  if (bookForm) {
    bookForm.addEventListener('submit', () => {
      const btn = document.getElementById('bookSubmitBtn');
      if (btn) {
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Booking…';
        btn.disabled  = true;
      }
    });
  }

  const editForm = document.getElementById('editForm');
  if (editForm) {
    editForm.addEventListener('submit', () => {
      const btn = document.getElementById('editSubmitBtn');
      if (btn) {
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving…';
        btn.disabled  = true;
      }
    });
  }
});


// ── Booking Modal ────────────────────────────────────────────────────────────
function openBookingModal(aptId) {
  const form = document.getElementById('bookingForm');
  form.action = '/book/' + aptId;
  form.reset();
  resetFileArea('bookPicPreview', 'bookPicPlaceholder');
  resetFileArea('bookDocPreview', 'bookDocPlaceholder');
  document.getElementById('bookingAptId').textContent = aptId;
  showModal('bookingOverlay');
}

function closeBookingModal() {
  hideModal('bookingOverlay');
}


// ── Edit Modal ───────────────────────────────────────────────────────────────
function openEditModal(aptId, name, address, phone, total_price, booking_money, due_amount) {
  const form = document.getElementById('editForm');
  form.action = '/edit/' + aptId;
  document.getElementById('editAptId').textContent  = aptId;
  document.getElementById('edit_name').value        = name    || '';
  document.getElementById('edit_address').value     = address || '';
  document.getElementById('edit_phone').value       = phone   || '';
  document.getElementById('edit_total_price').value = total_price || 0;
  document.getElementById('edit_booking_money').value = booking_money || 0;
  document.getElementById('edit_due_amount').value = due_amount || 0;
  resetFileArea('editPicPreview', 'editPicPlaceholder');
  resetFileArea('editDocPreview', 'editDocPlaceholder');
  showModal('editOverlay');
}

function closeEditModal() {
  hideModal('editOverlay');
}


// ── Cancel Modal ─────────────────────────────────────────────────────────────
function openCancelModal(aptId) {
  document.getElementById('cancelAptDisplay').textContent = 'Apartment ' + aptId;
  document.getElementById('cancelForm').action = '/cancel/' + aptId;
  showModal('cancelOverlay');
}

function closeCancelModal() {
  hideModal('cancelOverlay');
}


// ── Profile Modal (AJAX) ─────────────────────────────────────────────────────
function openProfileModal(aptId) {
  document.getElementById('profileAptId').textContent = aptId;
  document.getElementById('profileLoader').classList.remove('d-none');
  document.getElementById('profileContent').classList.add('d-none');
  document.getElementById('profileError').classList.add('d-none');
  showModal('profileOverlay');

  fetch('/profile/' + aptId)
    .then(r => {
      if (!r.ok) throw new Error('Not found');
      return r.json();
    })
    .then(data => {
      document.getElementById('profileName').textContent    = data.name    || '—';
      document.getElementById('profilePhone').textContent   = data.phone   || '—';
      document.getElementById('profileAddress').textContent = data.address || '—';
      document.getElementById('profileBookedAt').textContent= data.booked_at || '—';
      
      const totalPriceEl = document.getElementById('profileTotalPrice');
      if (totalPriceEl) totalPriceEl.textContent = 'BDT ' + (data.total_price || 0);
      
      const bookingMoneyEl = document.getElementById('profileBookingMoney');
      if (bookingMoneyEl) bookingMoneyEl.textContent = 'BDT ' + (data.booking_money || 0);
      
      const dueAmountEl = document.getElementById('profileDueAmount');
      if (dueAmountEl) dueAmountEl.textContent = 'BDT ' + (data.due_amount || 0);
      
      const invoiceBtn = document.getElementById('profileInvoiceBtn');
      if (invoiceBtn) invoiceBtn.href = '/report/' + aptId;

      const badge = document.getElementById('profileCompanyBadge');
      if (data.booked_by === 'nextgen') {
        badge.innerHTML = `<span class="tag-nextgen"><i class="bi bi-building-fill me-1"></i>${data.company_display || data.booked_by}</span>`;
      } else if (data.booked_by === 'luxury') {
        badge.innerHTML = `<span class="tag-luxury"><i class="bi bi-gem me-1"></i>${data.company_display || data.booked_by}</span>`;
      } else {
        badge.innerHTML = '';
      }

      const picImg     = document.getElementById('profilePicImg');
      const picDefault = document.getElementById('profilePicDefault');
      if (data.profile_pic) {
        picImg.src = '/static/' + data.profile_pic;
        picImg.classList.remove('d-none');
        picDefault.classList.add('d-none');
      } else {
        picImg.classList.add('d-none');
        picDefault.classList.remove('d-none');
      }

      const docRow  = document.getElementById('profileDocRow');
      const docLink = document.getElementById('profileDocLink');
      if (data.document) {
        docLink.href = '/static/' + data.document;
        docRow.classList.remove('d-none');
      } else {
        docRow.classList.add('d-none');
      }

      document.getElementById('profileLoader').classList.add('d-none');
      document.getElementById('profileContent').classList.remove('d-none');
    })
    .catch(() => {
      document.getElementById('profileLoader').classList.add('d-none');
      document.getElementById('profileError').classList.remove('d-none');
    });
}

function closeProfileModal() {
  hideModal('profileOverlay');
}


// ── File Preview Helpers ──────────────────────────────────────────────────────
function previewImage(input, previewId, areaId) {
  const file = input.files[0];
  if (!file) return;
  const preview     = document.getElementById(previewId);
  const area        = document.getElementById(areaId);
  const placeholder = area ? area.querySelector('[id$="Placeholder"]') : null;
  const reader      = new FileReader();
  reader.onload = e => {
    preview.src = e.target.result;
    preview.classList.remove('d-none');
    if (placeholder) placeholder.style.display = 'none';
  };
  reader.readAsDataURL(file);
}

function previewDocument(input, previewId, areaId) {
  const file = input.files[0];
  if (!file) return;
  const previewDiv  = document.getElementById(previewId);
  const area        = document.getElementById(areaId);
  const placeholder = area ? area.querySelector('[id$="Placeholder"]') : null;
  const nameSpan    = previewDiv ? previewDiv.querySelector('span') : null;
  if (nameSpan)    nameSpan.textContent = file.name;
  if (previewDiv)  previewDiv.classList.remove('d-none');
  if (placeholder) placeholder.style.display = 'none';
}

function resetFileArea(previewId, placeholderId) {
  const preview = document.getElementById(previewId);
  const ph      = document.getElementById(placeholderId);
  if (preview) {
    preview.classList.add('d-none');
    if (preview.tagName === 'IMG') preview.src = '';
  }
  if (ph) ph.style.display = '';
}
