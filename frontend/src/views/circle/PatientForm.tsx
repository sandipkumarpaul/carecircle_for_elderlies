import { useState } from 'react';
import { Alert, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, MenuItem, Stack, TextField } from '@mui/material';
import { api } from '../../lib/api';
import { Patient } from '../../lib/types';
export function PatientForm({ onClose, onCreated }: { onClose: () => void; onCreated: (p: Patient) => void }) {
  const [kind, setKind] = useState('self'); const [consent, setConsent] = useState(false);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError('');
    try { onCreated(await api<Patient>('/patients', { method: 'POST', body: JSON.stringify({ display_name: form.get('display_name'), timezone: form.get('timezone'), kind, consent, consent_basis: form.get('consent_basis') }) })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <Dialog open onClose={busy ? undefined : onClose} fullWidth maxWidth="sm"><form onSubmit={submit}><DialogTitle>Create a patient profile</DialogTitle><DialogContent><Stack spacing={2} sx={{ pt: 1 }}>
    <TextField select label="Who is this profile for?" value={kind} onChange={e => { setKind(e.target.value); setConsent(false); }}><MenuItem value="self">Myself</MenuItem><MenuItem value="dependent">Someone I am authorized to care for</MenuItem></TextField>
    <TextField required name="display_name" label="Patient name" inputProps={{ maxLength: 100 }} />
    <TextField required name="timezone" label="Patient timezone" defaultValue="Asia/Dhaka" helperText="Use an IANA name, such as Asia/Dhaka or Europe/London." />
    <TextField required multiline minRows={2} name="consent_basis" label="Consent / authority statement" inputProps={{ minLength: 10, maxLength: 300 }} helperText={kind === 'self' ? 'For example: I consent to managing my care with CareCircle.' : 'Describe the patient’s consent or your authority to represent them.'} />
    <FormControlLabel control={<Checkbox checked={consent} onChange={(_, v) => setConsent(v)} />} label="I confirm this consent statement and authorize creating this profile." />
    {error && <Alert severity="error">{error}</Alert>}
  </Stack></DialogContent><DialogActions sx={{ p: 3 }}><Button disabled={busy} onClick={onClose}>Cancel</Button><Button type="submit" variant="contained" disabled={!consent || busy}>Create profile</Button></DialogActions></form></Dialog>;
}
