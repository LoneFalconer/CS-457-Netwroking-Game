# Sprint 3 AI Implementation Checklist & Verification Roadmap

> **Instructions for AI Assistant (Antigravity):**
> You are implementing Sprint 3 (`server.py` and `client.py`) based strictly on `@protocol_blueprint.md`, `@fsm_specification.md`, `@concurrency_design.md`, `@sequence_diagram.md`, and `@ai_prompts.md`.
> 
> **Mandatory Workflow:**
> 1. Read each phase below before writing code.
> 2. Implement the exact requirements without inventing new JSON fields, message types, or protocol behaviors.
> 3. As you complete and verify each requirement in code, **update this file (`sprint3_roadmap.md`) by changing `- [ ]` to `- [x]`**.
> 4. Do not mark a task `- [x]` until the code for that specific requirement is written and verified against the spec.

---

## Phase 1: Specification & Schema Compliance Lock
Ensure both `server.py` and `client.py` adhere strictly to the wire protocol and schemas defined in `@protocol_blueprint.md` and `@ai_prompts.md`.

- [ ] **1.1 Transport & Framing:** Both applications use TCP (`socket.AF_INET`, `socket.SOCK_STREAM`) and frame every JSON message with a trailing newline (`\n`) encoded in `utf-8`.
- [ ] **1.2 Stream Coalescing & Fragmentation Buffer:** Both `server.py` and `client.py` maintain a persistent receive byte buffer per socket that appends chunks from `recv(4096)` and splits on `\n`, leaving partial trailing bytes in the buffer until the next `recv()` call.
- [ ] **1.3 Exact JSON Schema Enforcement (No Extra Keys):**
  - [ ] `CONNECT`: `{"msg_type": "CONNECT", "player_id": "<str>", "timestamp": <int>}`
  - [ ] `LOBBY_WAIT`: `{"msg_type": "LOBBY_WAIT", "timestamp": <int>}`
  - [ ] `GAME_START`: `{"msg_type": "GAME_START", "role": "<O|X>", "timestamp": <int>}`
  - [ ] `MOVE`: `{"msg_type": "MOVE", "player_id": "<str>", "payload": {"row": <int>, "col": <int>}, "timestamp": <int>}`
  - [ ] `STATE_UPDATE`: `{"msg_type": "STATE_UPDATE", "payload": {"row": <int>, "col": <int>}, "timestamp": <int>}`
  - [ ] `ERROR`: `{"msg_type": "ERROR", "error_code": <int>, "timestamp": <int>}`
  - [ ] `DISCONNECT`: `{"msg_type": "DISCONNECT", "player_id": "<str>", "timestamp": <int>}`
  - [ ] `GAME_OVER`: `{"msg_type": "GAME_OVER", "result": "<str>", "timestamp": <int>}`
- [ ] **1.4 Standardized Error Codes & Results:**
  - [ ] Error code `100` used for malformed JSON or missing required fields.
  - [ ] Error code `111` used for out-of-turn `MOVE` attempts.
  - [ ] Error code `112` used for out-of-bounds (`row`/`col` not in `0..2`) or already-occupied cell `MOVE` attempts.
  - [ ] `GAME_OVER` result strings strictly use `"WIN"`, `"LOSE"`, `"DRAW"`, `"WIN_FORFEIT"`, or `"LOSE_FORFEIT"`.

---

## Phase 2: `server.py` Implementation Checklist
Build `server.py` to the below sepcifications

### 2.1 CLI Argument Parsing & Socket Setup (Criterion 1)
- [ ] **2.1.1 `argparse` Flags:** Implements `-h` (help) and `-p` / `--port` (required integer).
- [ ] **2.1.2 Port Validation:** Validates that `-p` is between `1024` and `65535` (inclusive). Prints helpful usage syntax and exits cleanly with non-zero status if missing or invalid.
- [ ] **2.1.3 Non-Blocking Bind to `0.0.0.0`:** Binds listening TCP socket to `('0.0.0.0', args.port)` with `SO_REUSEADDR`, calls `server_sock.setblocking(False)`, and registers it with `selectors.DefaultSelector()`.

### 2.2 Single-Threaded `selectors` Multiplexing (Criterion 4)
- [ ] **2.2.1 Strictly Single-Threaded:** Uses `selectors.DefaultSelector()` exclusively for concurrency (zero use of `threading` or `asyncio`).
- [ ] **2.2.2 Non-Blocking Client Sockets:** Calls `conn.setblocking(False)` on every accepted client socket and registers it with the selector.
- [ ] **2.2.3 Selector Loop Timeout:** Calls `sel.select(timeout=1.0)` inside the main event loop so the 60-second turn timeout timer is checked at least once per second.

### 2.3 FSM States & Game Logic (`@fsm_specification.md`)
- [ ] **2.3.1 `INIT` $\rightarrow$ `WAITING_FOR_PLAYERS`:** Initializes server state, empty 3x3 board, client tracking dictionary, and starts listening.
- [ ] **2.3.2 `WAITING_FOR_PLAYERS` (Player 1 Connects):** Upon receiving `CONNECT` from the 1st client, stores `player_id`, assigns role `"O"`, sends `LOBBY_WAIT`, and stays in `WAITING_FOR_PLAYERS`.
- [ ] **2.3.3 `WAITING_FOR_PLAYERS` $\rightarrow$ `GAME_START` (Player 2 Connects):** Upon receiving `CONNECT` from the 2nd client, stores `player_id`, assigns role `"X"`, and transitions immediately to `GAME_START`. (Rejects or ignores extra connections while a match of 2 players is active).
- [ ] **2.3.4 `GAME_START` $\rightarrow$ `PLAYER_TURN`:** Resets 3x3 board to empty, sets active turn to `"O"` (Player 1 always starts first), sends `GAME_START` with `"role": "O"` to Player 1 and `"role": "X"` to Player 2, starts the 60-second turn timer (`time.time()`), and transitions to `PLAYER_TURN`.
- [ ] **2.3.5 `PLAYER_TURN` (Out-of-Turn Check):** If the non-active player sends `MOVE`, responds to that client with `ERROR` (`error_code: 111`) and remains in `PLAYER_TURN` without resetting the active player's timer.
- [ ] **2.3.6 `PLAYER_TURN` $\rightarrow$ `EVALUATE_MOVE`:** When the active player sends `MOVE`, validates `payload.row` and `payload.col`.
  - [ ] If coordinates are not integers in `0..2` or the cell is not empty: sends `ERROR` (`error_code: 112`) to the active player and returns to `PLAYER_TURN`.
  - [ ] If valid: updates server board, broadcasts `STATE_UPDATE` (`row`, `col`) to **both** clients.
- [ ] **2.3.7 Win / Draw / Continue Evaluation:**
  - [ ] If 3-in-a-row detected: transitions to `GAME_OVER`, sends `GAME_OVER` (`"WIN"`) to winner and `GAME_OVER` (`"LOSE"`) to loser, then runs `CLEANUP`.
  - [ ] If all 9 cells filled with no winner: transitions to `GAME_OVER`, sends `GAME_OVER` (`"DRAW"`) to both clients, then runs `CLEANUP`.
  - [ ] Otherwise: switches active turn (`"O"` $\leftrightarrow$ `"X"`), resets the 60-second turn timer, and transitions back to `PLAYER_TURN`.

### 2.4 Timeout, Disconnects & Cleanup
- [ ] **2.4.1 60-Second Turn Timeout:** If `time.time() - turn_start_time > 60` during `PLAYER_TURN`, transitions to `GAME_OVER`, sends `GAME_OVER` (`"LOSE_FORFEIT"`) to the active player and `GAME_OVER` (`"WIN_FORFEIT"`) to the waiting player, and runs `CLEANUP`.
- [ ] **2.4.2 Graceful `DISCONNECT` Message:** If a client sends `DISCONNECT` during an active game, transitions to `GAME_OVER`, sends `GAME_OVER` (`"WIN_FORFEIT"`) to the remaining player, and runs `CLEANUP`.
- [ ] **2.4.3 Abrupt Disconnect & EOF Handling:** Detects `recv()` returning `b""` (0-byte EOF) and catches `ConnectionResetError`, `BrokenPipeError`, and `TimeoutError`. Awards `"WIN_FORFEIT"` to the remaining player if in an active game (or cleans up the waiting client if in `WAITING_FOR_PLAYERS`) without crashing the server.
- [ ] **2.4.4 `CLEANUP` $\rightarrow$ `WAITING_FOR_PLAYERS`:** Unregisters client sockets from `selectors`, closes client sockets cleanly, resets board and active turn state, and returns to `WAITING_FOR_PLAYERS` ready for a new game.

---

## Phase 3: `client.py` Implementation Checklist
Build `client.py` to satisfy the following.

### 3.1 CLI Argument Parsing & Mandatory DNS Handling (Criteria 1 & 2)
- [ ] **3.1.1 `argparse` Flags:** Implements `-h` (help), `-i` (server DNS hostname or IP, required), and `-p` (server port, required integer validated in range `1024-65535`).
- [ ] **3.1.2 Mandatory `socket.gaierror` Exception Block:** Resolves `-i` via `socket.gethostbyname()` using the exact required error message and exit code `1`:
  ```python
  try:
      server_ip = socket.gethostbyname(args.hostname)
  except socket.gaierror as e:
      print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
      print("Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.")
      sys.exit(1)
  ```
- [ ] **3.1.3 Connection Error Handling:** Catches `ConnectionRefusedError` and ` OSError` when connecting to `(server_ip, args.port)` so the client exits cleanly with a friendly message instead of a raw traceback if the server is offline.

### 3.2 Client Protocol, Local Board Sync & CLI UI
- [ ] **3.2.1 Player ID & `CONNECT` Handshake:** Prompts the user for an alphanumeric gamer tag (or defaults cleanly if blank) and immediately sends `CONNECT` upon connecting.
- [ ] **3.2.2 Responsive Receive & Input Handling:** Uses non-blocking I/O or a daemon receiver thread with a `\n`-delimited receive buffer so incoming server messages (`LOBBY_WAIT`, `GAME_START`, `STATE_UPDATE`, `ERROR`, `GAME_OVER`) are processed and displayed immediately even while waiting for user input.
- [ ] **3.2.3 Local 3x3 Board & Turn Tracking:**
  - [ ] On `GAME_START`: Stores assigned role (`"O"` or `"X"`), initializes empty local 3x3 board, sets `current_turn = "O"`, renders the initial ASCII board, and displays turn status (`"Your Turn (O)"` or `"Waiting for Player O..."`).
  - [ ] On `STATE_UPDATE`: Places `current_turn` symbol (`"O"` or `"X"`) at `(payload.row, payload.col)` on the local 3x3 board, flips `current_turn` (`"O"` $\leftrightarrow$ `"X"`), re-renders the clean ASCII board, and prints updated turn status.
- [ ] **3.2.4 User Input & `DISCONNECT`:**
  - [ ] Allows user to enter moves as `row col` (e.g., `0 2` or `0,2`) and sends `MOVE` JSON to server.
  - [ ] Allows user to type `q` / `quit` (or press `Ctrl+C`) to send `DISCONNECT` JSON to the server and exit cleanly.
- [ ] **3.2.5 Human-Readable Error & Game Over Display:**
  - [ ] Translates `ERROR` codes (`100`, `111`, `112`) into clear CLI warnings (`"[ERROR 111] Out of turn! Please wait for your turn."`, `"[ERROR 112] Invalid move! Cell is occupied or out of bounds (0-2)."`).
  - [ ] On `GAME_OVER`: Prints a clear match result banner (`WIN`, `LOSE`, `DRAW`, `WIN_FORFEIT`, `LOSE_FORFEIT`), displays a session score/match summary, closes the socket, and exits cleanly.

---

## Phase 4: Automated Verification & Rubric Acceptance Tests
Run these verification checks after writing `server.py` and `client.py` and check them off once confirmed:

- [ ] **4.1 Help & Port Validation Check:**
  - [ ] `python3 server.py -h` and `python3 client.py -h` output clean usage instructions.
  - [ ] `python3 server.py -p 80` and `python3 client.py -i localhost -p 70000` reject out-of-range ports with usage syntax and exit non-zero.
- [ ] **4.2 Broken DNS Check:**
  - [ ] `python3 client.py -i invalid.hostname.smith.edu -p 8080` prints the exact `[ERROR] Unable to resolve DNS hostname...` message and exits with code `1` (no traceback).
- [ ] **4.3 Multi-Turn Gameplay & Edge-Case Verification:**
  - [ ] Server starts on `0.0.0.0:8080` and accepts 2 simultaneous clients on `localhost:8080`.
  - [ ] Client 1 receives `LOBBY_WAIT`, then both clients receive `GAME_START` (`O` and `X`).
  - [ ] Out-of-turn move returns `ERROR 111`; occupied cell move returns `ERROR 112`.
  - [ ] At least 3 valid turns complete with synchronized board updates on both clients up to a `GAME_OVER` state, and server cleanly resets to `WAITING_FOR_PLAYERS`.
- [ ] **4.4 Code Quality & PEP 8:**
  - [ ] Both `server.py` and `client.py` follow PEP 8 naming/formatting, are modular, and include explanatory docstrings and inline comments.
