// QuickHire Interactive JavaScript Helper & Ultra-Fast Live Sync Engine

// Safe cross-platform date parser for Mobile Safari, Chrome & Desktop
function parseSafeDate(dateStr) {
  if (!dateStr) return null;
  if (dateStr instanceof Date) return dateStr;
  
  try {
    const clean = String(dateStr).trim().replace('T', ' ');
    const parts = clean.split(' ');
    if (parts.length >= 2) {
      const dateParts = parts[0].split('-').map(Number);
      const timeParts = parts[1].split(':').map(Number);
      if (dateParts.length === 3) {
        return new Date(
          dateParts[0],
          dateParts[1] - 1,
          dateParts[2],
          timeParts[0] || 0,
          timeParts[1] || 0,
          timeParts[2] || 0
        );
      }
    }
  } catch (e) {
    console.error("Date parse error", e);
  }

  const d = new Date(dateStr);
  return isNaN(d.getTime()) ? null : d;
}

// 1. Live Job Digital Stopwatch with Auto-Stop on Target Completion (Worker View)
window.initLiveJobTimer = function(startTimeStr, prefix = 'worker', maxScheduledSecs = null) {
  const startDate = parseSafeDate(startTimeStr);
  if (!startDate) return;

  const hoursEl = document.getElementById(`${prefix}_timer_hrs`);
  const minsEl = document.getElementById(`${prefix}_timer_mins`);
  const secsEl = document.getElementById(`${prefix}_timer_secs`);
  const elapsedTextEl = document.getElementById(`${prefix}_elapsed_text`);
  const progressBarEl = document.getElementById(`${prefix}_timer_progress`);
  const finishBtnText = document.getElementById('finishBtnText');

  let intervalId = null;

  function tick() {
    const now = new Date();
    const realDiffSecs = Math.max(0, Math.floor((now.getTime() - startDate.getTime()) / 1000));
    const scheduledSecs = parseFloat(maxScheduledSecs || (progressBarEl ? progressBarEl.dataset.scheduledSeconds : null) || 10800);

    // Stop timer when scheduled duration is reached
    const isCompleted = realDiffSecs >= scheduledSecs;
    const displayDiffSecs = isCompleted ? scheduledSecs : realDiffSecs;

    const h = Math.floor(displayDiffSecs / 3600);
    const m = Math.floor((displayDiffSecs % 3600) / 60);
    const s = displayDiffSecs % 60;

    if (hoursEl) hoursEl.textContent = String(h).padStart(2, '0');
    if (minsEl) minsEl.textContent = String(m).padStart(2, '0');
    if (secsEl) secsEl.textContent = String(s).padStart(2, '0');

    if (progressBarEl) {
      const pct = Math.min(100, Math.round((displayDiffSecs / scheduledSecs) * 100));
      progressBarEl.style.width = `${pct}%`;
      progressBarEl.setAttribute('aria-valuenow', pct);
    }

    if (isCompleted) {
      if (elapsedTextEl) {
        elapsedTextEl.innerHTML = `<span class="badge bg-success text-white px-2 py-1 fs-6 shadow-sm"><i class="bi bi-check-circle-fill me-1"></i> Shift Target Completed! 100% Full Pay Earned</span>`;
      }
      if (progressBarEl) {
        progressBarEl.className = 'progress-bar bg-success';
      }
      if (finishBtnText) {
        finishBtnText.innerHTML = `<i class="bi bi-check2-circle me-1"></i> Claim 100% Payout &amp; Submit Completion`;
      }
      // Stop ticking once target is complete
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    } else {
      let timeText = '';
      if (displayDiffSecs < 60) {
        timeText = `${displayDiffSecs}s worked`;
      } else if (displayDiffSecs < 3600) {
        timeText = `${m}m ${s}s worked`;
      } else {
        timeText = `${(displayDiffSecs / 3600).toFixed(2)} hrs worked`;
      }

      const remainSecs = scheduledSecs - displayDiffSecs;
      const remMins = Math.ceil(remainSecs / 60);
      if (elapsedTextEl) {
        elapsedTextEl.innerHTML = `<i class="bi bi-stopwatch me-1 text-success"></i> <strong>${timeText}</strong> <span class="text-white-50">(${remMins}m remaining to full pay)</span>`;
      }
    }
  }

  tick();
  intervalId = setInterval(tick, 1000);
};

// 2. Live Notification Banner Timer & Employer Worker Stopwatch (With strict scheduled cap)
window.initBannerTimer = function(startTimeStr, elementId = 'global_banner_timer', maxScheduledSecs = null, endTimeStr = null) {
  const startDate = parseSafeDate(startTimeStr);
  const targetEl = document.getElementById(elementId);
  if (!startDate || !targetEl) return;

  // If already ended, show fixed static time and DO NOT tick
  if (endTimeStr) {
    const endDate = parseSafeDate(endTimeStr);
    if (endDate) {
      const fixedDiff = Math.max(0, Math.floor((endDate.getTime() - startDate.getTime()) / 1000));
      const h = Math.floor(fixedDiff / 3600);
      const m = Math.floor((fixedDiff % 3600) / 60);
      const s = fixedDiff % 60;
      targetEl.textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')} (Completed)`;
      return;
    }
  }

  let intervalId = null;

  function tickBanner() {
    const now = new Date();
    const realDiffSecs = Math.max(0, Math.floor((now.getTime() - startDate.getTime()) / 1000));
    
    // Strict duration cap if maxScheduledSecs is set
    const scheduledSecs = maxScheduledSecs ? parseFloat(maxScheduledSecs) : null;
    const isOver = scheduledSecs && realDiffSecs >= scheduledSecs;
    const displayDiffSecs = isOver ? scheduledSecs : realDiffSecs;

    const h = Math.floor(displayDiffSecs / 3600);
    const m = Math.floor((displayDiffSecs % 3600) / 60);
    const s = displayDiffSecs % 60;

    const formatted = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    targetEl.textContent = isOver ? `${formatted} (Target Reached)` : formatted;

    if (isOver && intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  tickBanner();
  intervalId = setInterval(tickBanner, 1000);
};

// 3. Ultra-Fast Sub-Second Live Sync (800ms) for Instant Multi-Device Reactivity
window.startLiveSync = function(jobId, initialAssignStatus, initialJobStatus, initialApplicantsCount) {
  if (!jobId) return;

  let lastAssignStatus = initialAssignStatus || null;
  let lastJobStatus = initialJobStatus || null;
  let lastApplicantsCount = initialApplicantsCount !== undefined ? initialApplicantsCount : null;

  setInterval(async () => {
    try {
      const res = await fetch(`/api/job-status/${jobId}`, { 
        cache: 'no-store',
        headers: { 'Accept': 'application/json' } 
      });
      if (!res.ok) return;
      const data = await res.json();

      let needsReload = false;

      if (lastAssignStatus !== null && data.user_assignment_status !== lastAssignStatus) {
        needsReload = true;
      } else if (lastJobStatus !== null && data.job_status !== lastJobStatus) {
        needsReload = true;
      } else if (lastApplicantsCount !== null && data.applicants_count !== lastApplicantsCount) {
        needsReload = true;
      }

      if (needsReload) {
        // Immediate instant UI refresh across devices
        window.location.reload();
      }
    } catch (e) {
      // Ignore transient network glitches
    }
  }, 800); // 800ms ultra-fast polling for instant reaction!
};

// 7. Toggle Password Visibility Eye Function
window.togglePasswordVisibility = function(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPass = (input.type === 'password');
  input.type = isPass ? 'text' : 'password';
  if (btnEl) {
    const icon = btnEl.querySelector('i');
    if (icon) {
      icon.className = isPass ? 'bi bi-eye-slash' : 'bi bi-eye';
    }
  }
};

// DOM Content Loaded Handler
document.addEventListener('DOMContentLoaded', () => {
  // Initialize Bootstrap tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

  // Auto-calculate total escrow on Post Job form
  const paymentInput = document.getElementById('payment');
  const workersInput = document.getElementById('required_workers');
  const escrowDisplay = document.getElementById('totalEscrowDisplay');
  const walletWarning = document.getElementById('walletWarning');

  function updateEscrowMath() {
    if (!paymentInput || !workersInput || !escrowDisplay) return;
    const pay = parseFloat(paymentInput.value) || 0;
    const workers = parseInt(workersInput.value) || 1;
    const total = pay * workers;
    escrowDisplay.textContent = `₹${total.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    const userWallet = parseFloat(escrowDisplay.dataset.walletBalance || 0);
    if (walletWarning) {
      if (total > userWallet) {
        walletWarning.classList.remove('d-none');
      } else {
        walletWarning.classList.add('d-none');
      }
    }
  }

  if (paymentInput && workersInput) {
    paymentInput.addEventListener('input', updateEscrowMath);
    workersInput.addEventListener('input', updateEscrowMath);
    updateEscrowMath();
  }

  // Auto-detect and initialize any banner timer
  const bannerTimerEl = document.getElementById('global_banner_timer');
  if (bannerTimerEl && bannerTimerEl.dataset.startTime) {
    window.initBannerTimer(bannerTimerEl.dataset.startTime, 'global_banner_timer');
  }

  // Auto-detect and initialize job details timer
  const workerTimerHrs = document.getElementById('worker_timer_hrs');
  if (workerTimerHrs && workerTimerHrs.dataset.startTime) {
    window.initLiveJobTimer(workerTimerHrs.dataset.startTime, 'worker');
  }
});
