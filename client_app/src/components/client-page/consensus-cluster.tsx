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

interface ConsensusClusterProps {}

const ConsensusCluster = React.forwardRef<
  { proposeOperation: (operation: string) => Promise<void> },
  ConsensusClusterProps
>((props, ref) => {
  const [algorithm, setAlgorithm] = React.useState<string>("paxos");
  const [nodes, setNodes] = React.useState<NodeStatus[]>([]);
  const [loading, setLoading] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string>("");

  const BASE_URL = "http://localhost";
  const NODE_PORTS = [8001, 8002, 8003, 8004];

  const fetchNodeStatus = async (port: number): Promise<NodeStatus | null> => {
    try {
      const response = await fetch(`${BASE_URL}:${port}/status`);
      if (!response.ok) return null;
      return await response.json();
    } catch (err) {
      return null;
    }
  };

  const fetchClusterStatus = async () => {
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
    } catch (err) {
      setError("Błąd podczas pobierania statusu klastra");
    } finally {
      setLoading(false);
    }
  };

  const proposeOperation = async (operation: string) => {
    setLoading(true);
    setError("");
    try {
      // Find leader for Raft, or use node 1 for Paxos
      let targetPort = 8001;
      
      if (algorithm === "raft") {
        const leader = nodes.find((n) => n.role === "leader");
        if (leader) {
          targetPort = 8000 + leader.node_id;
        } else {
          setError("Brak lidera w klastrze Raft. Poczekaj na wybór lidera.");
          setLoading(false);
          return;
        }
      }

      console.log(`Wysyłanie operacji do portu ${targetPort}:`, operation);

      const response = await fetch(`${BASE_URL}:${targetPort}/propose`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ operation }),
      });

      console.log("Odpowiedź:", response.status, response.statusText);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: "Nieznany błąd" }));
        setError(errorData.error || `Błąd HTTP ${response.status}: ${response.statusText}`);
      } else {
        const result = await response.json();
        console.log("Sukces:", result);
        // Refresh cluster status after successful operation
        setTimeout(() => fetchClusterStatus(), 500);
      }
    } catch (err) {
      console.error("Błąd podczas wysyłania operacji:", err);
      setError(`Błąd podczas wysyłania operacji: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAlgorithmChange = async (event: SelectChangeEvent<string>) => {
    const newAlgorithm = event.target.value;
    setLoading(true);
    setError("");
    
    try {
      // Send switch request to all nodes
      const switchPromises = NODE_PORTS.map((port) =>
        fetch(`${BASE_URL}:${port}/switch_algorithm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ algorithm: newAlgorithm }),
        })
      );
      
      await Promise.all(switchPromises);
      setAlgorithm(newAlgorithm);
      
      // Wait a bit for nodes to reinitialize
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await fetchClusterStatus();
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
      // Send reset request to all nodes
      const resetPromises = NODE_PORTS.map((port) =>
        fetch(`${BASE_URL}:${port}/reset`, {
          method: "POST",
        })
      );
      
      await Promise.all(resetPromises);
      
      // Wait a bit for nodes to reinitialize
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await fetchClusterStatus();
    } catch (err) {
      setError(`Błąd podczas resetowania: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  // Expose proposeOperation via ref
  React.useImperativeHandle(ref, () => ({
    proposeOperation,
  }));

  React.useEffect(() => {
    fetchClusterStatus();
    const interval = setInterval(fetchClusterStatus, 5000);
    return () => clearInterval(interval);
  }, []);

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
