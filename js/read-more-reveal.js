(function () {
  const SELECTOR = '.post-button .btn';
  const SPOT_RADIUS = 60;         // 悬停时光斑半径（px）
  const CLICK_ANIM_DURATION = 1800; // 点击动画时长（ms）

  let ticking = false;
  let lastMouseX = 0, lastMouseY = 0;

  let activeButton = null;
  let animStartTime = 0;
  let animStartRadius = 0;
  let animEndRadius = 0;
  let animFrameId = null;
  let clickHref = null;

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function distanceToRect(px, py, rect) {
    const dx = Math.max(rect.left - px, 0, px - rect.right);
    const dy = Math.max(rect.top - py, 0, py - rect.bottom);
    return Math.sqrt(dx * dx + dy * dy);
  }

  function updateButtonHover(btn, mouseX, mouseY) {
    if (!btn || !btn.isConnected) return;
    if (btn === activeButton) return;

    const rect = btn.getBoundingClientRect();
    const dist = distanceToRect(mouseX, mouseY, rect);

    const px = mouseX - rect.left;
    const py = mouseY - rect.top;

    btn.style.setProperty('--spot-x', px + 'px');
    btn.style.setProperty('--spot-y', py + 'px');

    const percentX = clamp((px / rect.width) * 100, 0, 100);
    const percentY = clamp((py / rect.height) * 100, 0, 100);
    btn.style.setProperty('--mx', percentX + '%');
    btn.style.setProperty('--my', percentY + '%');

    btn.style.setProperty('--mask-radius', SPOT_RADIUS + 'px');

    if (dist <= SPOT_RADIUS) {
      btn.classList.add('is-hover');
    } else {
      btn.classList.remove('is-hover');
    }
  }

  function onDocumentMouseMove(ev) {
    lastMouseX = ev.clientX;
    lastMouseY = ev.clientY;
    if (!ticking) {
      window.requestAnimationFrame(() => {
        document.querySelectorAll(SELECTOR).forEach(btn => {
          updateButtonHover(btn, lastMouseX, lastMouseY);
        });
        ticking = false;
      });
      ticking = true;
    }
  }

  function startClickAnimation(btn, href) {
    if (activeButton) {
      if (animFrameId) cancelAnimationFrame(animFrameId);
      if (clickHref) window.location.href = clickHref;
      activeButton = null;
    }

    activeButton = btn;
    clickHref = href;

    const rect = btn.getBoundingClientRect();
    const px = parseFloat(btn.style.getPropertyValue('--spot-x')) || (rect.width / 2);
    const py = parseFloat(btn.style.getPropertyValue('--spot-y')) || (rect.height / 2);

    const currentRadius = btn.classList.contains('is-hover') ? SPOT_RADIUS : 0;
    const maxRadius = Math.sqrt(rect.width * rect.width + rect.height * rect.height) * 1.5;

    animStartRadius = currentRadius;
    animEndRadius = maxRadius;
    animStartTime = performance.now();

    btn.classList.add('is-clicking');
    btn.classList.remove('is-hover');

    function updateMask(radius) {
      const maskValue = `radial-gradient(circle at ${px}px ${py}px, 
        rgba(0, 0, 0, 0) 0px, 
        rgba(0, 0, 0, 0) calc(${radius}px * 0.3), 
        rgba(0, 0, 0, 0.5) calc(${radius}px * 0.6), 
        rgba(0, 0, 0, 1) ${radius}px)`;
      btn.style.mask = maskValue;
      btn.style.webkitMask = maskValue;
    }

    updateMask(currentRadius);

    function animate(now) {
      const elapsed = now - animStartTime;
      let progress = Math.min(1, elapsed / CLICK_ANIM_DURATION);
      const easeProgress = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      const newRadius = animStartRadius + (animEndRadius - animStartRadius) * easeProgress;

      updateMask(newRadius);

      if (progress < 1) {
        animFrameId = requestAnimationFrame(animate);
      } else {
        btn.style.mask = 'none';
        btn.style.webkitMask = 'none';
        btn.classList.remove('is-clicking');
        activeButton = null;
        animFrameId = null;
        window.location.href = href;
      }
    }

    animFrameId = requestAnimationFrame(animate);
  }

  function bindButton(btn) {
    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';

    const handleClick = (ev) => {
      const href = btn.getAttribute('href');
      if (!href || href.startsWith('javascript:') || href === '#') return;
      if (ev.metaKey || ev.ctrlKey || btn.target === '_blank' || ev.button !== 0) return;
      if (activeButton) return;

      ev.preventDefault();

      const mx = getComputedStyle(btn).getPropertyValue('--mx').trim() || '50%';
      const my = getComputedStyle(btn).getPropertyValue('--my').trim() || '50%';
      btn.style.setProperty('--click-mx', mx);
      btn.style.setProperty('--click-my', my);

      startClickAnimation(btn, href);
    };

    btn.addEventListener('click', handleClick);
  }

  function init() {
    if (!document._mouseMoveBound) {
      document.addEventListener('mousemove', onDocumentMouseMove);
      document._mouseMoveBound = true;
    }
    document.querySelectorAll(SELECTOR).forEach(bindButton);
  }

  document.addEventListener('DOMContentLoaded', init);
  document.addEventListener('pjax:success', init);
})();