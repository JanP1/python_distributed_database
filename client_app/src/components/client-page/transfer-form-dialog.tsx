'use client'
import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, TextField, Select, MenuItem, Typography, FormControl, InputLabel } from "@mui/material";
import * as React from "react";

type AccountID = 'KONTO_A' | 'KONTO_B';

interface TransferFormDialogProps {
    open: boolean;
    handleClose: () => void;
    onSubmit: (amount: number, destination: AccountID) => Promise<void>; 
    title: string;
    description: string;
    sourceAccount: AccountID;
    allAccounts: AccountID[];
    balance: number;
}

const TransferFormDialog: React.FunctionComponent<TransferFormDialogProps> = ({ 
    open, handleClose, onSubmit, title, description, sourceAccount, allAccounts, balance
}) => {
    const [amount, setAmount] = React.useState<number | ''>('');
    const [destinationAccount, setDestinationAccount] = React.useState<AccountID | ''>('');
    const [error, setError] = React.useState<string | null>(null);

    React.useEffect(() => {
        
        if (open) {
            setAmount('');
            setDestinationAccount('');
            setError(null);
        }
    }, [open]);

    const handleSubmit = async () => {
        if (typeof amount !== 'number' || amount <= 0) {
            setError("Wprowadź poprawną, dodatnią kwotę.");
            return;
        }
        if (!destinationAccount) {
            setError("Wybierz konto docelowe.");
            return;
        }        
        try {
            await onSubmit(amount, destinationAccount as AccountID); 
            handleClose();
        } catch (e) {
             console.error("Błąd wysyłania przelewu:", e);
        }
    };

    const availableDestinations = allAccounts.filter(acc => acc !== sourceAccount);

    return (
        <Dialog open={open} onClose={handleClose}>
            <DialogTitle>{title}</DialogTitle>
            <DialogContent>
                <DialogContentText sx={{ mb: 2 }}>
                    {description}
                </DialogContentText>
                
                {error && <DialogContentText color="error">{error}</DialogContentText>}

                <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 2 }}>
                    Dostępne środki: <strong>{balance.toFixed(2)} PLN</strong>
                </Typography>

                <FormControl fullWidth margin="dense" variant="standard">
                    <InputLabel id="destination-select-label">Konto Docelowe</InputLabel>
                    <Select
                        labelId="destination-select-label"
                        value={destinationAccount}
                        onChange={(e) => setDestinationAccount(e.target.value as AccountID)}
                        label="Konto Docelowe"
                    >
                        {availableDestinations.map(acc => (
                            <MenuItem key={acc} value={acc}>{acc}</MenuItem>
                        ))}
                    </Select>
                </FormControl>

                <TextField
                    margin="dense"
                    id="amount"
                    label="Kwota Przelewu"
                    type="number"
                    fullWidth
                    variant="standard"
                    value={amount}
                    onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setAmount(isNaN(val) ? '' : val);
                    }}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Anuluj</Button>
                <Button onClick={handleSubmit} disabled={!amount || amount <= 0 || !destinationAccount}>Potwierdź Przelew</Button>
            </DialogActions>
        </Dialog>
    );
};

export default TransferFormDialog;