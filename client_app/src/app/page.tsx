'use client'
import { Container, Grid, Stack, Typography, Alert } from "@mui/material";
import Balance from "../components/client-page/balance";
import ConsensusCluster from "../components/client-page/consensus-cluster";
import ConsensusLogs from "../components/client-page/consensus-logs";
import * as React from "react";

// Definicja typów kont
type AccountID = 'KONTO_A' | 'KONTO_B';
type OperationType = 'DEPOSIT' | 'WITHDRAW' | 'TRANSFER';

interface ConsensusClusterRef {
    proposeOperation: (
        amount: number, 
        operationType: OperationType, 
        sourceAccount: AccountID, 
        destinationAccount?: AccountID
    ) => Promise<Record<AccountID, number>>;
}

const NODE_PORTS = [8001, 8002, 8003, 8004];
const BASE_URL = "http://localhost";

export default function Home() {
    const consensusRef = React.useRef<ConsensusClusterRef>(null); 
    const [selectedAccount, setSelectedAccount] = React.useState<AccountID>('KONTO_A');
    const [resetCounter, setResetCounter] = React.useState(0);
    const [globalError, setGlobalError] = React.useState<string>("");

    const handleClusterReset = () => {
        console.log("Cluster zresetowany, odświeżam saldo...");
        setResetCounter(prev => prev + 1);
    };

  
    const handleInitialLoad = async (accountID: AccountID): Promise<number> => {
        
        for (const port of NODE_PORTS) {
            try {
                const response = await fetch(`${BASE_URL}:${port}/accounts`);
                if (response.ok) {
                    const data = await response.json();
                    return data[accountID] ?? 0;
                }
            } catch {
                continue; 
            }
        }
        
        
        console.warn("Nie udało się pobrać salda z backendu, używam wartości domyślnych.");
        return accountID === 'KONTO_A' ? 10000.00 : 5000.00;
    }

    
    const handleBalanceChange = async (
        amount: number, 
        operationType: OperationType, 
        sourceAccount: AccountID, 
        destinationAccount?: AccountID
    ): Promise<Record<AccountID, number>> => {
        setGlobalError("");

        if (!consensusRef.current) {
            setGlobalError("Klaster nie jest gotowy.");
            throw new Error("Klaster rozłączony");
        }

        
        return await consensusRef.current.proposeOperation(
            amount,
            operationType,
            sourceAccount,
            destinationAccount
        );
    };

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            <Typography variant="h3" align="center" sx={{ mb: 4 }}>
                System rozproszonych baz danych
            </Typography>
            
            {globalError && (
                <Alert severity="error" sx={{ mb: 2 }}>{globalError}</Alert>
            )}

            <Grid container spacing={3}>
                <Grid size={{ xs: 12, md: 8 }}>
                    <Stack spacing={4}>
                        <ConsensusCluster ref={consensusRef} onReset={handleClusterReset} />          
                        <Balance 
                            selectedAccount={selectedAccount}
                            onAccountChange={setSelectedAccount}
                            
                            allAccounts={['KONTO_A', 'KONTO_B']}
                            handleInitialLoad={handleInitialLoad}
                            handleBalanceChange={handleBalanceChange} 
                            refreshTrigger={resetCounter}
                        />
                    </Stack>
                </Grid>
                
                <Grid size={{ xs: 12, md: 4 }}>
                    <ConsensusLogs />
                </Grid>
            </Grid>
        </Container>
    );
}