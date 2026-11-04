import { Checkbox, FormControlLabel, FormGroup, Typography } from '@mui/material';
import { Grant, scopeLabels } from '../lib/types';
export function ScopePicker({ value, onChange, allowed }: { value: Grant; onChange: (v: Grant) => void; allowed: string[] }) {
  return <><Typography variant="body2" color="text.secondary">Choose what this person may access. Manage permissions also include viewing that category.</Typography>
    <FormGroup sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
      {Object.entries(scopeLabels).filter(([key]) => allowed.includes(key) && (value.role === 'primary' || !['circle:manage', 'privacy:manage'].includes(key)))
        .map(([key, label]) => <FormControlLabel key={key} label={label} control={<Checkbox checked={value.scopes.includes(key)} disabled={key === 'circle:manage' && value.role === 'primary'}
          onChange={(_, checked) => onChange({ ...value, scopes: checked ? [...value.scopes, key] : value.scopes.filter(s => s !== key) })} />} />)}
    </FormGroup></>;
}
