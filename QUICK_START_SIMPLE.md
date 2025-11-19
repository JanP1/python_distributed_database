# Quick Start

## Wymagania
- Docker Desktop
- Node.js 18+

## Uruchomienie

### 1. Backend (Docker)
```powershell
docker-compose up -d --build
```

### 2. Frontend
```powershell
cd client_app
npm install
npm run dev
```

### 3. Otwórz
```
http://localhost:3000
```

## Zatrzymanie

```powershell
docker-compose down
```

---

## Podstawowe komendy testowe

### Status węzłów
```powershell
Invoke-WebRequest http://localhost:8001/status -UseBasicParsing
```

### Wyślij operację
```powershell
Invoke-WebRequest "http://localhost:8001/propose" -Method POST -Body '{"operation":"TEST"}' -ContentType "application/json" -UseBasicParsing
```

### Reset węzłów
```powershell
1..4 | ForEach-Object { Invoke-WebRequest "http://localhost:800$_/reset" -Method POST -UseBasicParsing }
```

### Logi Docker
```powershell
docker logs consensus_node1 -f
```
