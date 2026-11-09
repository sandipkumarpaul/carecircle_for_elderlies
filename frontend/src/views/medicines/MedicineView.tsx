import React from 'react';
import { Alert, Box, Button, Checkbox, Divider, FormControlLabel, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { api } from '../../lib/api';
import { Page, Patient, User } from '../../lib/types';
import { DoseSchedule } from './DoseSchedule';

type Medicine = { id: string; brand_name: string; generic_name: string; strength: string; form: string; source_name: string; source_license: string };
type Item = { medicine_id: string; quantity_per_dose: string; unit: string; start_date: string; end_date: string | null; schedule_kind: string; times_local: string[]; timezone: string; meal_relation: string; instructions: string | null };
type Saved = Item & { id: string; medicine: Medicine; schedule_status: string };
type Warning = { id: string; kind: string; severity: string; message: string; source: string };
type Review = { check_id: string; warnings: Warning[]; coverage: string };
type Rule = { id: string; severity: string; explanation: string; source: string };
const units: Record<string, string> = { tablet: 'tablet', capsule: 'capsule', liquid: 'ml', drops: 'drop', inhaler: 'puff', injection: 'unit', cream: 'unit' };

export function MedicineView({ patient, user }: { patient: Patient | null; user: User }) {
  const canRead = !!patient?.scopes.some(s => s === 'medicines:read' || s === 'medicines:write');
  const canWrite = !!patient?.scopes.includes('medicines:write');
  const path = `/patients/${patient?.id}`;
  const [q, setQ] = React.useState(''); const [strength, setStrength] = React.useState(''); const [form, setForm] = React.useState('');
  const [generic, setGeneric] = React.useState('');
  const [page, setPage] = React.useState<Page<Medicine>>({ items: [], total: 0, offset: 0, limit: 20 });
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState(''); const [notice, setNotice] = React.useState('');
  const [allergies, setAllergies] = React.useState(''); const [saved, setSaved] = React.useState<Saved[]>([]);
  const [chosen, setChosen] = React.useState<Medicine | null>(null);
  const [quantity, setQuantity] = React.useState('1'); const [start, setStart] = React.useState(''); const [end, setEnd] = React.useState('');
  const [kind, setKind] = React.useState('fixed_times'); const [times, setTimes] = React.useState('08:00');
  const [meal, setMeal] = React.useState('none'); const [instructions, setInstructions] = React.useState('');
  const [draft, setDraft] = React.useState<{ item: Item; medicine: Medicine }[]>([]);
  const [review, setReview] = React.useState<Review | null>(null); const [ack, setAck] = React.useState<string[]>([]);
  const [csv, setCsv] = React.useState(''); const [importResult, setImportResult] = React.useState('');
  const [rules, setRules] = React.useState<Rule[]>([]); const [ruleA, setRuleA] = React.useState<Medicine | null>(null); const [ruleB, setRuleB] = React.useState<Medicine | null>(null);
  const [severity, setSeverity] = React.useState('warning'); const [explanation, setExplanation] = React.useState(''); const [source, setSource] = React.useState('');
  const invalidate = () => { setReview(null); setAck([]); };
  async function act(work: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await work(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function search(offset = 0, query = q, dose = strength, shape = form, exactGeneric = generic) {
    const params = new URLSearchParams({ q: query, generic: exactGeneric, strength: dose, form: shape, offset: String(offset), limit: '20' });
    setPage(await api<Page<Medicine>>(`/medicines?${params}`));
  }
  async function loadPatient() {
    if (!canRead) return;
    const [a, p] = await Promise.all([api<{ generic_names: string[] }>(`${path}/allergies`), api<{ items: Saved[] }>(`${path}/prescriptions`)]);
    setAllergies(a.generic_names.join('\n')); setSaved(p.items);
  }
  React.useEffect(() => { void act(async () => { await search(); setRules((await api<{ items: Rule[] }>('/medicines/interaction-rules')).items); await loadPatient(); }); }, []);
  function addItem() {
    if (!chosen || !patient || !start || Number(quantity) <= 0) { setError('Choose a medicine, positive quantity and start date.'); return; }
    if (draft.length >= 20) { setError('Maximum 20 proposed items per review.'); return; }
    const item: Item = { medicine_id: chosen.id, quantity_per_dose: quantity, unit: units[chosen.form], start_date: start, end_date: end || null,
      schedule_kind: kind, times_local: kind === 'fixed_times' ? times.split(',').map(t => t.trim()) : [], timezone: patient.timezone, meal_relation: meal, instructions: instructions || null };
    setDraft([...draft, { medicine: chosen, item }]); setChosen(null); invalidate(); setError('');
  }
  return <Stack spacing={3}>
    <Typography variant="h5" component="h2">Medicine reference & review</Typography>
    <Alert severity="info">The included catalogue is synthetic teaching data. Checks cover only recorded rules and exact generic-name allergies. No warnings does not establish safety. Saving a record does not create dose reminders yet.</Alert>
    {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}{notice && <Alert severity="success">{notice}</Alert>}
    <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={2}>
      <Typography variant="h6">Search reference catalogue</Typography>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField label="Brand or generic name" value={q} onChange={e => setQ(e.target.value)} fullWidth />
        <TextField label="Strength filter" placeholder="10 mg" value={strength} onChange={e => setStrength(e.target.value)} />
        <TextField select label="Form filter" value={form} onChange={e => setForm(e.target.value)} sx={{ minWidth: 140 }}><MenuItem value="">All forms</MenuItem>{Object.keys(units).map(f => <MenuItem key={f} value={f}>{f}</MenuItem>)}</TextField>
        <Button variant="contained" disabled={busy} onClick={() => void act(async () => { setGeneric(''); await search(0, q, strength, form, ''); })}>Search</Button>
      </Stack><Typography variant="body2">{page.total} matches · Similar spellings are included; verify strength and form.</Typography>
      {page.items.map(m => <Box key={m.id} sx={{ borderTop: '1px solid #e0e7e2', pt: 2 }}>
        <Typography fontWeight={700}>{m.brand_name} · {m.strength} · {m.form}</Typography><Typography>{m.generic_name}</Typography>
        <Typography variant="caption" sx={{ overflowWrap: 'anywhere' }}>Source: {m.source_name} · License/provenance: {m.source_license}</Typography>
        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 1 }}>
          <Button disabled={busy} onClick={() => void act(async () => { setQ(m.generic_name); setGeneric(m.generic_name); setStrength(''); setForm(''); await search(0, m.generic_name, '', '', m.generic_name); })}>Find generic alternatives</Button>
          {canWrite && <Button disabled={busy} onClick={() => setChosen(m)}>Choose {m.brand_name}</Button>}
          {user.is_admin && <><Button onClick={() => setRuleA(m)}>Use as rule A</Button><Button onClick={() => setRuleB(m)}>Use as rule B</Button></>}
        </Stack></Box>)}
      {!page.items.length && <Typography>No medicines found. An administrator can import a reference CSV.</Typography>}
      <Stack direction="row"><Button disabled={busy || !page.offset} onClick={() => void act(() => search(Math.max(0, page.offset - 20)))}>Previous medicines</Button><Button disabled={busy || page.offset + page.limit >= page.total} onClick={() => void act(() => search(page.offset + page.limit))}>Next medicines</Button></Stack>
    </Stack></Paper>
    {canRead && <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={2}>
      <Typography variant="h6">{patient?.display_name} · Recorded medicines</Typography>
      <Button disabled={busy} onClick={() => void act(async () => { await loadPatient(); invalidate(); })}>Refresh medicine records</Button>
      {saved.length ? saved.map(s => <Box key={s.id}><Typography fontWeight={600}>{s.medicine.brand_name} · {s.quantity_per_dose} {s.unit}</Typography><Typography variant="body2">{s.start_date} to {s.end_date ?? 'no end date'} · {s.schedule_kind === 'as_needed' ? 'As needed' : s.times_local.join(', ')} · {s.timezone}</Typography><Typography variant="caption">{s.schedule_status === 'generated' ? 'Schedule generated; refresh to extend it' : 'Schedule not generated; use Refresh dose schedule'}</Typography></Box>) : <Typography>No current or upcoming medicine records.</Typography>}
      <Divider /><DoseSchedule patientId={patient!.id} canWrite={canWrite} records={saved} />
      <Divider /><Typography variant="h6">Reported generic allergies</Typography>
      <TextField label="Allergy generic names (one per line)" multiline minRows={2} value={allergies} disabled={!canWrite || busy} onChange={e => { setAllergies(e.target.value); invalidate(); }} helperText="Use exact catalogue generic names. Class allergies and synonyms are not checked. Saving an empty list clears entries." />
      {canWrite && <Button disabled={busy} onClick={() => void act(async () => { await api(`${path}/allergies`, { method: 'PUT', body: JSON.stringify({ generic_names: allergies.split('\n').map(s => s.trim()).filter(Boolean) }) }); invalidate(); setNotice('Reported allergies saved.'); })}>Save reported allergies</Button>}
    </Stack></Paper>}
    {patient && !canRead && <Alert severity="info">Your permissions do not include this patient’s medicine records.</Alert>}
    {canWrite && <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={2}>
      <Typography variant="h6">Propose medicine record</Typography><Typography>Select a catalogue medicine and enter existing prescription instructions. Timezone: {patient?.timezone}.</Typography>
      {chosen && <><Typography fontWeight={700}>Selected: {chosen.brand_name} · {chosen.strength}</Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField label={`Quantity per dose (${units[chosen.form]})`} type="number" value={quantity} onChange={e => setQuantity(e.target.value)} slotProps={{ htmlInput: { min: .001, step: .001 } }} />
          <TextField label="Start date" type="date" value={start} onChange={e => setStart(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
          <TextField label="End date (optional)" type="date" value={end} onChange={e => setEnd(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
        </Stack>
        <TextField select label="Schedule kind" value={kind} onChange={e => setKind(e.target.value)}><MenuItem value="fixed_times">Fixed times</MenuItem><MenuItem value="as_needed">As needed</MenuItem></TextField>
        {kind === 'fixed_times' && <TextField label="Local times (HH:MM, comma separated)" value={times} onChange={e => setTimes(e.target.value)} helperText="Up to six times, e.g. 08:00, 20:00" />}
        <TextField select label="Meal relation" value={meal} onChange={e => setMeal(e.target.value)}><MenuItem value="none">Not specified</MenuItem><MenuItem value="before_meal">Before meal</MenuItem><MenuItem value="after_meal">After meal</MenuItem></TextField>
        <TextField label="Prescription instructions (optional)" value={instructions} onChange={e => setInstructions(e.target.value)} />
        <Button disabled={busy} variant="outlined" onClick={addItem}>Add to proposed list</Button></>}
      {draft.map((d, i) => <Stack key={i} direction="row" justifyContent="space-between"><Typography>{d.medicine.brand_name} · {d.item.quantity_per_dose} {d.item.unit} · {d.item.start_date}</Typography><Button disabled={busy} onClick={() => { setDraft(draft.filter((_, n) => n !== i)); invalidate(); }}>Remove item {i + 1}</Button></Stack>)}
      <Button variant="contained" disabled={busy || !draft.length} onClick={() => void act(async () => { invalidate(); setReview(await api<Review>(`${path}/interaction-check`, { method: 'POST', body: JSON.stringify({ items: draft.map(d => d.item) }) })); })}>Check proposed medicines</Button>
      {review && <><Typography variant="h6">Warning review</Typography><Typography>{review.coverage}</Typography>
        {!review.warnings.length && <Alert severity="info">No matches in the limited reference rules.</Alert>}
        {review.warnings.map(w => <Box key={w.id}><Alert severity={w.severity === 'critical' ? 'error' : w.severity === 'warning' ? 'warning' : 'info'}><Typography fontWeight={700}>{w.kind} · {w.severity}</Typography><Typography>{w.message}</Typography><Typography variant="caption">Source: {w.source}</Typography></Alert><FormControlLabel control={<Checkbox checked={ack.includes(w.id)} onChange={e => setAck(e.target.checked ? [...ack, w.id] : ack.filter(id => id !== w.id))} />} label={`I have reviewed this ${w.kind} warning`} /></Box>)}
        <Typography variant="caption">Acknowledgement records review, not medical approval. Review expires in 15 minutes.</Typography>
        <Button variant="contained" disabled={busy || ack.length !== review.warnings.length} onClick={() => void act(async () => { await api(`${path}/prescriptions/confirm`, { method: 'POST', body: JSON.stringify({ check_id: review.check_id, acknowledged_warning_ids: ack }) }); setDraft([]); invalidate(); await loadPatient(); setNotice('Medicine record saved and dose schedule generated.'); })}>Confirm medicine record</Button></>}
    </Stack></Paper>}
    {user.is_admin && <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={2}>
      <Typography variant="h6">Reference administration</Typography><Typography>CSV columns: generic_name, brand_name, strength, form, source_name, source_license. Up to 500 rows. Any invalid row prevents the entire import; existing identities are skipped.</Typography>
      <Button component="label" variant="outlined">Choose medicine CSV<input hidden type="file" accept=".csv,text/csv" onChange={e => { const f = e.target.files?.[0]; if (!f) return; if (f.size > 500000) { setError('CSV must be under 500 KB.'); return; } void f.text().then(setCsv).catch(() => setError('Could not read CSV.')); }} /></Button>
      <TextField label="CSV content" multiline minRows={3} maxRows={8} value={csv} onChange={e => setCsv(e.target.value)} />
      <Button disabled={busy || !csv} onClick={() => void act(async () => { const r = await api<{ imported: number; duplicates: number; errors: { row: number; message: string }[] }>('/medicines/import', { method: 'POST', body: JSON.stringify({ csv_text: csv }) }); setImportResult(r.errors.length ? r.errors.map(e => `Row ${e.row}: ${e.message}`).join('\n') : `Imported ${r.imported}; skipped ${r.duplicates} duplicates.`); invalidate(); await search(); })}>Validate and import CSV</Button>
      {importResult && <Typography sx={{ whiteSpace: 'pre-wrap' }} role="status">{importResult}</Typography>}
      <Divider /><Typography variant="h6">Curated interaction rule</Typography><Typography>Select A/B from catalogue results. Rules apply to that generic pair across brands and strengths.</Typography><Typography>A: {ruleA?.brand_name ?? 'Not selected'} · B: {ruleB?.brand_name ?? 'Not selected'}</Typography>
      <TextField select label="Rule severity" value={severity} onChange={e => setSeverity(e.target.value)}>{['info', 'warning', 'critical'].map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}</TextField>
      <TextField label="Rule explanation" value={explanation} onChange={e => setExplanation(e.target.value)} /><TextField label="Rule source / provenance" value={source} onChange={e => setSource(e.target.value)} />
      <Button disabled={busy || !ruleA || !ruleB || !explanation.trim() || !source.trim()} onClick={() => void act(async () => { await api('/medicines/interaction-rules', { method: 'POST', body: JSON.stringify({ medicine_a_id: ruleA?.id, medicine_b_id: ruleB?.id, severity, explanation, source }) }); invalidate(); setRules((await api<{ items: Rule[] }>('/medicines/interaction-rules')).items); setNotice('Curated rule saved.'); })}>Save interaction rule</Button>
      {rules.map(r => <Typography key={r.id} variant="body2">{r.severity}: {r.explanation} — {r.source}</Typography>)}
    </Stack></Paper>}
  </Stack>;
}
