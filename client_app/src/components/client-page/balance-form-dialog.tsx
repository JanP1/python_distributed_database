import { Button } from "@mui/material";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import TextField from '@mui/material/TextField';
import * as React from "react";

interface Props {
  open: boolean;
  handleClose: () => void;
  onSubmit: (amount: number) => void;
  title: string;
  description: string;
  balance: number;
}

const ChangeBalanceFormDialog: React.FC<Props> = ({
  open,
  handleClose,
  onSubmit,
  title,
  description,
  balance,
}) => {
  const[amount, setAmount] = React.useState<number | "">(0);
  const[error, setError] = React.useState<string>("");
  
  // resetuj stan kiedy dialog się otwiera
  React.useEffect(() => {
    if (open) {
      setAmount("");
      setError("");
    }
  }, [open]);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (amount === "" || isNaN(Number(amount))) {
      setError("Podaj poprawną kwotę!");
      return;
    } else if (Number(amount) <= 0) {
      setError("Kwota musi być większa od zera!");
      return;
    } else if (Number(amount) > balance) {
      setError("Nie możesz wypłacić więcej niż wynosi Twoje saldo!");
      return;
    }
      setError("");
      onSubmit(Number(amount));
      handleClose();
    
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      sx= {{
        '& .MuiPaper-root': {
          background: "#2f3535ff",
          overflow: "hidden",
        },
        '& .MuiBackdrop-root': {
          backgroundColor: 'transparent' 
        }

      }}
    >
      <DialogTitle sx={{marginLeft: "20px", color: "#ffffff"}}>
        {title}
      </DialogTitle>
      <DialogContent
        sx={{
          width: "600px",
          padding: "20px",
        }}
      >
        <DialogContentText
          sx={{
            marginLeft: "20px",
            color: "#ffffff",
          }}
        >
          {description}
        </DialogContentText>
        <form onSubmit={handleSubmit}>
          <TextField
            id="amount"
            label="Kwota"
            autoFocus
            margin="dense"
            type="number"
            variant="standard"
            value={amount}
            onFocus={() => {
              setAmount(""); 
            }}
            onChange={(e) => {
             setAmount(e.target.value === "" ? "" : Number(e.target.value));
             setError(""); // usuń błąd przy zmianie
            }}
            error={Boolean(error)} // włącza czerwony kolor obramowania
            helperText={error}
            sx={{marginLeft: "20px", width: "80%", color: "white"}}
          />
          <DialogActions
            sx={{
              margin: "20px",
              justifyContent: "center",
            }}
          >
            <Button 
              onClick={handleClose} 
              type="button"
              variant="text"
              sx={{
                color: "#e61515ff",
                margin: "20px",
                '&:hover': {
                  color: "white",
                  backgroundColor: "#830007ff", 
                },
              }}
            >
              Anuluj
            </Button>
            <Button 
              type="submit"
              variant="text"
              sx={{
                color: "#08ac34ff",
                margin: "20px",
                '&:hover': {
                  color: "white",
                  backgroundColor: "#067a25ff", 
                },
              }}
            >
              Zmień saldo
            </Button>
          </DialogActions>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default ChangeBalanceFormDialog;