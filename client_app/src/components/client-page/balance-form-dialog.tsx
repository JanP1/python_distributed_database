'use client'
import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, TextField, Typography } from "@mui/material";
import * as React from "react";

interface ChangeBalanceFormDialogProps {
    open: boolean;
    handleClose: () => void;
    onSubmit: (amount: number) => Promise<void>; 
    title: string;
    description: string;
    balance: number;
}

const ChangeBalanceFormDialog: React.FunctionComponent<ChangeBalanceFormDialogProps> = ({ 
    open, handleClose, onSubmit, title, description, balance
}) => {
    const [amount, setAmount] = React.useState<number | ''>('');
    const [error, setError] = React.useState<string | null>(null);

    const handleSubmit = async () => {
        if (typeof amount !== 'number' || amount <= 0) {
            setError("Wprowadź poprawną, dodatnią kwotę.");
            return;
        }

        try {
            await onSubmit(amount); 
            setAmount(''); 
            setError(null);
            handleClose();
        } catch (e) {
            console.error("Błąd wysyłania transakcji z dialogu:", e);
        }
    };

    return (
        <Dialog open={open} onClose={handleClose}>
            <DialogTitle>{title}</DialogTitle>
            <DialogContent>
                <DialogContentText sx={{ mb: 2 }}>
                    {description}
                </DialogContentText>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 2 }}>
                    Dostępne środki: <strong>{balance.toFixed(2)} PLN</strong>
                </Typography>
                <TextField
                    autoFocus
                    margin="dense"
                    id="amount"
                    label="Kwota"
                    type="number"
                    fullWidth
                    variant="standard"
                    value={amount}
                    onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setAmount(isNaN(val) ? '' : val);
                        setError(null);
                    }}
                    error={!!error}
                    helperText={error}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Anuluj</Button>
                <Button onClick={handleSubmit} disabled={!amount || amount <= 0}>Potwierdź</Button>
            </DialogActions>
        </Dialog>
    );
};

export default ChangeBalanceFormDialog;