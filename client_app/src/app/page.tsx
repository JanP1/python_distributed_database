'use client'
import { Box, Container, Grid, Stack, Typography } from "@mui/material";
import Balance from "../components/client-page/balance";
import ConsensusCluster from "../components/client-page/consensus-cluster";
import ConsensusLogs from "../components/client-page/consensus-logs";
import * as React from "react";

export default function Home() {
  const consensusRef = React.useRef<{ proposeOperation: (operation: string) => Promise<void> }>(null);

  const handleBalanceChange = async (operation: string) => {
    if (consensusRef.current) {
      await consensusRef.current.proposeOperation(operation);
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Typography variant="h3" align="center" sx={{ mb: 4 }}>
        Distributed Database System
      </Typography>
      
      <Grid container spacing={3}>
        {/* Lewa kolumna - główne komponenty */}
        <Grid item xs={12} md={8}>
          <Stack spacing={4}>
            <ConsensusCluster ref={consensusRef} />
            <Balance onBalanceChange={handleBalanceChange} />
          </Stack>
        </Grid>
        
        {/* Prawa kolumna - panel logów konsensusu */}
        <Grid item xs={12} md={4}>
          <ConsensusLogs />
        </Grid>
      </Grid>
    </Container>
  );
}
