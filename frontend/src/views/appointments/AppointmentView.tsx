import React from 'react';
import { Alert, Box, Button, Checkbox, Chip, Divider, FormControlLabel, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { api } from '../../lib/api';
import { Page, Patient } from '../../lib/types';

// CC-14 (Saif): schedule appointments, manage pre-visit checklist, complete/cancel and post-visit prompt.
type Status = 'scheduled' | 'completed' | 'cancelled';
type ChecklistItem = { text: string; done: boolean };
type Appt = { id: string; clinician_label: string; location: string | null; notes: string | null; scheduled_at: string; scheduled_local: string; timezone: string; status: Status; checklist: { items: ChecklistItem[] }; completed_at: string | null; cancelled_at: string | null; cancelled_reason: string | null; post_visit_prompt_at: string | null; post_visit_dismissed_at: string | null; created_by_name: string };

const statusChip: Record<Status, { label: string; color: 'info' | 'success' | 'default' }> = {
  scheduled: { label: 'Scheduled', color: 'info' },
  completed: { label: 'Completed', color: 'success' },
  cancelled: { label: 'Cancelled', color: 'default' },
};

const blank = { clinician_label: '', location: '', notes: '', scheduled_at: '', timezone: 'Asia/Dhaka', checklist_text: '' };

export function AppointmentView({ patient }: { patient: Patient | null }) {
  const canRead = !!patient?.scopes.some(s => s === 'appointments:read' || s === 'appointments:write');
  const canWrite = !!patient?.scopes.includes('appointments:write');
  const path = `/patients/${patient?.id}`;
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState(''); const [notice, setNotice] = React.useState('');
  const [page, setPage] = React.useState<Page<Appt>>({ items: [], total: 0, offset: 0, limit: 10 });
  const [filter, setFilter] = React.useState<'' | Status>('');
  const [form, setForm] = React.useState(blank);
  const [expanded, setExpanded] = React.useState<string | null>(null);

  async function act(work: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await work(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function load(offset = 0, only: '' | Status = filter) {
    const params = new URLSearchParams({ offset: String(offset), limit: '10' });
    if (only) params.set('status', only);
    setPage(await api<Page<Appt>>(`${path}/appointments?${params}`));
  }
  React.useEffect(() => { if (canRead) void act(() => load()); }, [patient?.id]);

  async function saveAppointment(e: React.FormEvent) {
    e.preventDefault();
    await act(async () => {
      const checklist = form.checklist_text.split('\n').map(t => t.trim()).filter(Boolean).map(text => ({ text, done: false }));
      const body: Record<string, unknown> = { clinician_label: form.clinician_label, timezone: form.timezone, scheduled_at: new Date(form.scheduled_at).toISOString(), checklist };
      if (form.location.trim()) body.location = form.location.trim();
      if (form.notes.trim()) body.notes = form.notes.trim();
      await api(`${path}/appointments`, { method: 'POST', body: JSON.stringify(body) });
      setNotice('Appointment scheduled.'); setForm(blank); await load();
    });
  }
  async function toggleItem(appt: Appt, idx: number, done: boolean) {
    await act(async () => {
      await api(`${path}/appointments/${appt.id}/checklist/${idx}?done=${done}`, { method: 'PATCH', body: JSON.stringify({}) });
      await load(page.offset);
      setExpanded(appt.id); // keep checklist open after reload
    });
  }
  async function complete(appt: Appt) {
    await act(async () => {
      await api(`${path}/appointments/${appt.id}/complete`, { method: 'POST', body: JSON.stringify({ post_visit_prompt: true }) });
      setNotice('Appointment marked completed. A prescription upload prompt has been added.'); await load(page.offset);
    });
  }
  async function cancel(appt: Appt) {
    const reason = window.prompt('Reason for cancellation (optional):') ?? undefined;
    await act(async () => {
      await api(`${path}/appointments/${appt.id}/cancel`, { method: 'POST', body: JSON.stringify({ reason: reason || null }) });
      setNotice('Appointment cancelled.'); await load(page.offset);
    });
  }
  async function dismissPrompt(appt: Appt) {
    await act(async () => {
      await api(`${path}/appointments/${appt.id}/dismiss-prompt`, { method: 'POST', body: JSON.stringify({}) });
      setNotice('Post-visit prompt dismissed.'); await load(page.offset);
    });
  }
  const fmt = (iso: string) => new Date(iso).toLocaleString(undefined, { timeZone: patient?.timezone, dateStyle: 'medium', timeStyle: 'short' });

  return <Stack spacing={3}>
    <Typography variant="h5" component="h2">Appointments</Typography>
    {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
    {notice && <Alert severity="success" onClose={() => setNotice('')}>{notice}</Alert>}
    {!patient ? <Alert severity="info">Choose a patient profile to see appointments.</Alert>
      : !canRead ? <Alert severity="warning">Your access does not include viewing appointments for this patient.</Alert>
      : <>
      {canWrite && <Paper variant="outlined" sx={{ p: 3 }}><form onSubmit={saveAppointment}><Stack spacing={2}>
        <Typography variant="h6" component="h3">Schedule appointment</Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField required label="Clinician or service" value={form.clinician_label} onChange={e => setForm({ ...form, clinician_label: e.target.value })} fullWidth />
          <TextField label="Location (optional)" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} fullWidth />
        </Stack>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField required type="datetime-local" label="Date and time" value={form.scheduled_at} onChange={e => setForm({ ...form, scheduled_at: e.target.value })} slotProps={{ inputLabel: { shrink: true } }} sx={{ minWidth: 260 }} />
          <TextField required label="Timezone" value={form.timezone} onChange={e => setForm({ ...form, timezone: e.target.value })} helperText="IANA name, e.g. Asia/Dhaka" />
        </Stack>
        <TextField label="Notes (optional)" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} multiline minRows={2} />
        <TextField label="Pre-visit checklist items (one per line, optional)" value={form.checklist_text} onChange={e => setForm({ ...form, checklist_text: e.target.value })} multiline minRows={2} helperText="e.g. Bring current prescriptions" />
        <Box><Button type="submit" variant="contained" disabled={busy || !form.clinician_label || !form.scheduled_at}>Schedule</Button></Box>
      </Stack></form></Paper>}

      <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={2}>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={2}>
          <Typography variant="h6" component="h3">Appointments ({page.total})</Typography>
          <TextField select size="small" label="Show" value={filter} onChange={e => { const f = e.target.value as '' | Status; setFilter(f); void act(() => load(0, f)); }} sx={{ minWidth: 180 }}>
            <MenuItem value="">All</MenuItem><MenuItem value="scheduled">Scheduled</MenuItem><MenuItem value="completed">Completed</MenuItem><MenuItem value="cancelled">Cancelled</MenuItem>
          </TextField>
        </Stack>
        {page.items.length === 0 && <Typography color="text.secondary">No appointments found.</Typography>}
        {page.items.map(appt => <Box key={appt.id}><Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between" alignItems={{ sm: 'flex-start' }}>
          <Box sx={{ flex: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography fontWeight={600}>{appt.clinician_label}</Typography>
              <Chip size="small" label={statusChip[appt.status].label} color={statusChip[appt.status].color} />
            </Stack>
            <Typography variant="body2" color="text.secondary">{fmt(appt.scheduled_at)}{appt.location ? ` · ${appt.location}` : ''} · {appt.timezone}</Typography>
            {appt.notes && <Typography variant="body2" sx={{ mt: 0.5 }}>{appt.notes}</Typography>}
            {appt.status === 'cancelled' && appt.cancelled_reason && <Typography variant="body2" color="text.secondary">Reason: {appt.cancelled_reason}</Typography>}
            {appt.post_visit_prompt_at && !appt.post_visit_dismissed_at && <Alert severity="info" sx={{ mt: 1 }} action={canWrite ? <Button size="small" onClick={() => void dismissPrompt(appt)}>Dismiss</Button> : undefined}>Post-visit: remember to upload the new prescription.</Alert>}
            {appt.checklist.items.length > 0 && <Box sx={{ mt: 1 }}>
              <Button size="small" onClick={() => setExpanded(expanded === appt.id ? null : appt.id)}>{expanded === appt.id ? 'Hide checklist' : `Show checklist (${appt.checklist.items.filter(i => i.done).length}/${appt.checklist.items.length} done)`}</Button>
              {expanded === appt.id && <Stack sx={{ ml: 1 }}>{appt.checklist.items.map((item, idx) => <FormControlLabel key={idx} control={<Checkbox checked={item.done} disabled={!canWrite || appt.status !== 'scheduled' || busy} onChange={e => void toggleItem(appt, idx, e.target.checked)} size="small" />} label={<Typography variant="body2" sx={{ textDecoration: item.done ? 'line-through' : 'none' }}>{item.text}</Typography>} />)}</Stack>}
            </Box>}
          </Box>
          {canWrite && appt.status === 'scheduled' && <Stack direction="row" spacing={1} sx={{ flexShrink: 0 }}>
            <Button size="small" variant="outlined" disabled={busy} onClick={() => void complete(appt)}>Complete</Button>
            <Button size="small" color="error" disabled={busy} onClick={() => void cancel(appt)}>Cancel</Button>
          </Stack>}
        </Stack><Divider sx={{ mt: 2 }} /></Box>)}
        {page.total > page.limit && <Stack direction="row" spacing={2} alignItems="center">
          <Button disabled={busy || !page.offset} onClick={() => void act(() => load(page.offset - page.limit))}>Previous</Button>
          <Typography>{page.offset + 1}–{Math.min(page.offset + page.limit, page.total)} of {page.total}</Typography>
          <Button disabled={busy || page.offset + page.limit >= page.total} onClick={() => void act(() => load(page.offset + page.limit))}>Next</Button>
        </Stack>}
      </Stack></Paper>
    </>}
  </Stack>;
}
