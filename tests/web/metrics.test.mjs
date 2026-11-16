import {parseCSV, daysBetween, runDay, median, changes, marketMetrics, filterPostings} from '../../assets/metrics.mjs';
export function runTests() {
  let passed = 0;
  const eq = (actual, expected, message) => { if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(`${message}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`); passed++; };
  const row = (posting_id, options = {}) => ({posting_id, first_seen:'2026-01-01', last_seen:'2026-01-10', first_run:'false', in_role:'true', status:'open', removed_date:'', employer:'A', location:'Chicago', title:'Financial Analyst', ...options});
  const status = {run_time:'2026-01-10T00:01:00Z', first_run_date:'2026-01-01'};
  const rows = [
    row('baseline', {first_run:'true'}),
    row('fast', {status:'removed', removed_date:'2026-01-08'}),
    row('slow', {status:'removed', removed_date:'2026-01-10', in_role:'false'}),
    row('still-open'),
    row('recent', {first_seen:'2026-01-09', employer:'B'}),
    row('today', {first_seen:'2026-01-10', in_role:'false', title:'Engineer', location:'New York'})
  ];
  eq(daysBetween('2026-03-07','2026-03-09'),2,'UTC dates ignore daylight savings');
  eq(runDay({run_time:'2026-01-09T23:30:00-06:00'}),'2026-01-10','Run day uses UTC');
  eq(median([9,1,7,3]),5,'Even median'); eq(median([9,1,3]),3,'Odd median'); eq(median([]),null,'No median');
  const m = marketMetrics(rows,status);
  eq(m.daily.length,10,'Includes zero-observation calendar days');
  eq(m.daily[0].all,3,'Baseline excluded from first observations');
  eq(m.daily[0].role,2,'Role series calculated independently');
  eq(m.daily[7].removed,1,'Removals grouped by removed date');
  eq(m.open,4,'Open total'); eq(m.employers[0],{label:'A',count:3},'Open employer distribution');
  eq(m.locations[0],{label:'Chicago',count:3},'Open locations');
  eq(m.median,8,'Removed durations omit baseline');
  eq(m.eligible,3,'Seven-day eligibility excludes baseline and recent');
  eq(m.fast,1,'Exactly seven days qualifies'); eq(m.share,1/3,'Open eligible jobs remain denominator');
  eq(changes(rows,'2026-01-10').added.map(r=>r.posting_id),['today'],'Latest date new arrivals');
  eq(changes(rows,'2026-01-01').added.length,3,'Baseline not new');
  eq(filterPostings(rows,{roleOnly:true,employer:'A',days:'7',sort:'oldest'},'2026-01-10').map(r=>r.posting_id),['baseline','still-open'],'Role employer days filters');
  eq(filterPostings(rows,{query:'engineer'},'2026-01-10').map(r=>r.posting_id),['today'],'Case insensitive title search');
  eq(filterPostings(rows,{location:'Chicago',shortlistOnly:true},'2026-01-10',new Set(['recent','slow'])).map(r=>r.posting_id),['recent'],'Shortlist excludes removed roles');
  eq(filterPostings(rows,{sort:'oldest'},'2026-01-10')[0].first_seen,'2026-01-01','Oldest order');
  const empty = marketMetrics([],{...status,first_run_date:null});
  eq(empty.share,null,'Empty denominator'); eq(empty.median,null,'Empty duration');
  const header = 'posting_id,source,source_id,employer,title,location,department,posted_date,url,in_role,first_run,first_seen,last_seen,status,removed_date';
  const csv = header + '\r\nx,s,1,Employer,"Analyst, ""Senior""","Chicago\nRemote",,,https://example.com,true,false,2026-01-01,2026-01-10,open,\r\n';
  const parsed = parseCSV('\uFEFF'+csv);
  eq(parsed.length,1,'CSV one row'); eq(parsed[0].title,'Analyst, "Senior"','CSV quoted commas and escaped quotes');
  eq(parsed[0].location,'Chicago\nRemote','CSV multiline field'); eq(parsed[0].removed_date,'','CSV trailing empty cell');
  let rejected = false; try { parseCSV(header+'\nx,s'); } catch { rejected=true; } eq(rejected,true,'Reject incomplete rows');
  rejected=false; try { daysBetween('2026-02-30','2026-03-01'); } catch { rejected=true; } eq(rejected,true,'Reject impossible dates');
  return passed;
}
if (typeof process !== 'undefined' && process.versions?.node) console.log(`${runTests()} browser-metric assertions passed`);
