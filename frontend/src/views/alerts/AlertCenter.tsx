import React from 'react';
import { Alert, Box, Button, Checkbox, Chip, FormControlLabel, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { api } from '../../lib/api';
import { Patient } from '../../lib/types';

type Entry = { id: string; type: string; severity: 'info' | 'warning' | 'critical'; status: string; source_type: string; created_at: string; read_at: string | null; acknowledged_at: string | null; resolved_at: string | null };
type Feed = { items: Entry[]; total: number; offset: number; limit: number };
type Preference = { timezone: string; quiet_start: string | null; quiet_end: string | null };
const names: Record<string, string> = { vital_threshold: 'Vital reading outside set limits', vital_trend: 'Worsening vital trend', missed_dose: 'Missed medicine dose', low_stock: 'Medicine running low', stock_reconciliation: 'Medicine stock needs review', checkin_missed: 'Daily check-in missed', prescription_changed: 'Prescription changed', possible_side_effect: 'Possible medicine side effect', adherence_risk: 'Medicine adherence risk', task_due: 'Care task due', sos: 'Emergency SOS' };

export function AlertCenter({ patient }: { patient: Patient | null }) {
  const canRead = !!patient?.scopes.some(s => s === 'alerts:read' || s === 'alerts:write');
  const canWrite = !!patient?.scopes.includes('alerts:write');
  const [feed, setFeed] = React.useState<Feed>({ items: [], total: 0, offset: 0, limit: 20 });
  const [status, setStatus] = React.useState(''); const [severity, setSeverity] = React.useState('');
  const [unread, setUnread] = React.useState(false); const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(''); const [notice, setNotice] = React.useState('');
  const [prefs, setPrefs] = React.useState<Preference>({ timezone: patient?.timezone ?? 'Asia/Dhaka', quiet_start: null, quiet_end: null });
  const path = `/patients/${patient?.id}`;
  async function load(offset = 0) {
    const params = new URLSearchParams({ offset: String(offset), unread: String(unread) });
    if (status) params.set('status', status); if (severity) params.set('severity', severity);
    setFeed(await api<Feed>(`${path}/alerts?${params}`));
  }
  async function act(work: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await work(); } catch (e) { setError((e as Error).message); setFeed({ items: [], total: 0, offset: 0, limit: 20 }); }
    finally { setBusy(false); }
  }
  React.useEffect(() => { if (canRead) void act(async () => { await load(); setPrefs(await api<Preference>(`${path}/alert-preferences`)); }); }, []);
  if (!patient) return null;
  if (!canRead) return <Alert severity="info">Your permissions do not include this patient’s alert centre.</Alert>;
  return <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 } }}><Stack spacing={2}>
    <Typography component="h2" variant="h5">Health alert centre</Typography>
    <Typography>Alerts for {patient.display_name}, with critical alerts first, then warnings and information; newest first within each severity.</Typography>
    <Typography variant="body2">Only alerts addressed to you and still permitted by your access are shown. Acknowledging means someone is handling the alert; resolving closes it for the care circle. Neither action changes the underlying health record.</Typography>
    {error && <Alert severity="error">{error}</Alert>}{notice && <Alert severity="success">{notice}</Alert>}
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
      <TextField select label="Alert status filter" value={status} onChange={e => setStatus(e.target.value)} sx={{ minWidth: 160 }}><MenuItem value="">All statuses</MenuItem>{['open', 'acknowledged', 'resolved'].map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}</TextField>
      <TextField select label="Alert severity filter" value={severity} onChange={e => setSeverity(e.target.value)} sx={{ minWidth: 160 }}><MenuItem value="">All severities</MenuItem>{['critical', 'warning', 'info'].map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}</TextField>
      <FormControlLabel control={<Checkbox checked={unread} onChange={e => setUnread(e.target.checked)} />} label="Unread alerts only" />
      <Button disabled={busy} onClick={() => void act(() => load())}>Refresh alerts</Button>
    </Stack>
    <Typography role="status">{feed.total} matching alerts</Typography>
    {!feed.items.length && <Typography>No matching alerts. New vital alerts appear here after refreshing.</Typography>}
    {feed.items.map(entry => <Box key={entry.id} data-testid="alert-entry" sx={{ border: '1px solid #dce6df', borderRadius: 1, p: 2 }}>
      <Stack direction="row" gap={1} flexWrap="wrap"><Chip size="small" color={entry.severity === 'critical' ? 'error' : entry.severity === 'warning' ? 'warning' : 'info'} label={entry.severity} /><Chip size="small" label={entry.status} /><Chip size="small" label={entry.read_at ? 'Read' : 'Unread'} /></Stack>
      <Typography component="h3" variant="h6" sx={{ mt: 1 }}>{names[entry.type] ?? entry.type.replaceAll('_', ' ')}</Typography>
      <Typography variant="body2">Raised {new Date(entry.created_at).toLocaleString()}</Typography>
      {entry.acknowledged_at && <Typography variant="body2">Acknowledged {new Date(entry.acknowledged_at).toLocaleString()}</Typography>}
      {entry.resolved_at && <Typography variant="body2">Resolved {new Date(entry.resolved_at).toLocaleString()}</Typography>}
      <Stack direction="row" flexWrap="wrap" gap={1}>
        {entry.source_type === 'vital' && <Button href="#vitals-panel">Review vitals</Button>}
        {!entry.read_at && <Button disabled={busy} onClick={() => void act(async () => { await api(`${path}/alerts/${entry.id}/read`, { method: 'POST' }); await load(feed.offset); })}>Mark read</Button>}
        {canWrite && entry.status === 'open' && <Button disabled={busy} onClick={() => void act(async () => { await api(`${path}/alerts/${entry.id}/acknowledge`, { method: 'POST' }); await load(feed.offset); setNotice('Alert acknowledged. Pending escalation deliveries cancelled.'); })}>Acknowledge alert</Button>}
        {canWrite && entry.status !== 'resolved' && <Button disabled={busy} onClick={() => void act(async () => { await api(`${path}/alerts/${entry.id}/resolve`, { method: 'POST' }); await load(feed.offset); setNotice('Alert resolved.'); })}>Resolve alert</Button>}
      </Stack>
    </Box>)}
    <Stack direction="row"><Button disabled={busy || !feed.offset} onClick={() => void act(() => load(Math.max(0, feed.offset - 20)))}>Previous alerts</Button><Button disabled={busy || feed.offset + 20 >= feed.total} onClick={() => void act(() => load(feed.offset + 20))}>Next alerts</Button></Stack>
    <Typography component="h3" variant="h6">Your email quiet hours for this patient</Typography>
    <Typography variant="body2">Noncritical email deliveries wait until quiet hours end. Critical alerts bypass quiet hours, and in-app alerts remain visible. Email sending is not connected yet.</Typography>
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
      <TextField label="Quiet-hours timezone" value={prefs.timezone} onChange={e => setPrefs({ ...prefs, timezone: e.target.value })} />
      <TextField label="Quiet hours start" type="time" value={prefs.quiet_start ?? ''} slotProps={{ inputLabel: { shrink: true } }} onChange={e => setPrefs({ ...prefs, quiet_start: e.target.value || null })} />
      <TextField label="Quiet hours end" type="time" value={prefs.quiet_end ?? ''} slotProps={{ inputLabel: { shrink: true } }} onChange={e => setPrefs({ ...prefs, quiet_end: e.target.value || null })} />
    </Stack>
    <Stack direction="row"><Button disabled={busy} onClick={() => void act(async () => { setPrefs(await api<Preference>(`${path}/alert-preferences`, { method: 'PUT', body: JSON.stringify(prefs) })); setNotice('Quiet hours saved.'); })}>Save quiet hours</Button><Button disabled={busy} onClick={() => void act(async () => { setPrefs(await api<Preference>(`${path}/alert-preferences`, { method: 'PUT', body: JSON.stringify({ ...prefs, quiet_start: null, quiet_end: null }) })); setNotice('Quiet hours disabled.'); })}>Disable quiet hours</Button></Stack>
  </Stack></Paper>;
}
