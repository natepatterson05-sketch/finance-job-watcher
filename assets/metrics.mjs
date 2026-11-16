const DAY = 86400000;
export function dayNumber(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error(`Invalid UTC date: ${value}`);
  const number = Date.parse(`${value}T00:00:00Z`);
  if (!Number.isFinite(number) || new Date(number).toISOString().slice(0, 10) !== value) throw new Error('Invalid date');
  return number / DAY;
}
export function daysBetween(start, end) { return dayNumber(end) - dayNumber(start); }
export function runDay(status) { return new Date(status.run_time).toISOString().slice(0, 10); }

// RFC-style CSV parser: quoted commas, escaped quotes, CRLF, and multiline fields.
export function parseCSV(text) {
  const records = []; let row = [], field = '', quoted = false;
  text = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"' && !field) quoted = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); records.push(row); row = []; field = '';
    } else field += c;
  }
  if (quoted) throw new Error('History has an unfinished CSV field');
  if (field || row.length) { row.push(field); records.push(row); }
  if (!records.length) throw new Error('History CSV is empty');
  const headers = records.shift();
  const expected = 'posting_id,source,source_id,employer,title,location,department,posted_date,url,in_role,first_run,first_seen,last_seen,status,removed_date';
  if (headers.join(',') !== expected) throw new Error('Unexpected history columns');
  return records.filter(r => r.some(Boolean)).map(r => {
    if (r.length !== headers.length) throw new Error('History has an incomplete row');
    return Object.fromEntries(headers.map((h, i) => [h, r[i]]));
  });
}
export function changes(rows, day) {
  return {
    added: rows.filter(r => r.first_seen === day && r.first_run === 'false'),
    removed: rows.filter(r => r.removed_date === day)
  };
}
export function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b), middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}
function groups(rows, key) {
  const map = new Map();
  for (const row of rows) { const label = row[key] || 'Not provided'; map.set(label, (map.get(label) || 0) + 1); }
  return [...map].map(([label, count]) => ({label, count})).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}
export function marketMetrics(rows, status) {
  const day = runDay(status), open = rows.filter(r => r.status === 'open');
  const baselineExcluded = rows.filter(r => r.first_run === 'false');
  const durations = baselineExcluded.filter(r => r.status === 'removed' && r.removed_date)
    .map(r => daysBetween(r.first_seen, r.removed_date)).filter(n => n >= 0);
  const eligible = baselineExcluded.filter(r => daysBetween(r.first_seen, day) >= 7);
  const fast = eligible.filter(r => r.removed_date && daysBetween(r.first_seen, r.removed_date) >= 0 && daysBetween(r.first_seen, r.removed_date) <= 7);
  const daily = [];
  const start = status.first_run_date || day;
  for (let n = dayNumber(start); n <= dayNumber(day); n++) {
    const date = new Date(n * DAY).toISOString().slice(0, 10);
    daily.push({date, all: 0, role: 0, removed: 0});
  }
  const byDate = new Map(daily.map(d => [d.date, d]));
  for (const row of rows) {
    const added = byDate.get(row.first_seen), removed = byDate.get(row.removed_date);
    if (added && row.first_run === 'false') { added.all++; if (row.in_role === 'true') added.role++; }
    if (removed) removed.removed++;
  }
  return {day, daily, employers: groups(open, 'employer'), locations: groups(open, 'location'),
    durations, median: median(durations), eligible: eligible.length, fast: fast.length,
    share: eligible.length ? fast.length / eligible.length : null, open: open.length};
}
export function filterPostings(rows, filters, day, shortlist = new Set()) {
  return rows.filter(r => r.status === 'open')
    .filter(r => !filters.roleOnly || r.in_role === 'true')
    .filter(r => !filters.employer || r.employer === filters.employer)
    .filter(r => !filters.location || r.location === filters.location)
    .filter(r => !filters.query || r.title.toLowerCase().includes(filters.query.toLowerCase()))
    .filter(r => !filters.shortlistOnly || shortlist.has(r.posting_id))
    .filter(r => !filters.days || daysBetween(r.first_seen, day) >= Number(filters.days))
    .sort((a, b) => (filters.sort === 'oldest' ? a.first_seen.localeCompare(b.first_seen) : b.first_seen.localeCompare(a.first_seen)) || a.posting_id.localeCompare(b.posting_id));
}
