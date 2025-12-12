# Quick Start

## Wymagania
- Zainstalowany i uruchomiony **Docker Desktop**
- Zainstalowany **Node.js 18+** (razem z `npm`)

Wszystkie komendy poniżej uruchamiaj w **PowerShell** w katalogu głównym projektu
`python_distributed_database` (chyba że jest napisane inaczej).

---

## Jak uruchomić w 3 krokach

### 1. Backend (kontenery Docker)
```powershell
docker-compose up -d --build
```

### 2. Frontend (interfejs WWW)
```powershell
cd client_app

# tylko za pierwszym razem
npm install

# za każdym razem, gdy chcesz uruchomić UI
npm run dev
```

### 3. Wejdź w przeglądarce
```text
http://localhost:3000
```

To wszystko – po tych krokach powinieneś widzieć panel do pracy z klastrem.

---

## Jak zatrzymać

Zatrzymaj kontenery (w katalogu głównym projektu):

```powershell
docker-compose down
```

Jeśli frontend (`npm run dev`) nadal działa, przerwij go skrótem `Ctrl+C` w tym samym oknie terminala.

---
