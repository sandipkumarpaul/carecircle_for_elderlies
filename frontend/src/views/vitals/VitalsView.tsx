import React from 'react';
import { Alert, Box, Button, Chip, Divider, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { api } from '../../lib/api';
import { Page, Patient } from '../../lib/types';

// CC-12 (Saif): log vitals, set per-patient limits and show the documented trend rule.
// All rules (ranges, thresholds, trend, alerts) are enforced by the backend; this view only presents them.
type Kind = 'bp' | 'sugar' | 'weight' | 'spo2';
type Status = 'in_range' | 'out_of_range' | 'no_threshold';
type Reading = { id: string; kind: Kind; unit: string; value: string; secondary_value: string | null; observed_at: string; recorded_by_name: string; threshold_status: Status };
type Saved = Reading & { alerts_raised: { type: string; alert_id: string }[] };
type TrendRuleView = { unit: string; min_readings: number; window_days: number; min_change: string };
type Threshold = { id: string; kind: Kind; unit: string; lower: string | null; upper: string | null; secondary_lower: string | null; secondary_upper: string | null; effective_trend: TrendRuleView };
type Trend = { kind: Kind; status: 'no_readings' | 'insufficient_readings' | 'no_trend' | 'worsening'; readings_in_window?: number; rule: TrendRuleView; detail?: { direction: 'up' | 'down'; change: string } | null };
type Defaults = Record<string, { unit: string; lower?: number; upper?: number; secondary_lower?: number; secondary_upper?: number }>;

const kinds: Kind[] = ['bp', 'sugar', 'weight', 'spo2'];
const names: Record<Kind, string> = { bp: 'Blood pressure', sugar: 'Blood sugar', weight: 'Weight', spo2: 'Oxygen (SpO2)' };
const units: Record<Kind, string[]> = { bp: ['mmHg'], sugar: ['mg/dL', 'mmol/L'], weight: ['kg'], spo2: ['%'] };
const statusChip: Record<Status, { label: string; color: 'success' | 'error' | 'default' }> = {
  in_range: { label: 'Within your limits', color: 'success' },
  out_of_range: { label: 'Outside your limits', color: 'error' },
  no_threshold: { label: 'No limits set', color: 'default' },
};
const alertNames: Record<string, string> = { vital_threshold: 'limit', vital_trend: 'trend' };
const blank = { lower: '', upper: '', secondary_lower: '', secondary_upper: '', min_readings: '3', window_days: '14', min_change: '' };

function show(reading: { value: string; secondary_value: string | null; unit: string }) {
  const trim = (n: string) => String(Number(n));
  return reading.secondary_value ? `${trim(reading.value)}/${trim(reading.secondary_value)} ${reading.unit}` : `${trim(reading.value)} ${reading.unit}`;
}

export function VitalsView({ patient }: { patient: Patient | null }) {
  const canRead = !!patient?.scopes.some(s => s === 'vitals:read' || s === 'vitals:write');
  const canWrite = !!patient?.scopes.includes('vitals:write');
  const path = `/patients/${patient?.id}`;
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState(''); const [notice, setNotice] = React.useState('');
  const [page, setPage] = React.useState<Page<Reading>>({ items: [], total: 0, offset: 0, limit: 10 }); const [filter, setFilter] = React.useState<'' | Kind>('');
  const [trends, setTrends] = React.useState<Trend[]>([]); const [thresholds, setThresholds] = React.useState<Threshold[]>([]);
  const [defaults, setDefaults] = React.useState<Defaults>({}); const [disclaimer, setDisclaimer] = React.useState('');
  // reading form
  const [kind, setKind] = React.useState<Kind>('bp'); const [unit, setUnit] = React.useState('mmHg');
  const [value, setValue] = React.useState(''); const [second, setSecond] = React.useState(''); const [when, setWhen] = React.useState('');
  // threshold form
  const [tKind, setTKind] = React.useState<Kind>('bp'); const [tUnit, setTUnit] = React.useState('mmHg'); const [t, setT] = React.useState(blank);

  async function act(work: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await work(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function loadReadings(offset = 0, only: '' | Kind = filter) {
    const params = new URLSearchParams({ offset: String(offset), limit: '10' }); if (only) params.set('kind', only);
    setPage(await api<Page<Reading>>(`${path}/vitals?${params}`));
  }
  async function loadAll() {
    if (!canRead) return;
    const [, tr, th] = await Promise.all([loadReadings(0), api<{ items: Trend[] }>(`${path}/vitals/trends`),
      api<{ items: Threshold[]; demo_defaults: Defaults; notice: string }>(`${path}/vital-thresholds`)]);
    setTrends(tr.items); setThresholds(th.items); setDefaults(th.demo_defaults); setDisclaimer(th.notice);
  }
  React.useEffect(() => { void act(loadAll); }, []);

  function chooseKind(next: Kind) { setKind(next); setUnit(units[next][0]); setValue(''); setSecond(''); }
  function chooseThresholdKind(next: Kind) { setTKind(next); setTUnit(units[next][0]); setT(blank); }

  async function saveReading(event: React.FormEvent) {
    event.preventDefault();
    await act(async () => {
      const body: Record<string, unknown> = { kind, unit, value };
      if (kind === 'bp') body.secondary_value = second;
      if (when) body.observed_at = new Date(when).toISOString();
      const saved = await api<Saved>(`${path}/vitals`, { method: 'POST', body: JSON.stringify(body) });
      const raised = saved.alerts_raised.map(a => alertNames[a.type] ?? a.type);
      setNotice(raised.length ? `Reading saved. A ${raised.join(' and ')} alert was raised for the care circle.` : 'Reading saved.');
      setValue(''); setSecond(''); setWhen('');
      await loadAll();
    });
  }
  function editThreshold(row: Threshold) {
    setTKind(row.kind); setTUnit(row.unit);
    setT({ lower: row.lower ?? '', upper: row.upper ?? '', secondary_lower: row.secondary_lower ?? '', secondary_upper: row.secondary_upper ?? '',
      min_readings: String(row.effective_trend.min_readings), window_days: String(row.effective_trend.window_days), min_change: row.effective_trend.min_change });
  }
  function loadDemo() {
    const d = defaults[tKind]; if (!d) return;
    setTUnit(d.unit);
    setT({ ...blank, lower: d.lower?.toString() ?? '', upper: d.upper?.toString() ?? '', secondary_lower: d.secondary_lower?.toString() ?? '', secondary_upper: d.secondary_upper?.toString() ?? '' });
  }
  async function saveThreshold(event: React.FormEvent) {
    event.preventDefault();
    await act(async () => {
      const orNull = (v: string) => (v.trim() === '' ? null : v.trim());
      const body: Record<string, unknown> = { unit: tUnit, lower: orNull(t.lower), upper: orNull(t.upper) };
      if (tKind === 'bp') { body.secondary_lower = orNull(t.secondary_lower); body.secondary_upper = orNull(t.secondary_upper); }
      if (t.min_change.trim() !== '') body.trend = { min_readings: Number(t.min_readings), window_days: Number(t.window_days), min_change: t.min_change.trim() };
      await api(`${path}/vital-thresholds/${tKind}`, { method: 'PUT', body: JSON.stringify(body) });
      setNotice(`Limits for ${names[tKind].toLowerCase()} saved.`);
      await loadAll();
    });
  }
  async function removeThreshold(row: Threshold) {
    await act(async () => { await api(`${path}/vital-thresholds/${row.kind}`, { method: 'DELETE' }); setNotice('Limits removed.'); await loadAll(); });
  }
  function trendText(tr: Trend) {
    const rule = `${tr.rule.min_readings} readings within ${tr.rule.window_days} days, changing by at least ${Number(tr.rule.min_change)} ${tr.rule.unit}`;
    if (tr.status === 'no_readings') return 'No readings yet.';
    if (tr.status === 'insufficient_readings') return `Not enough readings yet (${tr.readings_in_window} in the last ${tr.rule.window_days} days; ${tr.rule.min_readings} needed).`;
    if (tr.status === 'worsening') return `Worsening trend: ${tr.detail?.direction === 'up' ? 'rose' : 'fell'} by ${Number(tr.detail?.change)} ${tr.rule.unit} across the last ${tr.rule.min_readings} readings.`;
    return `No worsening trend. Rule: ${rule}.`;
  }
  const when_ = (iso: string) => new Date(iso).toLocaleString(undefined, { timeZone: patient?.timezone, dateStyle: 'medium', timeStyle: 'short' });

  return <Stack spacing={3}>
    <Typography variant="h5" component="h2">Vitals &amp; trend alerts</Typography>
    <Alert severity="info">Record measurements and set limits for this patient. Limits and the trend rule are demonstration settings for this course project, not medical advice or a diagnosis. Ask the patient’s clinician which limits apply.</Alert>
    {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}{notice && <Alert severity="success" onClose={() => setNotice('')}>{notice}</Alert>}
    {!patient ? <Alert severity="info">Choose a patient profile to see vitals.</Alert> : !canRead ? <Alert severity="warning">Your care-circle access does not include viewing vitals for this patient.</Alert> : <>
      {canWrite ? <Paper variant="outlined" sx={{ p: 3 }}><form onSubmit={saveReading}><Stack spacing={2}>
        <Typography variant="h6" component="h3">Add a reading</Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField select label="Measurement" value={kind} onChange={e => chooseKind(e.target.value as Kind)} sx={{ minWidth: 200 }}>{kinds.map(k => <MenuItem key={k} value={k}>{names[k]}</MenuItem>)}</TextField>
          <TextField select label="Unit" value={unit} onChange={e => setUnit(e.target.value)} sx={{ minWidth: 120 }}>{units[kind].map(u => <MenuItem key={u} value={u}>{u}</MenuItem>)}</TextField>
          <TextField required label={kind === 'bp' ? 'Systolic (top number)' : 'Value'} value={value} onChange={e => setValue(e.target.value)} slotProps={{ htmlInput: { inputMode: 'decimal' } }} />
          {kind === 'bp' && <TextField required label="Diastolic (bottom number)" value={second} onChange={e => setSecond(e.target.value)} slotProps={{ htmlInput: { inputMode: 'decimal' } }} />}
        </Stack>
        <TextField type="datetime-local" label="Measured at (leave empty for now)" value={when} onChange={e => setWhen(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} helperText={`Uses your device’s clock. Not in the future and not older than 30 days. Times below are shown in ${patient.timezone}.`} sx={{ maxWidth: 420 }} />
        <Box><Button type="submit" variant="contained" disabled={busy || !value}>Save reading</Button></Box>
      </Stack></form></Paper> : <Alert severity="info">You can view vitals but not add readings or change limits.</Alert>}

      <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={1.5}>
        <Typography variant="h6" component="h3">Trends</Typography>
        <Typography variant="body2" color="text.secondary">A worsening trend needs several readings that keep moving in the worsening direction by at least the stated amount. It is a simple fixed rule, not a prediction.</Typography>
        {trends.map(tr => <Stack key={tr.kind} direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ sm: 'center' }}>
          <Typography sx={{ minWidth: 160 }} fontWeight={600}>{names[tr.kind]}</Typography>
          <Chip size="small" label={tr.status === 'worsening' ? 'Worsening' : tr.status === 'no_readings' ? 'No data' : tr.status === 'insufficient_readings' ? 'Need more readings' : 'Stable'} color={tr.status === 'worsening' ? 'warning' : 'default'} />
          <Typography variant="body2">{trendText(tr)}</Typography></Stack>)}
      </Stack></Paper>

      <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={2}>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={2}>
          <Typography variant="h6" component="h3">Readings ({page.total})</Typography>
          <TextField select size="small" label="Show" value={filter} onChange={e => { const f = e.target.value as '' | Kind; setFilter(f); void act(() => loadReadings(0, f)); }} sx={{ minWidth: 200 }}>
            <MenuItem value="">All measurements</MenuItem>{kinds.map(k => <MenuItem key={k} value={k}>{names[k]}</MenuItem>)}</TextField>
        </Stack>
        {page.items.length === 0 && <Typography color="text.secondary">No readings recorded yet.</Typography>}
        {page.items.map(r => <Box key={r.id}><Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between" alignItems={{ sm: 'center' }}>
          <Box><Typography fontWeight={600}>{names[r.kind]}: {show(r)}</Typography><Typography variant="body2" color="text.secondary">{when_(r.observed_at)} · recorded by {r.recorded_by_name}</Typography></Box>
          <Chip size="small" label={statusChip[r.threshold_status].label} color={statusChip[r.threshold_status].color} /></Stack><Divider sx={{ mt: 1 }} /></Box>)}
        {page.total > page.limit && <Stack direction="row" spacing={2} alignItems="center">
          <Button disabled={busy || !page.offset} onClick={() => void act(() => loadReadings(page.offset - page.limit))}>Previous</Button>
          <Typography>{page.offset + 1}–{Math.min(page.offset + page.limit, page.total)} of {page.total}</Typography>
          <Button disabled={busy || page.offset + page.limit >= page.total} onClick={() => void act(() => loadReadings(page.offset + page.limit))}>Next</Button></Stack>}
      </Stack></Paper>

      <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={2}>
        <Typography variant="h6" component="h3">Limits for this patient</Typography>
        {thresholds.length === 0 && <Typography color="text.secondary">No limits set. Readings are saved but are not compared with any limit.</Typography>}
        {thresholds.map(row => <Stack key={row.id} direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between" alignItems={{ sm: 'center' }}>
          <Typography>{names[row.kind]} ({row.unit}): {[row.lower && `at least ${Number(row.lower)}`, row.upper && `at most ${Number(row.upper)}`, row.secondary_lower && `diastolic at least ${Number(row.secondary_lower)}`, row.secondary_upper && `diastolic at most ${Number(row.secondary_upper)}`].filter(Boolean).join(', ') || 'trend rule only'}</Typography>
          {canWrite && <Stack direction="row" spacing={1}><Button size="small" onClick={() => editThreshold(row)}>Edit</Button><Button size="small" color="error" disabled={busy} onClick={() => void removeThreshold(row)}>Remove</Button></Stack>}</Stack>)}
        {canWrite && <form onSubmit={saveThreshold}><Stack spacing={2}>
          <Divider />
          <Typography variant="subtitle1" component="h4">Set limits</Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField select label="Measurement for limits" value={tKind} onChange={e => chooseThresholdKind(e.target.value as Kind)} sx={{ minWidth: 220 }}>{kinds.map(k => <MenuItem key={k} value={k}>{names[k]}</MenuItem>)}</TextField>
            <TextField select label="Limit unit" value={tUnit} onChange={e => setTUnit(e.target.value)} sx={{ minWidth: 120 }}>{units[tKind].map(u => <MenuItem key={u} value={u}>{u}</MenuItem>)}</TextField>
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField label={tKind === 'bp' ? 'Systolic at least' : 'At least'} value={t.lower} onChange={e => setT({ ...t, lower: e.target.value })} />
            <TextField label={tKind === 'bp' ? 'Systolic at most' : 'At most'} value={t.upper} onChange={e => setT({ ...t, upper: e.target.value })} />
            {tKind === 'bp' && <><TextField label="Diastolic at least" value={t.secondary_lower} onChange={e => setT({ ...t, secondary_lower: e.target.value })} />
              <TextField label="Diastolic at most" value={t.secondary_upper} onChange={e => setT({ ...t, secondary_upper: e.target.value })} /></>}
          </Stack>
          <Typography variant="body2" color="text.secondary">Optional trend rule. Leave “Change of at least” empty to use the standard rule (3 readings within 14 days, standard minimum change).</Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField label="Readings needed" type="number" value={t.min_readings} onChange={e => setT({ ...t, min_readings: e.target.value })} slotProps={{ htmlInput: { min: 3, max: 10 } }} />
            <TextField label="Within days" type="number" value={t.window_days} onChange={e => setT({ ...t, window_days: e.target.value })} slotProps={{ htmlInput: { min: 1, max: 60 } }} />
            <TextField label={`Change of at least (${tUnit})`} value={t.min_change} onChange={e => setT({ ...t, min_change: e.target.value })} />
          </Stack>
          {disclaimer && <Typography variant="body2" color="text.secondary">{disclaimer}</Typography>}
          <Stack direction="row" spacing={2}><Button type="submit" variant="contained" disabled={busy}>Save limits</Button><Button disabled={busy || !defaults[tKind]} onClick={loadDemo}>Fill demonstration values</Button></Stack>
        </Stack></form>}
      </Stack></Paper>
    </>}
  </Stack>;
}
