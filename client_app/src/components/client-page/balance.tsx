'use client'
import { Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import * as React from "react";
import ChangeBalanceFormDialog from "./balance-form-dialog";

interface BalanceProps {
  onBalanceChange?: (operation: string) => Promise<void>;
}

const Balance: React.FunctionComponent<BalanceProps> = ({ onBalanceChange }) => {

  const[depositDialog, setDepositDialog] = React.useState(false);

  const[withdrawDialog, setWithdrawDialog] = React.useState(false);

  const[balance, setBalance] = React.useState<number>(10000);

  const handleSubmitIncrease = async (amount: number) => {
    const newBalance = balance + amount;
    setBalance(newBalance);
    
    // Send operation to consensus cluster
    if (onBalanceChange) {
      const operation = `DEPOSIT ${amount} PLN, new balance: ${newBalance} PLN`;
      await onBalanceChange(operation);
    }
  }

  const handleSubmitDecrease = async (amount: number) => {
    const newBalance = balance - amount;
    setBalance(newBalance);
    
    // Send operation to consensus cluster
    if (onBalanceChange) {
      const operation = `WITHDRAW ${amount} PLN, new balance: ${newBalance} PLN`;
      await onBalanceChange(operation);
    }
  }

  return (
    <Card sx={{maxWidth: 600, padding: "20px", backgroundColor: "#58a2a253", color: "white"}}>
        <CardContent>
          <Typography gutterBottom variant="h5" component="div"> 
            Saldo dostępne na twoim koncie bankowym.
          </Typography>
          <Typography variant="body2" sx={{ color: "rgba(255, 255, 255, 0.84)" }}>
            Poniżej jest twoje saldo konta, jeśli chcesz wpłacić lub wypłacić pieniądze naciśnij odpowiedni przycisk.
          </Typography>
        </CardContent>
        <Box sx={{padding: "20px", backgroundColor: "rgba(7, 75, 75, 1)", borderRadius: "8px"}}>
          <Typography variant="h2" component="h2" fontWeight={700} align="center">
            {balance} PLN
          </Typography>
        </Box>
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="center"
        >
          <Button
            variant="contained"
            size="large"
            onClick={() => setWithdrawDialog(true)}
            sx={{
              color: "white",
              fontWeight: "400",
              backgroundColor: "#a41414ff",
              margin: "20px",
              '&:hover': {
                backgroundColor: "#c61a1aff", 
              },
            }}
          >
            Wypłać
          </Button>

          <ChangeBalanceFormDialog 
            open={withdrawDialog}
            handleClose={() => setWithdrawDialog(false)}
            onSubmit={handleSubmitDecrease}
            title="Wypłać wybraną kwotę"
            description="Wpisz kwotę, którą chcesz wypłacić ze swojego konta bankowego."
            balance={balance}
          />

          <Button
            variant="contained"
            size="large"
            onClick={() => setDepositDialog(true)}
            sx={{
              color: "white",
              fontWeight: "400",
              backgroundColor: "#067a25ff",
              margin: "20px",
              '&:hover': {
                backgroundColor: "#078c2aff", 
              },
            }}
          >
            Wpłać
          </Button>

          <ChangeBalanceFormDialog 
            open={depositDialog}
            handleClose={() => setDepositDialog(false)}
            onSubmit={handleSubmitIncrease}
            title="Wpłać wybraną kwotę"
            description="Wpisz kwotę, którą chcesz wpłacić na swoje konto bankowe."
            balance={balance}
          />

        </Stack>
      </Card>
  );
};

export default Balance;