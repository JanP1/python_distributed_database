'use client'
import {
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  SelectChangeEvent,
  Stack,
  Typography,
  Chip,
  Alert,
} from "@mui/material";
import * as React from "react";

type AccountID = 'KONTO_A' | 'KONTO_B';
type OperationType = 'DEPOSIT' | 'WITHDRAW' | 'TRANSFER';


interface NodeStatus {
  node_id: number;
  algorithm?: string;
  role?: string;
  term?: number;
  leader?: string;
  ip?: string;
  log_size: number;
  promised_id?: string;
}

interface ConsensusClusterProps {
  onReset?: () => void;
}

const BASE_URL = "http://localhost";
const NODE_PORTS = [8001, 8002, 8003, 8004];

const ConsensusCluster = React.forwardRef<
  { proposeOperation: (
    amount: number,
    operationType: OperationType,
    sourceAccount: AccountID,
    destinationAccount?: AccountID,
  ) => Promise<Record<AccountID, number>> },
  ConsensusClusterProps
>((props, ref) => {
  const [algorithm, setAlgorithm] = React.useState<string>("paxos");
  const [nodes, setNodes] = React.useState<NodeStatus[]>([]);
  const [loading, setLoading] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string>("");

  const fetchClusterStatus = React.useCallback(async () => { 
    const fetchNodeStatus = async (port: number): Promise<NodeStatus | null> => {
      try {
        const response = await fetch(`${BASE_URL}:${port}/status`);
        if (!response.ok) return null;
        return await response.json();
      } catch{
        return null;
      }
    };

    setLoading(true);
    setError("");
    try {
      const statusPromises = NODE_PORTS.map((port) => fetchNodeStatus(port));
      const statuses = await Promise.all(statusPromises);
      const validStatuses = statuses.filter((s) => s !== null) as NodeStatus[];
      
      if (validStatuses.length === 0) {
        setError("Nie można połączyć się z żadnym węzłem. Upewnij się, że Docker containers są uruchomione.");
      } else {
        setNodes(validStatuses);
        if (validStatuses[0].algorithm) {
          setAlgorithm(validStatuses[0].algorithm);
        }
      }
    } catch{
      setError("Błąd podczas pobierania statusu klastra");
    } finally {
      setLoading(false);
    }
  }, []);

  const proposeOperation = async (
    amount: number,
    operationType: OperationType,
    sourceAccount: AccountID,
    destinationAccount?: AccountID
  ): Promise<Record<AccountID, number>> => {
    setLoading(true);
    setError("");
    try {
      // Znajdź lidera dla Rafta lub użyj jednego węzła dla Paxos
      let targetPort = 8001;
      
      if (algorithm === "raft") {
        const leader = nodes.find((n) => n.role === "leader");
        if (leader) {
          targetPort = 8000 + leader.node_id;
        } else {
          throw new Error("Brak lidera w klastrze Raft. Poczekaj na wybór lidera.");
        }
      } else if (algorithm === "paxos") {
        if (nodes.length === 0) {
          throw new Error("Brak dostępnych węzłów Paxos.");
        }
        targetPort = 8000 + nodes[0].node_id;
      }

      let operationString: string;

      if (operationType === 'TRANSFER' && destinationAccount) {
                // TRANSFER;KONTO_A;KONTO_B;100.00;TX_ID:T[timestamp]
                const txId = `T${Date.now()}`;
                operationString = `${operationType};${sourceAccount};${destinationAccount};${amount.toFixed(2)};TX_ID:${txId}`;
            } else {
                // DEPOSIT/WITHDRAW;KONTO_A;100.00;TX_ID:T[timestamp]
                const txId = `T${Date.now()}`;
                operationString = `${operationType};${sourceAccount};${amount.toFixed(2)};TX_ID:${txId}`;
      }

      console.log(`Wysyłanie operacji do portu ${targetPort}:`, operationString);

      const response = await fetch(`${BASE_URL}:${targetPort}/propose`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ operation: operationString}),
      });

      console.log("Odpowiedź:", response.status, response.statusText);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: "Nieznany błąd" }));
        throw new Error(errorData.error || `Błąd HTTP ${response.status}: ${response.statusText}`);
      } 
      const result = await response.json();

      if (result && result.success === false) {
        throw new Error(result.error || "Operacja zakończona niepowodzeniem po stronie serwera.");
      }

      if(result && (result.new_state || result.success === true)) {
        console.log("Sukces:", result);
        setTimeout(() => fetchClusterStatus(), 500);
        return result.new_state || {};
      }
      console.warn("Otrzymano nieoczekiwaną odpowiedź:", result);
      throw new Error("Nieprawidłowa struktura odpowiedzi z serwera.");
    } catch (err: unknown) {
      console.error("Błąd podczas wysyłania operacji:", err);
      setError(`Błąd podczas wysyłania operacji: ${err instanceof Error ? err.message : String(err)}`);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const handleAlgorithmChange = async (event: SelectChangeEvent<string>) => {
    const newAlgorithm = event.target.value;
    setLoading(true);
    setError("");
    
    try {
      const switchPromises = NODE_PORTS.map((port) =>
        fetch(`${BASE_URL}:${port}/switch_algorithm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ algorithm: newAlgorithm }),
        })
      );
      
      await Promise.all(switchPromises);
      setAlgorithm(newAlgorithm);
      // Zaczekaj chwilę na reinicjalizację węzłów
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await fetchClusterStatus();
      if (props.onReset) {
        props.onReset();
      }
    } catch (err) {
      setError(`Błąd podczas zmiany algorytmu: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    setError("");
    
    try {
      const resetPromises = NODE_PORTS.map((port) =>
        fetch(`${BASE_URL}:${port}/reset`, {
          method: "POST",
        })
      );
      
      await Promise.all(resetPromises);
      
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await fetchClusterStatus();

      if (props.onReset) {
        props.onReset();
      }

    } catch (err) {
      setError(`Błąd podczas resetowania: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  React.useImperativeHandle(ref, () => ({
    proposeOperation,
  }));

  React.useEffect(() => {
    fetchClusterStatus();
    const interval = setInterval(fetchClusterStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchClusterStatus]);

  const getNodeColor = (node: NodeStatus) => {
    if (algorithm === "raft") {
      if (node.role === "leader") return "success";
      if (node.role === "candidate") return "warning";
      return "info";
    }
    return "default";
  };

  return (
    <Card sx={{ maxWidth: 800, padding: "20px", backgroundColor: "#58a2a253", color: "white" }}>
      <CardContent>
        <Typography gutterBottom variant="h4" component="div">
          Distributed Database Cluster
        </Typography>
        <Typography variant="body2" sx={{ color: "rgba(255, 255, 255, 0.84)", mb: 2 }}>
          Zarządzanie klastrem z algorytmami konsensusu Raft i Paxos
        </Typography>

        <Stack direction="row" spacing={3} alignItems="flex-start" sx={{ mb: 3 }}>
          <Box sx={{ flex: 1 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
          </Box>
          
          <FormControl sx={{ minWidth: 200 }}>
            <InputLabel 
              id="algorithm-select-label"
              sx={{ color: "white", "&.Mui-focused": { color: "white" } }}
            >
              Algorytm konsensusu
            </InputLabel>
            <Select
              labelId="algorithm-select-label"
              value={algorithm}
              label="Algorytm konsensusu"
              onChange={handleAlgorithmChange}
              disabled={loading}
              sx={{
                color: "white",
                ".MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255, 255, 255, 0.5)" },
                "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: "white" },
                "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: "white" },
                ".MuiSvgIcon-root": { color: "white" },
              }}
            >
              <MenuItem value="raft">Raft</MenuItem>
              <MenuItem value="paxos">Paxos</MenuItem>
            </Select>
          </FormControl>
        </Stack>

        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Status węzłów:
          </Typography>
          <Stack spacing={2}>
            {nodes.length === 0 && !loading && (
              <Typography>Brak połączenia z węzłami...</Typography>
            )}
            {nodes.map((node) => (
              <Box
                key={node.node_id}
                sx={{
                  padding: "15px",
                  backgroundColor: "rgba(7, 75, 75, 0.5)",
                  borderRadius: "8px",
                }}
              >
                <Stack direction="row" spacing={2} alignItems="center">
                  <Typography variant="h6">Node {node.node_id}</Typography>
                  <Chip
                    label={node.algorithm?.toUpperCase() || "N/A"}
                    color="primary"
                    size="small"
                  />
                  {algorithm === "raft" && node.role && (
                    <Chip
                      label={node.role.toUpperCase()}
                      color={getNodeColor(node)}
                      size="small"
                    />
                  )}
                  {algorithm === "raft" && node.term !== undefined && (
                    <Typography variant="body2">Term: {node.term}</Typography>
                  )}
                  {algorithm === "paxos" && node.promised_id && (
                    <Typography variant="body2">Promised: {node.promised_id}</Typography>
                  )}
                  <Typography variant="body2">Log: {node.log_size} entries</Typography>
                </Stack>
              </Box>
            ))}
          </Stack>
        </Box>

        <Stack direction="row" spacing={2} justifyContent="center">
          <Button
            variant="contained"
            size="large"
            onClick={fetchClusterStatus}
            disabled={loading}
            sx={{
              color: "white",
              fontWeight: "400",
              backgroundColor: "#067a25ff",
              "&:hover": {
                backgroundColor: "#078c2aff",
              },
            }}
          >
            Odśwież Status
          </Button>
          <Button
            variant="contained"
            size="large"
            onClick={handleReset}
            disabled={loading}
            sx={{
              color: "white",
              fontWeight: "400",
              backgroundColor: "#d32f2fff",
              "&:hover": {
                backgroundColor: "#f44336ff",
              },
            }}
          >
            Zresetuj
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
});

ConsensusCluster.displayName = "ConsensusCluster";

export default ConsensusCluster;
