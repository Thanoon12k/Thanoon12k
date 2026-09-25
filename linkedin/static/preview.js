// Renders .lipost[data-body] elements the way the post will look on LinkedIn.
(function () {
  const esc = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // Same rule as post.py full_text(): the link goes before a trailing hashtag paragraph.
  function fullText(body, link) {
    body = body.trim(); link = (link || '').trim();
    if (!link) return body;
    const paras = body.split('\n\n'), last = paras[paras.length - 1];
    if (paras.length > 1 && last.split(/\s+/).every(w => w.startsWith('#')))
      return [...paras.slice(0, -1), '🔗 ' + link, last].join('\n\n');
    return body + '\n\n🔗 ' + link;
  }
  function fmt(text) {
    return esc(text).replace(/(^|\s)(#[\p{L}\p{N}_]+)/gu, '$1<span class="ht">$2</span>')
                    .replace(/(https?:\/\/\S+)/g, '<span class="ht">$1</span>');
  }
  function render(el) {
    const d = el.dataset, text = fullText(d.body || '', d.link);
    const lines = text.split('\n');
    let short = lines.slice(0, 3).join('\n');
    if (short.length > 210) short = short.slice(0, 210);
    const cut = short.length < text.length;
    const name = d.name || 'You', initial = esc(name.trim()[0] || '?');
    el.innerHTML =
      `<div class="hd"><div class="av">${d.avatar ? `<img src="${esc(d.avatar)}" alt="">` : initial}</div>
       <div><div class="nm">${esc(name)}</div><div class="hl">${esc(d.headline || '')}</div>
       <div class="hl">${esc(d.when || 'Now')} · 🌐</div></div></div>
       <div class="tx">${text ? fmt(cut ? short : text) + (cut ? '<span class="more">…see more</span>' : '') : '<span style="color:#999">Your post text appears here…</span>'}</div>
       ${d.img ? `<div class="im"><img src="${esc(d.img)}" alt=""></div>` : ''}
       <div class="ft"><span>👍 Like</span><span>💬 Comment</span><span>🔁 Repost</span><span>➤ Send</span></div>`;
    const more = el.querySelector('.more');
    if (more) more.onclick = () => { el.querySelector('.tx').innerHTML = fmt(text); };
  }
  window.renderLiPost = render;
  document.querySelectorAll('.lipost[data-body]').forEach(render);
})();
