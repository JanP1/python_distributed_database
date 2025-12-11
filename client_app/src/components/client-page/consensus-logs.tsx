'use client'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Stack,
  Chip,
  IconButton,
  Collapse,
} from "@mui/material";
import * as React from "react";

interface LogEntry {
  timestamp: string;
  node_id: number;
  level: string;
  message: string;
  algorithm: string;
}

const BASE_URL = "http://localhost";
const NODE_PORTS = [8001, 8002, 8003, 8004];

export default function ConsensusLogs() {
  const [logs, setLogs] = React.useState<LogEntry[]>([]);
  const [expanded, setExpanded] = React.useState(false);

  const fetchLogs = async () => {
    try {
      const logPromises = NODE_PORTS.map(async (port) => {
        try {
          const response = await fetch(`${BASE_URL}:${port}/consensus_logs`);
          if (!response.ok) return [];
          const data = await response.json();
          return data.logs || [];
        } catch {
          return [];
        }
      });

      const allLogs = await Promise.all(logPromises);
      const mergedLogs = allLogs.flat();

      mergedLogs.sort((a, b) => 
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      
      setLogs(mergedLogs.slice(0, 50));
    } catch (err) {
      console.error("Error fetching logs:", err);
    }
  };

  React.useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, []);

  type ChipColor = "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning";
  const getLevelColor = (level: string): ChipColor => {
    switch (level) {
      case "INFO": return "info";
      // PAXOS LOGS
      case "CONSENSUS": return "primary"; 
      case "PROMISE": return "secondary"; 
      case "ACCEPT": return "warning";    
      case "ACCEPTED": return "success";  
      case "REJECT": return "error"; 
      // RAFT LOGS
      case "LEADER": return "success"; 
      case "VOTE": return "secondary"; 
      case "COMMIT": return "primary"; 
      case "TERM": return "warning";

      case "PROPOSE": return "info";    
      case "ELECTION": return "warning";
      case "ERROR": return "error";
      case "SYSTEM": return "default";
      default: return "default";
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('pl-PL', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      fractionalSecondDigits: 3
    });
  };

  return (
    <Card sx={{ 
      backgroundColor: "#58a2a253", 
      color: "white",
      width: "100%"
    }}>
      <CardContent>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h5">
            Logi Konsensusu
          </Typography>
          <IconButton
            onClick={() => setExpanded(!expanded)}
            sx={{ color: "white" }}
            aria-label={expanded ? "Zwiń" : "Rozwiń"}
          >
            <Typography variant="h4" sx={{ lineHeight: 1 }}>
              {expanded ? "▲" : "▼"}
            </Typography>
          </IconButton>
        </Stack>
        
        <Collapse in={expanded}>
          <Box sx={{ 
            mt: 2, 
            maxHeight: "400px", 
            overflowY: "auto",
            backgroundColor: "rgba(7, 75, 75, 0.3)",
            borderRadius: "8px",
            padding: "10px"
          }}>
            {logs.length === 0 ? (
              <Typography variant="body2" sx={{ color: "rgba(255, 255, 255, 0.7)" }}>
                Brak logów...
              </Typography>
            ) : (
              <Stack spacing={1}>
                {logs.map((log, index) => (
                  <Box
                    key={index}
                    sx={{
                      padding: "8px",
                      backgroundColor: "rgba(0, 0, 0, 0.2)",
                      borderRadius: "4px",
                      
                      borderLeft: `3px solid ${
                        log.level === "ERROR" || log.level === "REJECT" ? "#f44336" :
                        log.level === "ACCEPTED" || log.level === "LEADER" ? "#4caf50" : 
                        log.level === "PROPOSE" ? "#0288d1" :  
                        log.level === "PROMISE" || log.level === "VOTE" ? "#9c27b0" :  
                        log.level === "ACCEPT" || log.level === "ELECTION" || log.level === "TERM" ? "#ff9800" : 
                        log.level === "CONSENSUS" || log.level === "COMMIT" ? "#2196f3" :
                        log.level === "SYSTEM" ? "#ffffff" :
                        "#9e9e9e"
                      }`
                    }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                      <Typography variant="caption" sx={{ color: "rgba(255, 255, 255, 0.6)" }}>
                        {formatTime(log.timestamp)}
                      </Typography>
                      <Chip 
                        label={`Node ${log.node_id}`} 
                        size="small"
                        sx={{ 
                          height: "20px",
                          fontSize: "0.7rem",
                          backgroundColor: "rgba(255, 255, 255, 0.2)"
                        }}
                      />
                      <Chip 
                        label={log.level} 
                        size="small"
                        color={getLevelColor(log.level)} 
                        sx={{ height: "20px", fontSize: "0.7rem" }}
                      />
                      <Chip 
                        label={log.algorithm.toUpperCase()} 
                        size="small"
                        sx={{ 
                          height: "20px",
                          fontSize: "0.7rem",
                          backgroundColor: "rgba(255, 255, 255, 0.15)"
                        }}
                      />
                    </Stack>
                    <Typography variant="body2" sx={{ mt: 0.5, fontSize: "0.85rem" }}>
                      {log.message}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            )}
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
}
