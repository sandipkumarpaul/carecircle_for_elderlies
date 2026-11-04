import { useEffect, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControlLabel, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { ScopePicker } from '../../components/ScopePicker';
import { api } from '../../lib/api';
import { Circle, Grant, Invitation, Member, Patient, User, scopeLabels } from '../../lib/types';

export function CircleView({ patient, user, onAccessChanged }: { patient: Patient; user: User; onAccessChanged: () => void }) {
  const [data, setData] = useState<Circle | null>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [grant, setGrant] = useState<Grant>({ role: 'secondary', scopes: [] }); const [editing, setEditing] = useState<Member | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false); const [consent, setConsent] = useState(false); const [link, setLink] = useState('');
  const [confirm, setConfirm] = useState<{ kind: 'members' | 'invites'; id: string; name: string } | null>(null);
  const base = `/patients/${patient.id}/circle`;
  async function reload() {
    try { setData(await api<Circle>(base)); } catch (e) { setData(null); setError((e as Error).message); onAccessChanged(); }
  }
  useEffect(() => { setData(null); setLink(''); if (patient.can_manage) void reload(); }, [patient.id, patient.can_manage]);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const fields = new FormData(event.currentTarget); setBusy(true); setError('');
    try {
      if (editing) await api(`${base}/members/${editing.id}`, { method: 'PATCH', body: JSON.stringify(grant) });
      else { const result = await api<Invitation & { invite_url: string }>(`${base}/invites`, { method: 'POST', body: JSON.stringify({ ...grant, email: fields.get('email'), expires_in_hours: Number(fields.get('expires')), consent }) }); setLink(result.invite_url); }
      setEditing(null); setInviteOpen(false); await reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function revoke() {
    if (!confirm) return; setBusy(true); setError('');
    try { await api(`${base}/${confirm.kind}/${confirm.id}`, { method: 'DELETE' }); setConfirm(null); await reload(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  if (!patient.can_manage) return <Card variant="outlined"><CardContent><Stack spacing={2}>
    <Typography variant="h6">Your access to {patient.display_name}</Typography><Typography>You are a {patient.role} caregiver. Circle management is not included in your access.</Typography>
    <Stack direction="row" gap={1} flexWrap="wrap">{patient.scopes.map(s => <Chip key={s} label={scopeLabels[s] ?? s} />)}</Stack>{!patient.scopes.length && <Typography>No health-data access has been granted yet.</Typography>}
  </Stack></CardContent></Card>;
  return <Stack spacing={3}>
    <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems="start" gap={2}>
      <Box><Typography variant="h5" component="h2">{patient.display_name}’s care circle</Typography><Typography color="text.secondary">{patient.timezone} · Your role: {patient.role}</Typography></Box>
      <Button variant="contained" onClick={() => { setEditing(null); setGrant({ role: 'secondary', scopes: [] }); setConsent(false); setInviteOpen(true); setError(''); }}>Invite caregiver</Button>
    </Stack>
    {error && <Alert severity="error">{error}</Alert>}
    {link && <Alert severity="success"><Stack spacing={1}><Typography>Invitation created. Copy this private link and share it with the invited person. No email was sent.</Typography>
      <TextField label="New invitation link" value={link} fullWidth slotProps={{ input: { readOnly: true } }} /><Button size="small" onClick={() => void navigator.clipboard.writeText(link).catch(() => setError('Select and copy the link manually.'))}>Copy link</Button>
    </Stack></Alert>}
    {!data && !error && <Typography role="status">Loading care circle…</Typography>}
    {data && <><Card variant="outlined"><CardContent><Typography variant="h6" component="h3" sx={{ mb: 2 }}>Caregivers</Typography>
      {!data.members.length && <Typography color="text.secondary">No caregivers yet. Invite someone you trust.</Typography>}
      <Stack spacing={2}>{data.members.map(member => <Box key={member.id}>
        <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap"><Typography fontWeight={700}>{member.display_name}</Typography><Chip size="small" label={member.revoked_at ? 'Revoked' : member.role} /></Stack>
        <Typography variant="body2" color="text.secondary">{member.email}</Typography><Typography variant="body2" sx={{ my: 1 }}>{member.scopes.map(s => scopeLabels[s] ?? s).join(' · ') || 'No health-data permissions'}</Typography>
        {!member.revoked_at && member.user_id !== user.id && (member.role !== 'primary' || patient.role === 'patient') && <Stack direction="row" gap={1}>
          <Button size="small" onClick={() => { setEditing(member); setGrant({ role: member.role, scopes: member.scopes }); setError(''); }}>Edit access</Button>
          <Button size="small" color="error" onClick={() => setConfirm({ kind: 'members', id: member.id, name: member.display_name })}>Revoke access</Button>
        </Stack>}<Divider sx={{ mt: 2 }} /></Box>)}</Stack>
    </CardContent></Card><Card variant="outlined"><CardContent><Typography variant="h6" component="h3" sx={{ mb: 2 }}>Invitations</Typography>
      {!data.invitations.length && <Typography color="text.secondary">No invitations sent.</Typography>}
      <Stack spacing={2}>{data.invitations.map(inv => {
        const state = inv.accepted_at ? 'Accepted' : inv.revoked_at ? 'Revoked' : new Date(inv.expires_at) <= new Date() ? 'Expired' : 'Pending';
        return <Stack key={inv.id} direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1}><Box><Typography>{inv.email} · {inv.role}</Typography><Typography variant="body2" color="text.secondary">{state} · Expires {new Date(inv.expires_at).toLocaleString()}</Typography></Box>
          {state === 'Pending' && (inv.role !== 'primary' || patient.role === 'patient') && <Button color="error" onClick={() => setConfirm({ kind: 'invites', id: inv.id, name: inv.email })}>Revoke invitation</Button>}</Stack>;
      })}</Stack></CardContent></Card></>}
    <Dialog open={inviteOpen || !!editing} onClose={busy ? undefined : () => { setInviteOpen(false); setEditing(null); }} fullWidth maxWidth="sm"><form onSubmit={save}><DialogTitle>{editing ? `Edit access for ${editing.display_name}` : 'Invite a caregiver'}</DialogTitle><DialogContent><Stack spacing={2} sx={{ pt: 1 }}>
      {!editing && <TextField required type="email" name="email" label="Caregiver email" />}
      <TextField select label="Caregiver role" value={grant.role} onChange={e => { const role = e.target.value as Grant['role']; setGrant({ role, scopes: role === 'primary' ? [...grant.scopes.filter(s => s !== 'circle:manage'), 'circle:manage'] : grant.scopes.filter(s => !['circle:manage', 'privacy:manage'].includes(s)) }); }}>
        <MenuItem value="secondary">Secondary caregiver</MenuItem>{patient.role === 'patient' && <MenuItem value="primary">Primary caregiver</MenuItem>}</TextField>
      {grant.role === 'primary' && <Alert severity="info">A primary caregiver can manage secondary members within their own access. Only one primary caregiver can be active.</Alert>}
      <ScopePicker value={grant} onChange={setGrant} allowed={patient.scopes} />
      {!editing && <><TextField name="expires" type="number" label="Link expires in hours" defaultValue={48} inputProps={{ min: 1, max: 168 }} required /><FormControlLabel control={<Checkbox checked={consent} onChange={(_, v) => setConsent(v)} />} label="I authorize sharing the selected information with this person." /></>}
      {error && <Alert severity="error">{error}</Alert>}
    </Stack></DialogContent><DialogActions sx={{ p: 3 }}><Button disabled={busy} onClick={() => { setEditing(null); setInviteOpen(false); }}>Cancel</Button><Button type="submit" variant="contained" disabled={busy || (!editing && !consent)}>{editing ? 'Save access' : 'Create invitation'}</Button></DialogActions></form></Dialog>
    <Dialog open={!!confirm} onClose={busy ? undefined : () => setConfirm(null)}><DialogTitle>Revoke access?</DialogTitle><DialogContent><Typography>{confirm?.name} will no longer be able to use this {confirm?.kind === 'invites' ? 'invitation' : 'care-circle access'}. Restoring access requires a new invitation.</Typography></DialogContent><DialogActions><Button onClick={() => setConfirm(null)} disabled={busy}>Cancel</Button><Button color="error" onClick={revoke} disabled={busy}>Confirm revocation</Button></DialogActions></Dialog>
  </Stack>;
}
