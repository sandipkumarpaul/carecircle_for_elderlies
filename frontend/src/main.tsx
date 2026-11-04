import React from 'react';
import ReactDOM from 'react-dom/client';
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material';
import App from './App';
const theme = createTheme({
  palette: { primary: { main: '#17645b' }, background: { default: '#f5f8f6' } },
  typography: { fontFamily: 'system-ui, sans-serif', h1: { fontSize: 'clamp(2.3rem, 5vw, 3.6rem)', fontWeight: 750, letterSpacing: '-0.04em' } },
  shape: { borderRadius: 14 },
  components: { MuiButton: { styleOverrides: { root: { textTransform: 'none', fontWeight: 650 } } } },
});
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><ThemeProvider theme={theme}><CssBaseline /><App /></ThemeProvider></React.StrictMode>);
