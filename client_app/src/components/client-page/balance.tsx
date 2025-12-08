'use client'
import { Box, Button, Card, CardContent, Stack, Typography, Select, SelectChangeEvent, MenuItem, FormControl, InputLabel } from "@mui/material";
import * as React from "react";
import ChangeBalanceFormDialog from "./balance-form-dialog";
import TransferFormDialog from "./transfer-form-dialog"; 

type AccountID = 'KONTO_A' | 'KONTO_B';
type OperationType = 'DEPOSIT' | 'WITHDRAW' | 'TRANSFER';

interface BalanceProps {
    selectedAccount: AccountID;
    onAccountChange: (account: AccountID) => void;
    allAccounts: AccountID[];
    handleInitialLoad: (accountID: AccountID) => Promise<number>;
    handleBalanceChange: (
        amount: number, 
        operationType: OperationType, 
        sourceAccount: AccountID, 
        destinationAccount?: AccountID
    ) => Promise<Record<AccountID, number>>; 
    refreshTrigger?: number;
}

const Balance: React.FunctionComponent<BalanceProps> = ({ 
    selectedAccount, 
    onAccountChange, 
    allAccounts,
    handleInitialLoad, 
    handleBalanceChange,
    refreshTrigger
}) => {

    const [depositDialog, setDepositDialog] = React.useState(false);
    const [withdrawDialog, setWithdrawDialog] = React.useState(false);
    const [transferDialog, setTransferDialog] = React.useState(false); 
    
    const [balances, setBalances] = React.useState<Record<string, number>>({});
    
    const [isLoading, setIsLoading] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);

    const currentBalance = balances[selectedAccount];

    React.useEffect(() => {
        if (balances[selectedAccount] !== undefined) {
            return; 
        }
        const fetchBalance = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const fetchedBalance = await handleInitialLoad(selectedAccount);
                
                setBalances(prev => ({
                    ...prev,
                    [selectedAccount]: fetchedBalance
                }));
            } catch (e) {
                console.error("Błąd ładowania salda:", e);
                if (balances[selectedAccount] === undefined) {
                    setError("Nie udało się pobrać salda.");
                }
            } finally {
                setIsLoading(false);
            }
        };

        fetchBalance();
    }, [selectedAccount, handleInitialLoad, refreshTrigger, balances]); 

    React.useEffect(() => {
        if (refreshTrigger !== undefined) {
            setBalances({}); 
        }
    }, [refreshTrigger]);

    const handleSubmitOperation = async (
        amount: number, 
        type: OperationType, 
        destinationAccount?: AccountID
    ) => {
        setDepositDialog(false);
        setWithdrawDialog(false);
        setTransferDialog(false);
        
        setError(null);
        setIsLoading(true);

        try {
            const newAccountsState = await handleBalanceChange(
                amount, 
                type, 
                selectedAccount, 
                destinationAccount
            );

            // Aktualizacja kont
            if (newAccountsState) {
                setBalances(prev => ({
                    ...prev,
                    ...newAccountsState 
                }));
            } else {
                const refreshedBalance = await handleInitialLoad(selectedAccount);
                setBalances(prev => ({
                    ...prev,
                    [selectedAccount]: refreshedBalance
                }));
            }

        } catch (e: unknown) {
            console.error("Błąd transakcji:", e);
            const errorMessage = e instanceof Error ? e.message : String(e);
            setError(errorMessage || "Wystąpił nieznany błąd transakcji.");
        } finally {
            setIsLoading(false);
        }
    }

    const handleSubmitIncrease = async (amount: number) => await handleSubmitOperation(amount, 'DEPOSIT');
    const handleSubmitDecrease = async (amount: number) => {
        const currentFunds = balances[selectedAccount] ?? 0;
        
        if (amount > currentFunds) {
            setWithdrawDialog(false); 
            setError("Operacja odrzucona: Brak wystarczających środków na koncie.");
            return; 
        }
        
        await handleSubmitOperation(amount, 'WITHDRAW');
    }
    const handleSubmitTransfer = async (amount: number, destination: AccountID) => {
        const currentFunds = balances[selectedAccount] ?? 0;

        if (amount > currentFunds) {
            setTransferDialog(false);
            setError("Przelew odrzucony: Brak wystarczających środków na koncie źródłowym.");
            return; 
        }

        await handleSubmitOperation(amount, 'TRANSFER', destination);
    }

    const handleAccountSelectionChange = (event: SelectChangeEvent) => {
        onAccountChange(event.target.value as AccountID);
    }
    
    return (
        <Card sx={{ maxWidth: 600, padding: "20px", backgroundColor: "#58a2a253", color: "white"}}>
            <CardContent>
                <Typography gutterBottom variant="h5" component="div"> 
                    Zarządzanie kontem bankowym
                </Typography>
                <FormControl fullWidth variant="filled" sx={{mb: 2, backgroundColor: 'rgba(255,255,255,0.1)'}}>
                    <InputLabel id="account-select-label" sx={{color: 'white'}}>Wybierz Konto</InputLabel>
                    <Select
                        labelId="account-select-label"
                        value={selectedAccount}
                        onChange={handleAccountSelectionChange}
                        label="Wybierz Konto"
                        sx={{color: 'white', '& .MuiSelect-icon': { color: 'white' }}}
                    >
                        {allAccounts.map(account => (
                            <MenuItem key={account} value={account}>{account}</MenuItem>
                        ))}
                    </Select>
                </FormControl>
                
                {error && (
                    <Box sx={{ color: 'white', backgroundColor: '#c61a1a', padding: '10px', borderRadius: '4px', mb: 2 }}>
                        {error}
                    </Box>
                )}
            </CardContent>
            <Box sx={{padding: "20px", backgroundColor: "rgba(7, 75, 75, 1)", borderRadius: "8px"}}>
                <Typography variant="h2" component="h2" fontWeight={700} align="center">
                    {isLoading && currentBalance === undefined 
                        ? 'Ładowanie...' 
                        : currentBalance !== undefined 
                            ? `${currentBalance.toFixed(2)} PLN` 
                            : 'Błąd/Brak danych'}
                </Typography>
                <Typography variant="body1" align="center" sx={{mt: 1}}>
                    Aktualnie wybrane konto: {selectedAccount}
                </Typography>
            </Box>
            <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-around"
                sx={{mt: 2}}
            >
                <Button variant="contained" onClick={() => setWithdrawDialog(true)} 
                  disabled={isLoading || currentBalance === undefined} 
                  sx={{color: "white", fontWeight: "400", backgroundColor: "#a41414ff", margin: "20px", '&:hover': {backgroundColor: "#c61a1aff",}}}
                >Wypłać</Button>
                
                <ChangeBalanceFormDialog 
                    open={withdrawDialog} handleClose={() => setWithdrawDialog(false)} onSubmit={handleSubmitDecrease} 
                    title="Wypłać wybraną kwotę" description={`Wypłać z ${selectedAccount}.`} 
                    balance={currentBalance ?? 0}
                />
                
                <Button variant="contained" onClick={() => setDepositDialog(true)} 
                  disabled={isLoading || currentBalance === undefined} 
                  sx={{ color: "white", fontWeight: "400", backgroundColor: "#067a25ff", margin: "20px", '&:hover': { backgroundColor: "#078c2aff", },}} 
                >Wpłać</Button>
                
                <ChangeBalanceFormDialog 
                    open={depositDialog} handleClose={() => setDepositDialog(false)} onSubmit={handleSubmitIncrease} 
                    title="Wpłać wybraną kwotę" description={`Wpłać na ${selectedAccount}.`} 
                    balance={currentBalance ?? 0}
                />
                
                <Button variant="contained" onClick={() => setTransferDialog(true)} 
                  disabled={isLoading || currentBalance === undefined} 
                  color="warning">Przelej</Button>

                <TransferFormDialog
                    open={transferDialog}
                    handleClose={() => setTransferDialog(false)}
                    onSubmit={handleSubmitTransfer}
                    title="Wykonaj Przelew"
                    description={`Przelew z ${selectedAccount} na inne konto.`}
                    sourceAccount={selectedAccount}
                    allAccounts={allAccounts}
                    balance={currentBalance ?? 0}
                />
            </Stack>
        </Card>
    );
};

export default Balance;