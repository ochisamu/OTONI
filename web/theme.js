(() => {
  const media = matchMedia('(prefers-color-scheme: dark)');
  let preference = 'system';
  try { const saved = localStorage.getItem('music-room-theme'); if (['system','light','dark'].includes(saved)) preference = saved; } catch {}
  function apply() { document.documentElement.dataset.theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference; }
  apply();
  media.addEventListener('change', apply);
  document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('themeSelect');
    select.value = preference;
    select.addEventListener('change', () => { preference = select.value; try { localStorage.setItem('music-room-theme', preference); } catch {} apply(); });
  });
})();
