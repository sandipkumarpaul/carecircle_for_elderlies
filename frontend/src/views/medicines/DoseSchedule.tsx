import React from 'react';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import { api } from '../../lib/api';

type Dose = { id: string; medicine_name: string; strength: string; scheduled_at: string; timezone: string; quantity: string; unit: string; meal_relation: string; instructions: string | null };
type Result = { items: Dose[]; total: number; offset: number; limit: number };

export function DoseSchedule({ patientId, canWrite, records }: { patientId: string; canWrite: boolean; records: unknown }) {
  const [data, setData] = React.useState<Result>({ items: [], total: 0, offset: 0, limit: 50 });
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const path = `/patients/${patientId}/doses`;
  async function load(offset = 0, refresh = false) {
    setBusy(true); setError('');
    try {
      if (refresh) await api(`${path}/refresh`, { method: 'POST' });
      setData(await api<Result>(`${path}?offset=${offset}`));
    } catch (e) { setData({ items: [], total: 0, offset: 0, limit: 50 }); setError((e as Error).message); }
    finally { setBusy(false); }
  }
  React.useEffect(() => { void load(); }, [patientId, records]);
  return <Stack spacing={2}>
    <Typography component="h3" variant="h6">Upcoming doses</Typography>
    <Typography variant="body2">Times use each medicine record’s timezone. The schedule covers today and the next 13 days when generated. As-needed medicines have no automatic doses. No reminders are sent yet.</Typography>
    {error && <Alert severity="error">{error}</Alert>}
    {canWrite && <Button disabled={busy} onClick={() => void load(0, true)}>Refresh dose schedule</Button>}
    {data.items.map(d => <Box key={d.id} data-testid="scheduled-dose">
      <Typography fontWeight={600}>{d.medicine_name} · {d.strength} · {d.quantity} {d.unit}</Typography>
      <Typography>{new Date(d.scheduled_at).toLocaleString('en-GB', { timeZone: d.timezone })} · {d.timezone}</Typography>
      {d.meal_relation !== 'none' && <Typography>{d.meal_relation.replaceAll('_', ' ')}</Typography>}
      {d.instructions && <Typography sx={{ overflowWrap: 'anywhere' }}>{d.instructions}</Typography>}
    </Box>)}
    {!data.items.length && <Typography>No upcoming scheduled doses. For older records, a member with Manage medicines can refresh the schedule.</Typography>}
    <Typography variant="body2">{data.total} upcoming doses</Typography>
    <Stack direction="row"><Button disabled={busy || !data.offset} onClick={() => void load(Math.max(0, data.offset - data.limit))}>Previous doses</Button><Button disabled={busy || data.offset + data.limit >= data.total} onClick={() => void load(data.offset + data.limit)}>Next doses</Button></Stack>
  </Stack>;
}
