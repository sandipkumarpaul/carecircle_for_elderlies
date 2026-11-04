import { useState } from 'react';
import { Alert, Button, Card, CardContent, Checkbox, Chip, FormControlLabel, Stack, TextField, Typography } from '@mui/material';
import { api } from '../../lib/api';
import { Invitation, Patient, scopeLabels } from '../../lib/types';
export function AcceptInvite({ initialToken, onAccepted }: { initialToken: string; onAccepted: (p: Patient) => void }) {
  const [input, setInput] = useState(initialToken); const [preview, setPreview] = useState<Invitation | null>(null);
  const [consent, setConsent] = useState(false); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  function token() { return input.includes('#invite=') ? new URLSearchParams(new URL(input).hash.slice(1)).get('invite') ?? '' : input.trim(); }
  async function act(accept: boolean) {
    setBusy(true); setError('');
    try {
      if (accept) { const p = await api<Patient>('/circle/invites/accept', { method: 'POST', body: JSON.stringify({ token: token(), consent }) }); setInput(''); setPreview(null); setConsent(false); history.replaceState(null, '', location.pathname); onAccepted(p); }
      else { setPreview(await api<Invitation>('/circle/invites/preview', { method: 'POST', body: JSON.stringify({ token: token() }) })); setConsent(false); }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <Card variant="outlined"><CardContent><Stack spacing={2}><Typography variant="h6" component="h2">Have an invitation?</Typography>
    <Typography color="text.secondary">Paste the link shared with you. Your account email must match the invitation.</Typography>
    <TextField label="Invitation link or token" value={input} onChange={e => { setInput(e.target.value); setPreview(null); }} />
    {!preview && <Button variant="outlined" disabled={!input || busy} onClick={() => act(false)}>Review invitation</Button>}
    {preview && <><Typography>Join <strong>{preview.patient_name}</strong> as a {preview.role} caregiver.</Typography><Stack direction="row" gap={1} flexWrap="wrap">{preview.scopes.map(s => <Chip key={s} size="small" label={scopeLabels[s] ?? s} />)}</Stack>
      <Typography variant="body2">Expires: {new Date(preview.expires_at).toLocaleString()}</Typography><FormControlLabel control={<Checkbox checked={consent} onChange={(_, v) => setConsent(v)} />} label="I accept this caregiver role and the access shown above." />
      <Button variant="contained" disabled={!consent || busy} onClick={() => act(true)}>Accept invitation</Button></>}
    {error && <Alert severity="error">{error}</Alert>}
  </Stack></CardContent></Card>;
}
