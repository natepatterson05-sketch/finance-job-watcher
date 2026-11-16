import {parseCSV, runDay, changes, marketMetrics, filterPostings, daysBetween} from './metrics.mjs';
const $ = selector => document.querySelector(selector);
const count = value => Number(value).toLocaleString();
const DATA_CACHE = 'finance-watcher-data-v1';
const PAIR_URL = new URL('./__last_data_pair', document.baseURI).href;
let installPrompt;
function el(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function notify(text) { $('#notice').textContent = text; }
function safeLink(row) {
  const link = el('a', row.title); let url;
  try { url = new URL(row.url); } catch { return el('span', row.title); }
  if (url.protocol !== 'https:') return el('span', row.title);
  link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; return link;
}
function decode(pair) {
  const status = pair.status, rows = parseCSV(pair.history);
  if (!Array.isArray(status.sources) || !Number.isFinite(status.open) || !status.run_time) throw new Error('Invalid status data');
  runDay(status);
  return {rows, status, cachedAt: pair.cachedAt};
}
async function loadData() {
  try {
    const [historyResponse, statusResponse] = await Promise.all([
      fetch('./data/history.csv', {cache: 'no-store'}), fetch('./data/status.json', {cache: 'no-store'})
    ]);
    if (!historyResponse.ok || !statusResponse.ok) throw new Error('Data request failed');
    const pair = {history: await historyResponse.text(), status: await statusResponse.json(), cachedAt: new Date().toISOString()};
    const decoded = decode(pair);
    try { const cache = await caches.open(DATA_CACHE); await cache.put(PAIR_URL, new Response(JSON.stringify(pair), {headers: {'Content-Type': 'application/json'}})); }
    catch { notify('Live data loaded. This browser could not save it for offline use.'); }
    return {...decoded, offline: false};
  } catch (error) {
    try {
      const cache = await caches.open(DATA_CACHE), response = await cache.match(PAIR_URL);
      if (response) return {...decode(await response.json()), offline: true};
    } catch { /* No valid saved snapshot. */ }
    throw new Error('Data could not be loaded. Connect to the internet and reload to save your first snapshot.');
  }
}
function readShortlist() {
  try { const value = JSON.parse(localStorage.getItem('finance-watcher-shortlist') || '[]'); return new Set(Array.isArray(value) ? value.filter(x => typeof x === 'string') : []); }
  catch { return new Set(); }
}
function star(row, shortlist, onChange) {
  const button = el('button', shortlist.has(row.posting_id) ? '★' : '☆', 'star');
  button.type = 'button'; button.setAttribute('aria-pressed', String(shortlist.has(row.posting_id)));
  button.setAttribute('aria-label', `Save ${row.title} at ${row.employer}`);
  button.addEventListener('click', () => {
    if (shortlist.has(row.posting_id)) shortlist.delete(row.posting_id); else shortlist.add(row.posting_id);
    try { localStorage.setItem('finance-watcher-shortlist', JSON.stringify([...shortlist])); }
    catch { notify('Your browser could not save the shortlist. Changes will last for this visit only.'); }
    onChange();
  }); return button;
}
function postingTable(rows, {shortlist = null, onChange = () => {}, day} = {}) {
  if (!rows.length) return el('p', 'No postings match this view.', 'empty');
  const wrap = el('div', undefined, 'table-wrap'), table = el('table');
  const caption = el('caption', 'Job postings and application links', 'sr-only'); table.append(caption);
  const thead = el('thead'), header = el('tr');
  for (const title of [...(shortlist ? ['Save'] : []), 'Role / apply', 'Employer', 'Location', 'First seen']) { const th = el('th', title); th.scope = 'col'; header.append(th); }
  thead.append(header); table.append(thead); const tbody = el('tbody');
  for (const row of rows) {
    const tr = el('tr');
    if (shortlist) { const td = el('td'); td.append(star(row, shortlist, onChange)); tr.append(td); }
    const title = el('td'); title.append(safeLink(row));
    if (row.in_role === 'true') title.append(el('span', 'Finance', 'tag'));
    if (row.first_run === 'true') title.append(el('span', 'Baseline', 'tag neutral'));
    tr.append(title, el('td', row.employer), el('td', row.location || 'Not provided'));
    const first = el('td', row.first_seen);
    if (day) first.append(el('small', `${daysBetween(row.first_seen, day)} days observed`));
    tr.append(first); tbody.append(tr);
  }
  table.append(tbody); wrap.append(table); return wrap;
}
function today(rows, status) {
  const day = runDay(status), diff = changes(rows, day);
  for (const key of ['days_with_success', 'open', 'new_today', 'removed_today']) $(`[data-count="${key}"]`).textContent = count(status[key]);
  $('#new-list').replaceChildren(postingTable(diff.added, {day}));
  $('#removed-list').replaceChildren(postingTable(diff.removed, {day}));
  $('#new-total').textContent = count(diff.added.length); $('#removed-total').textContent = count(diff.removed.length);
  const sources = $('#sources'); sources.replaceChildren();
  for (const source of status.sources) {
    const item = el('li', undefined, 'source');
    item.append(el('span', source.name), el('span', source.ok ? `${count(source.count)} postings` : 'Fetch failed', source.ok ? 'source-ok' : 'source-failed'));
    sources.append(item);
  }
  $('#source-summary').textContent = `${status.sources.filter(s => s.ok).length} of ${status.sources.length} sources succeeded in the latest attempt`;
}
function browse(rows, status) {
  const day = runDay(status), shortlist = readShortlist(), form = $('#filters');
  for (const [name, key] of [['employer', 'employer'], ['location', 'location']]) {
    const select = form.elements[name];
    const values = [...new Set(rows.filter(r => r.status === 'open').map(r => r[key]).filter(Boolean))].sort();
    for (const value of values) { const option = el('option', value); option.value = value; select.append(option); }
  }
  function render() {
    const filtered = filterPostings(rows, {roleOnly: form.elements.roleOnly.checked,
      employer: form.elements.employer.value, location: form.elements.location.value,
      days: form.elements.days.value, query: form.elements.query.value.trim(), sort: form.elements.sort.value,
      shortlistOnly: form.elements.shortlistOnly.checked}, day, shortlist);
    $('#results-count').textContent = `${count(filtered.length)} open postings`;
    $('#shortlist-count').textContent = `${shortlist.size} saved`;
    $('#browse-list').replaceChildren(postingTable(filtered, {shortlist, onChange: render, day}));
  }
  form.addEventListener('input', render); form.addEventListener('submit', event => event.preventDefault());
  $('#reset-filters').addEventListener('click', () => { form.reset(); render(); }); render();
}
const SVG = 'http://www.w3.org/2000/svg';
function svgNode(tag, attrs = {}, text) {
  const node = document.createElementNS(SVG, tag); for (const [k, value] of Object.entries(attrs)) node.setAttribute(k, value);
  if (text !== undefined) node.textContent = text; return node;
}
function chart(target, entries, series = [{key: 'count', label: 'Postings', color: '#087f72'}]) {
  const host = $(target); host.replaceChildren();
  if (!entries.length || entries.every(e => series.every(s => !e[s.key]))) { host.append(el('p', 'No qualifying observations yet.', 'empty')); return; }
  const labelWidth = 230, plotWidth = 420, rowHeight = series.length > 1 ? 48 : 34;
  const height = 45 + entries.length * rowHeight;
  const svg = svgNode('svg', {viewBox: `0 0 720 ${height}`, role: 'img', 'aria-label': host.dataset.label});
  svg.append(svgNode('title', {}, host.dataset.label));
  const max = Math.max(...entries.flatMap(e => series.map(s => e[s.key])));
  for (let tick = 0; tick <= 4; tick++) {
    const x = labelWidth + tick * plotWidth / 4;
    svg.append(svgNode('line', {x1: x, x2: x, y1: 22, y2: height - 5, stroke: '#e0e8e9'}));
    svg.append(svgNode('text', {x, y: 14, 'text-anchor': 'middle', fill: '#526575', 'font-size': 11}, Number((max * tick / 4).toFixed(1))));
  }
  entries.forEach((entry, index) => {
    const y = 32 + index * rowHeight;
    const text = svgNode('text', {x: labelWidth - 12, y: y + 12, 'text-anchor': 'end', fill: '#263e50', 'font-size': 12}, entry.label.length > 31 ? entry.label.slice(0, 29) + '…' : entry.label);
    text.append(svgNode('title', {}, entry.label)); svg.append(text);
    series.forEach((s, j) => {
      const value = entry[s.key];
      const rect = svgNode('rect', {x: labelWidth, y: y + j * 18, width: value / max * plotWidth, height: 13, rx: 3, fill: s.color});
      rect.append(svgNode('title', {}, `${entry.label}: ${s.label} ${value}`)); svg.append(rect);
      svg.append(svgNode('text', {x: labelWidth + value / max * plotWidth + 6, y: y + j * 18 + 11, fill: '#263e50', 'font-size': 11}, value));
    });
  });
  host.append(svg);
  const legend = el('div', undefined, 'legend');
  for (const s of series) { const label = el('span', s.label); label.style.setProperty('--series-color', s.color); legend.append(label); } host.append(legend);
  const details = el('details'), summary = el('summary', 'View chart data'); details.append(summary);
  const table = el('table'), head = el('tr'); head.append(el('th', 'Category'), ...series.map(s => el('th', s.label))); const thead = el('thead'); thead.append(head); table.append(thead);
  const tbody = el('tbody'); for (const e of entries) { const tr = el('tr'); tr.append(el('td', e.label), ...series.map(s => el('td', e[s.key]))); tbody.append(tr); } table.append(tbody); details.append(table); host.append(details);
}
function market(rows, status) {
  const m = marketMetrics(rows, status), recent = m.daily.at(-1), totalNew = m.daily.reduce((sum, d) => sum + d.all, 0);
  $('#market-asof').textContent = `As of ${m.day} UTC · ${count(rows.length)} unique postings observed`;
  $('#finding-new').textContent = `${count(totalNew)} new postings observed after baseline`;
  $('#explain-new').textContent = `${count(recent?.all || 0)} new postings were first seen on the latest run date. Teal shows all roles; navy shows finance roles. Baseline postings are excluded. Zero bars can also mean no successful observations that day.`;
  chart('#chart-new', m.daily.map(d => ({...d, label: d.date})), [{key: 'all', label: 'All roles', color: '#087f72'}, {key: 'role', label: 'Finance roles', color: '#172e4b'}]);
  const removed = m.daily.reduce((sum, d) => sum + d.removed, 0);
  $('#finding-removed').textContent = `${count(removed)} postings currently recorded as removed`;
  $('#explain-removed').textContent = 'Counts use the removed date in the current history. A failed source cannot cause a removal. Reopened postings have no removed date, so earlier removal episodes are not counted here.';
  chart('#chart-removed', m.daily.map(d => ({label: d.date, count: d.removed})));
  $('#finding-employers').textContent = m.employers.length ? `${m.employers[0].label} leads with ${count(m.employers[0].count)} open postings` : 'No open postings observed';
  $('#explain-employers').textContent = `The full watch list currently has ${count(m.open)} open postings. These counts include all roles and retain the last known state of sources that failed.`;
  chart('#chart-employers', m.employers);
  $('#finding-duration').textContent = m.median === null ? 'Median days open is not available yet' : `Removed postings were observed open for a median of ${m.median} days`;
  $('#explain-duration').textContent = `${count(m.durations.length)} removed, non-baseline postings qualify. Duration is removed date minus first-seen date, measured in UTC days. First-run postings are excluded because their true start dates are unknown.`;
  const bins = [{label:'0–6 days',count:0},{label:'7–13 days',count:0},{label:'14–29 days',count:0},{label:'30+ days',count:0}];
  for (const n of m.durations) bins[n < 7 ? 0 : n < 14 ? 1 : n < 30 ? 2 : 3].count++;
  chart('#chart-duration', bins);
  $('#finding-share').textContent = m.share === null ? 'Seven-day removal share needs more history' : `${(m.share * 100).toFixed(1)}% of eligible postings were removed within seven days`;
  $('#explain-share').textContent = `${count(m.fast)} of ${count(m.eligible)} eligible postings were removed within seven days of first observation. Eligibility excludes baseline postings and requires first-seen at least seven days before ${m.day}. Still-open eligible postings remain in the denominator.`;
  chart('#chart-share', [{label:'Removed within 7 days',count:m.fast},{label:'Other eligible postings',count:m.eligible - m.fast}]);
  $('#finding-locations').textContent = m.locations.length ? `${m.locations[0].label} is the most common open-posting location` : 'No open locations observed';
  $('#explain-locations').textContent = 'The ten most common location labels among all open postings. Labels are kept as supplied by employers; multi-location postings count once under their supplied label.';
  chart('#chart-locations', m.locations.slice(0, 10));
}
async function main() {
  const page = document.body.dataset.page;
  document.querySelector(`[data-nav="${page}"]`)?.setAttribute('aria-current', 'page');
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; $('#install-app').hidden = false; });
  $('#install-app').addEventListener('click', async () => { if (installPrompt) { await installPrompt.prompt(); installPrompt = null; $('#install-app').hidden = true; } });
  try {
    const {rows, status, offline, cachedAt} = await loadData();
    $('#run-time').textContent = `Last run ${status.run_time.replace('T', ' ').replace(/\.\d+Z$/, ' UTC').replace('Z', ' UTC')}`;
    $('#connection').textContent = offline ? 'Saved snapshot' : 'Live data';
    if (offline) notify(`Network unavailable. Showing the last loaded snapshot, saved ${new Date(cachedAt).toLocaleString()}.`);
    if (page === 'today') today(rows, status); else if (page === 'browse') browse(rows, status); else market(rows, status);
    $('#loading').hidden = true; $('#content').hidden = false;
  } catch (error) { $('#loading').textContent = error.message; $('#loading').classList.add('error'); }
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(() => notify('Offline page caching is unavailable. Use HTTPS or localhost for app installation.'));
}
main();
