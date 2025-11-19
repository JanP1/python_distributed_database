# Distributed Database System with Consensus Algorithms

System rozproszonej bazy danych wykorzystujący algorytmy konsensusu **Raft** i **Paxos** do zapewnienia spójności danych między wieloma serwerami.

## 📋 Spis treści

- [Architektura Systemu](#architektura-systemu)
- [Algorytmy Konsensusu](#algorytmy-konsensusu)
  - [Raft](#raft)
  - [Paxos](#paxos)
- [Struktura Plików](#struktura-plików)
- [Docker i Sieć](#docker-i-sieć)
- [Uruchomienie](#uruchomienie)
- [Użycie](#użycie)
- [API](#api)

---

## 🏗️ Architektura Systemu

System składa się z **4 niezależnych węzłów** (serwerów), które komunikują się ze sobą aby osiągnąć konsensus przed zapisaniem operacji. Każdy węzeł:

- Nasłuchuje na **HTTP** (porty 8001-8004) - obsługa requestów od klientów
- Nasłuchuje na **TCP** (porty 5001-5004) - komunikacja między węzłami
- Może działać w trybie **Raft** lub **Paxos** (dynamiczne przełączanie)

```
┌─────────────────────────────────────────────────────────────┐
│                     Client (Frontend UI)                     │
│                   http://localhost:3000                      │
└──────────────┬──────────────┬──────────────┬────────────────┘
               │ HTTP         │ HTTP         │ HTTP
               ▼              ▼              ▼
         ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
         │ Node 1  │◄──►│ Node 2  │◄──►│ Node 3  │◄──►│ Node 4  │
         │:8001    │TCP │:8002    │TCP │:8003    │TCP │:8004    │
         │:5001    │    │:5002    │    │:5003    │    │:5004    │
         └─────────┘    └─────────┘    └─────────┘    └─────────┘
              ▲              ▲              ▲              ▲
              │              │              │              │
              └──────────────┴──────────────┴──────────────┘
                        Docker Network
                     172.20.0.11 - 172.20.0.14
```

---

## 🧠 Algorytmy Konsensusu

### Raft

**Raft** to algorytm konsensusu oparty na **wyborze lidera**. 

#### Koncepcja:
1. **Wybory lidera** (Leader Election)
   - Na początku wszystkie węzły są `follower`
   - Po timeout węzeł staje się `candidate` i wysyła `REQUEST_VOTE`
   - Jeśli otrzyma większość głosów, zostaje `leader`
   - Tylko lider może przyjmować operacje od klientów

2. **Replikacja logów** (Log Replication)
   - Lider otrzymuje operację od klienta
   - Lider wysyła `APPEND_ENTRIES` do wszystkich followerów
   - Followerzy odpowiadają `APPEND_RESPONSE`
   - Po otrzymaniu kworum (większości), operacja jest zatwierdzona

3. **Terminy** (Terms)
   - Każdy term ma maksymalnie jednego lidera
   - Term zwiększa się przy każdych wyborach

#### Zalety:
- ✅ Prostsza implementacja niż Paxos
- ✅ Jasny podział ról (leader/follower/candidate)
- ✅ Wszystkie węzły mają identyczne logi

---

### Paxos

**Paxos** to algorytm konsensusu **bez lidera**. Każdy węzeł może proponować wartości.

#### Koncepcja:
1. **Faza PREPARE**
   - Proposer generuje unikalny ID propozycji `(round, node_id)`
   - Wysyła `PREPARE(ID)` do wszystkich acceptorów
   - Acceptorzy odpowiadają `PROMISE` jeśli ID > poprzedniego

2. **Faza ACCEPT**
   - Proposer po otrzymaniu większości `PROMISE` wysyła `ACCEPT(ID, value)`
   - Acceptorzy sprawdzają czy ID jest nadal najwyższy
   - Jeśli tak, zapisują wartość i wysyłają `ACCEPTED`

3. **Quorum i konsensus**
   - Większość węzłów (3 z 4) musi się zgodzić
   - Wartość jest zatwierdzona po otrzymaniu większości `ACCEPTED`

#### Zalety:
- ✅ Brak single point of failure (brak lidera)
- ✅ Każdy węzeł może proponować
- ✅ Teoretycznie udowodniona poprawność

#### Wady:
- ⚠️ Tylko proposer zapisuje w logu (inni tylko PROMISE/ACCEPT)
- ⚠️ Bardziej skomplikowana implementacja

---

## 📁 Struktura Plików

### Backend (Python)

#### `consensus_server.py` - **Główny serwer konsensusu**
- Jednolity serwer obsługujący oba algorytmy (Raft i Paxos)
- Uruchamia serwer HTTP dla REST API (porty 8001-8004)
- Uruchamia serwer TCP dla komunikacji między węzłami (porty 5001-5004)
- Obsługuje endpointy: /status, /propose, /log, /switch_algorithm, /start_election
- Dynamicznie przełącza między algorytmami bez restartu kontenera
- Filtruje wiadomości TCP aby ignorować niewłaściwy algorytm
- Automatycznie rozpoczyna wybory lidera przy przełączeniu na Raft (Node 1 po 0.5s, inne po 1.5s)
- Zapewnia obsługę CORS dla requestów z przeglądarki

---

#### `Raft/raft_messages.py` - **Definicje wiadomości Raft**
- Definiuje strukturę wiadomości Raft (RaftMessage dataclass)
- Zawiera typy wiadomości: REQUEST_VOTE, VOTE, APPEND_ENTRIES, APPEND_RESPONSE
- Przechowuje informacje o nadawcy, odbiorcy, typie wiadomości, termie i zawartości

---

#### `Raft/raft_nodes.py` - **Logika węzła Raft**
- Implementuje węzeł Raft z rolami: follower, candidate, leader
- Zarządza termami, głosowaniem i replikowanym logiem
- Obsługuje REQUEST_VOTE - głosowanie na kandydata w wyborach
- Obsługuje VOTE - zlicza głosy i awansuje do lidera przy kworum
- Obsługuje APPEND_ENTRIES - replikuje wpisy logu od lidera
- Obsługuje APPEND_RESPONSE - zlicza potwierdzenia od followerów
- Wszystkie węzły mają identyczny log po osiągnięciu konsensusu
---

#### `Paxos/paxos_messages.py` - **Definicje wiadomości Paxos**
- Definiuje strukturę wiadomości Paxos (PaxosMessage dataclass)
- Zawiera typy wiadomości: PREPARE, PROMISE, ACCEPT, ACCEPTED
- Przechowuje informacje o nadawcy, odbiorcy, identyfikatorze rundy i zawartości

---

#### `Paxos/paxos_nodes.py` - **Logika węzła Paxos**
- Implementuje węzeł Paxos (proposer i acceptor w jednym)
- Zarządza najwyższym obiecanym ID propozycji
- Obsługuje PREPARE - przyjmuje propozycje z wyższym ID
- Obsługuje PROMISE - zlicza obietnice i przechodzi do fazy ACCEPT
- Obsługuje ACCEPT - akceptuje wartość jeśli ID jest aktualny
- Obsługuje ACCEPTED - zlicza akceptacje i zapisuje do logu przy kworum
- **Uwaga**: Tylko proposer (węzeł inicjujący) zapisuje wartość w logu, inne węzły tylko głosują

---

### Frontend (Next.js + React)

#### `client_app/src/app/page.tsx`
- Główna strona aplikacji Next.js z układem 2-kolumnowym
- Lewa kolumna: komponenty ConsensusCluster i Balance
- Prawa kolumna: panel logów konsensusu w czasie rzeczywistym
- Zarządza komunikacją między interfejsem bankowym a systemem rozproszonym

#### `client_app/src/components/client-page/consensus-cluster.tsx`
- Komponent zarządzania klastrem konsensusu
- Wyświetla status wszystkich 4 węzłów (role, term, log_size)
- Menu Select do dynamicznego przełączania algorytmu (Raft/Paxos)
- Eksponuje funkcję proposeOperation() do wysyłania operacji
- Automatycznie odświeża status węzłów co 5 sekund
- Znajduje lidera Raft lub używa Node 1 dla Paxos
- **Przycisk "Zresetuj"** - resetuje węzły do stanu początkowego (zachowuje wybrany algorytm)

#### `client_app/src/components/client-page/consensus-logs.tsx`
- **Panel logów konsensusu w czasie rzeczywistym**
- Rozwija się po kliknięciu ikony
- Pobiera logi ze wszystkich 4 węzłów co 2 sekundy
- Wyświetla ostatnie 50 zdarzeń konsensusu
- Koloruje logi według typu: INFO, CONSENSUS, PROPOSE, ELECTION, ERROR
- Pokazuje timestamp, node_id, algorytm i szczegóły zdarzenia

#### `client_app/src/components/client-page/balance.tsx`
- Komponent operacji bankowych (wpłata/wypłata)
- Automatycznie wysyła każdą transakcję do klastra konsensusu
- Wyświetla aktualny stan konta
- Formularze do wprowadzania kwot wpłat i wypłat

---

## 🐳 Docker i Sieć

### `Dockerfile`
- Definiuje obraz Docker z Python 3.12-slim
- Kopiuje pliki Raft, Paxos i consensus_server.py
- Otwiera porty 8000 (HTTP) i 5000 (TCP)
- Uruchamia consensus_server.py jako główny proces

### `docker-compose.yml`
- Definiuje 4 węzły (consensus_node1-4)
- Każdy węzeł ma statyczne IP (172.20.0.11-14)
- Mapuje porty: 8001-8004 (HTTP), 5001-5004 (TCP)
- Konfiguruje zmienne środowiskowe (NODE_ID, PEERS, ALGORITHM)
- Tworzy izolowaną sieć Docker (consensus_network)

### `.gitignore`
- Ignoruje pliki Python (__pycache__, *.pyc)
- Ignoruje pliki IDE (.vscode, .idea)
- Ignoruje logi i pliki tymczasowe

### Komunikacja w Docker

1. **HTTP (Klient → Węzeł)**: `localhost:8001-8004 → Container:8000`
2. **TCP (Węzeł ↔ Węzeł)**: Węzły komunikują się przez statyczne IP 172.20.0.11-14 na porcie 5000
3. **Izolacja**: Sieć `consensus_network` izoluje klaster od innych kontenerów

---

## 🚀 Szybki Start

#### 1️⃣ Backend (Docker - 4 węzły konsensusu)

```powershell
# Sklonuj repozytorium
git clone https://github.com/JanP1/python_distributed_database.git
cd python_distributed_database

# Uruchom klaster Docker
docker-compose up -d --build

# Sprawdź czy wszystkie węzły działają
docker ps
# Powinno pokazać: consensus_node1, consensus_node2, consensus_node3, consensus_node4

# (Opcjonalnie) Zobacz logi
docker logs consensus_node1 -f
```

#### 2️⃣ Frontend (Next.js UI)

```powershell
# W nowym terminalu
cd client_app
npm install
npm run dev
```

#### 3️⃣ Otwórz aplikację

Otwórz przeglądarkę: **http://localhost:3000**


## 💻 Użycie

### Przez UI (http://localhost:3000)
- **Lewa kolumna:**
  - Wybierz algorytm z menu rozwijanego (Raft/Paxos)
  - Zobacz status węzłów (role, term, log_size)
  - **Przyciski akcji:**
    - **"Odśwież Status"** - ręczne odświeżenie statusu węzłów
    - **"Zresetuj"** (czerwony) - resetuje wszystkie węzły do stanu początkowego (czyści logi operacji, zachowuje algorytm)
  - Wpłać/Wypłać - operacje automatycznie replikowane
  - Odświeża się co 5 sekund
- **Prawa kolumna - Panel logów konsensusu:**
  - Kliknij ikonę ▼/▲, aby rozwinąć/zwinąć panel z logami
  - Zobacz zdarzenia konsensusu w czasie rzeczywistym
  - Logi kodowane kolorami:
    - 🔵 **INFO** - informacje systemowe
    - 🔵 **CONSENSUS** - wymiana wiadomości między węzłami
    - 🟢 **PROPOSE** - propozycje nowych operacji
    - 🟠 **ELECTION** - wybory lidera (tylko Raft)
    - 🔴 **ERROR** - błędy
  - Automatyczne odświeżanie co 2 sekundy
  - Wyświetla ostatnie 50 zdarzeń ze wszystkich węzłów

### Dostępne endpointy API:
- **GET /status** - Zwraca status węzła (algorytm, rola, term, lider, rozmiar logu)
- **POST /propose** - Proponuje operację do zatwierdzenia przez klaster
- **GET /log** - Zwraca replikowany log węzła
- **GET /consensus_logs** - Zwraca logi zdarzeń konsensusu (dla UI)
- **POST /start_election** - Rozpoczyna wybory lidera (tylko Raft)
- **POST /switch_algorithm** - Przełącza węzeł między Raft a Paxos
- **POST /reset** - Resetuje węzeł do stanu początkowego (czyści logi operacji, zachowuje algorytm)

---

## 📊 Porównanie Algorytmów

| Cecha | Raft | Paxos |
|-------|------|-------|
| **Lider** | Tak, wymagany | Nie, każdy może proponować |
| **Replikacja logów** | Wszystkie węzły | Tylko proposer |
| **Złożoność** | Prostsza | Bardziej skomplikowana |
| **Fazy** | 1 (APPEND_ENTRIES) | 2 (PREPARE, ACCEPT) |
| **Wybory** | Tak (REQUEST_VOTE) | Nie |
| **Quorum** | Większość (3/4) | Większość (3/4) |
| **Przełączanie** | Automatyczne wybory po 1.5s | Gotowy od razu |
