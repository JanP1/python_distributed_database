'use client';

import * as React from 'react';
import { CacheProvider } from '@emotion/react';
import { ThemeProvider, CssBaseline } from '@mui/material';
import createEmotionCache from './createEmotionCache';
import { createTheme } from '@mui/material/styles';

const clientSideEmotionCache = createEmotionCache();
const theme = createTheme({
  palette: {
    mode: 'dark',
    background: { default: '#052929' },
    primary: { main: '#08ac34' },
  },
});

export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  return (
    <CacheProvider value={clientSideEmotionCache}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </CacheProvider>
  );
}
