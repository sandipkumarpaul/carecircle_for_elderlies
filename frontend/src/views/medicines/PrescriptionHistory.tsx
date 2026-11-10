import React from 'react';
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material';
import { api } from '../../lib/api';
import type { Medicine, Item } from './MedicineView';

export type Version = { id: string; prescription_id: string; version_number: number; status: string; current: boolean; effective_from: string; effective_until: string | null; change_reason: string | null; items: (Item & { medicine: Medicine })[] };
type History = { items: Version[]; total: number; offset: number; limit: number };

export function PrescriptionHistory({ patientId, canWrite, records, onRevise, onChanged }: { patientId: string; canWrite: boolean; records: unknown; onRevise: (v: Version) => void; onChanged: () => Promise<void> }) {
  const [data, setData] = React.useState<History>({ items: [], total: 0, offset: 0, limit: 20 });
  const [busy, setBusy] = React.useState(false); const [error, setError] = React.useState('');
  const [stopping, setStopping] = React.useState<Version | null>(null); const [reason, setReason] = React.useState('');
  const path = `/patients/${patientId}`;
  async function load(offset = 0) { setData(await api<History>(`${path}/prescription-history?offset=${offset}`)); }
  async function act(fn: () => Promise<void>) { setBusy(true); setError(''); try { await fn(); } catch (e) { setError((e as Error).message); setData({ items: [], total: 0, offset: 0, limit: 20 }); } finally { setBusy(false); } }
  React.useEffect(() => { void act(() => load()); }, [patientId, records]);
  return <Stack spacing={2}>
    <Typography component="h3" variant="h6">Prescription version history</Typography>
    <Typography variant="body2">Revise or stop only to record an existing clinician instruction. Changes take effect when confirmed. Earlier versions and completed dose history are preserved.</Typography>
    {error && <Alert severity="error">{error}</Alert>}
    <Button disabled={busy} onClick={() => void act(() => load())}>Refresh prescription history</Button>
    {data.items.map(v => <Box key={v.id} data-testid="prescription-version" sx={{ border: '1px solid #dce6df', borderRadius: 1, p: 2 }}>
      <Typography fontWeight={700}>Version {v.version_number} · {v.status === 'stopped' ? 'Stopped' : v.current ? 'Current' : 'Previous'}</Typography>
      <Typography variant="body2">From {new Date(v.effective_from).toLocaleString()}{v.effective_until ? ` until ${new Date(v.effective_until).toLocaleString()}` : ''}</Typography>
      {v.change_reason && <Typography sx={{ overflowWrap: 'anywhere' }}>Reason: {v.change_reason}</Typography>}
      {v.items.map((i, n) => <Box key={n}><Typography>{i.medicine.brand_name} · {i.medicine.strength} · {i.quantity_per_dose} {i.unit}</Typography><Typography variant="body2">{i.start_date} to {i.end_date ?? 'no end date'} · {i.schedule_kind === 'as_needed' ? 'As needed' : i.times_local.join(', ')} · {i.timezone}</Typography>{i.instructions && <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{i.instructions}</Typography>}</Box>)}
      {canWrite && v.current && <Stack direction="row" flexWrap="wrap"><Button disabled={busy} onClick={() => onRevise(v)}>Revise this prescription</Button><Button disabled={busy} onClick={() => { setStopping(v); setReason(''); }}>Stop this prescription</Button></Stack>}
    </Box>)}
    {!data.items.length && <Typography>No prescription versions to show.</Typography>}
    {stopping && <Box sx={{ border: '1px solid #dce6df', p: 2 }}><Stack spacing={2}>
      <Typography>Stop version {stopping.version_number}? Future pending doses will be cancelled and authorized care-circle recipients will receive an in-app alert.</Typography>
      <TextField label="Reason for stopping" value={reason} onChange={e => setReason(e.target.value)} multiline slotProps={{ htmlInput: { maxLength: 1000 } }} />
      <Stack direction="row"><Button disabled={busy || reason.trim().length < 3} onClick={() => void act(async () => { await api(`${path}/prescriptions/${stopping.prescription_id}/stop`, { method: 'POST', body: JSON.stringify({ expected_version_id: stopping.id, reason }) }); setStopping(null); await onChanged(); await load(); })}>Confirm stop</Button><Button disabled={busy} onClick={() => setStopping(null)}>Cancel stop</Button></Stack>
    </Stack></Box>}
    <Stack direction="row"><Button disabled={busy || !data.offset} onClick={() => void act(() => load(data.offset - 20))}>Previous versions</Button><Button disabled={busy || data.offset + 20 >= data.total} onClick={() => void act(() => load(data.offset + 20))}>Next versions</Button></Stack>
  </Stack>;
}
