# Networked Tic-Tac-Toe (TCP Client & Server)

A two-player, turn-based networked Tic-Tac-Toe game implemented in Python 3 using TCP stream sockets (`socket.AF_INET`, `socket.SOCK_STREAM`), newline-delimited (`\n`) JSON framing, and single-threaded non-blocking I/O multiplexing (`selectors`).

---

## Project Architecture & Features

- **Transport & Framing:** Reliable TCP stream transport with persistent per-socket coalescing buffers and `\n`-delimited JSON serialization.
- **Server Concurrency (`server.py`):** Single-threaded event loop powered by Python's `selectors.DefaultSelector()` managing two simultaneous client connections, state isolation, turn enforcement, and a 60-second turn timeout timer.
- **Deterministic FSM Engine:** Enforces strict state transitions (`INIT` $\rightarrow$ `WAITING_FOR_PLAYERS` $\rightarrow$ `GAME_START` $\rightarrow$ `PLAYER_TURN` $\leftrightarrow$ `EVALUATE_MOVE` $\rightarrow$ `GAME_OVER` $\rightarrow$ `CLEANUP` $\rightarrow$ `WAITING_FOR_PLAYERS`).
- **Client UI (`client.py`):** Fixed-width ASCII game board, real-time asynchronous state updates, graceful DNS resolution error handling (`socket.gaierror`), and a post-game menu to play again or switch servers while preserving session score history.

---

## Prerequisites

- **Python 3.8+** (Uses only Python Standard Library modules: `socket`, `selectors`, `argparse`, `json`, `sys`, `time`, `threading`). No external `pip` packages are required.

---

## CLI Flags & Usage Reference

### 1. Server (`server.py`)
The server binds to `0.0.0.0` on the specified listening port and waits for two players to connect.

| Flag | Long Flag | Required | Description |
| :--- | :--- | :---: | :--- |
| `-h` | `--help` | No | Displays help and usage instructions. |
| `-p <PORT>` | `--port <PORT>` | **Yes** | TCP listening port (must be an integer in range `1024`–`65535`). |

**Syntax:**
```bash
python3 server.py -h
python3 server.py -p <port>
```

---

### 2. Client (`client.py`)
The client resolves the server hostname via DNS (`socket.gethostbyname()`), connects via TCP, and launches the interactive CLI game interface.

| Flag | Long Flag | Required | Description |
| :--- | :--- | :---: | :--- |
| `-h` | `--help` | No | Displays help and usage instructions. |
| `-i <HOST>` | `--ip` / `--hostname` | **Yes** | Server DNS hostname (e.g., `server.smith.edu`, `localhost`) or IPv4 address. |
| `-p <PORT>` | `--port <PORT>` | **Yes** | Server TCP port (must be an integer in range `1024`–`65535`). |

**Syntax:**
```bash
python3 client.py -h
python3 client.py -i <server_hostname_or_ip> -p <port>
```

---

## Quick-Start Examples

### Example 1: Running a Local 2-Player Match on `localhost`
Open **three separate terminal windows** in the project directory:

**Terminal 1 — Start the Game Server:**
```bash
python3 server.py -p 8080
```

**Terminal 2 — Launch Player 1 (Assigned Role `O`, Goes First):**
```bash
python3 client.py -i localhost -p 8080
```

**Terminal 3 — Launch Player 2 (Assigned Role `X`, Goes Second):**
```bash
python3 client.py -i localhost -p 8080
```

---

### Example 2: Connecting Across a Network Using a DNS Hostname
When deployed across router infrastructure with DNS configured:

```bash
# On the Server Host:
python3 server.py -p 8080

# On Client Machine 1:
python3 client.py -i server.smith.edu -p 8080

# On Client Machine 2:
python3 client.py -i server.smith.edu -p 8080
```

---

### Example 3: Testing Graceful DNS Failure Handling
If an unresolvable hostname is supplied or the DNS server is unreachable, the client catches `socket.gaierror` cleanly and exits with status code `1`:

```bash
python3 client.py -i invalid.hostname.edu -p 8080
```
**Output:**
```text
[ERROR] Unable to resolve DNS hostname 'invalid.hostname.edu'.
Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.
```

---

## How to Play (In-Game Controls)

1. **Enter Gamer Tag:** Upon launching `client.py`, enter an alphanumeric player ID (e.g., `Alice`).
2. **Making a Move:** When the prompt displays `[TURN] Your Turn`, enter your move as `row col` (or `row,col`) using zero-indexed coordinates (`0`, `1`, or `2`):
   - `0 0` $\rightarrow$ Top-Left
   - `0 2` $\rightarrow$ Top-Right
   - `1 1` $\rightarrow$ Center
   - `2 2` $\rightarrow$ Bottom-Right
3. **Quitting Mid-Game:** Type `q` or `quit` (or press `Ctrl+C`) to send a `DISCONNECT` message and forfeit cleanly.
4. **Post-Game Menu:** After each match concludes (`WIN`, `LOSE`, `DRAW`, or forfeit), your cumulative session score (`Wins / Losses / Draws`) is displayed and you can choose:
   - `[1]` Reconnect to the same server for a rematch
   - `[2]` Enter a new server hostname and port
   - `[3]` Quit the application
