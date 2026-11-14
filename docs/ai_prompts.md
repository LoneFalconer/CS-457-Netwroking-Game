# AI Prompts

Implement the networking layer for my tic-tac-toe TCP game exactly as follows. You MUST exactly follow the protocols defined. Do not invent, add, or otherwise hallucinate additional types, fields, rules, or protocol behavior. Even if you think there is a better way, DO NOT intervene with your own will. The protocol and FSM have been designed. Your one and ONLY job is to implement them, not design them.

Protocol Blueprint:

Language: Python 

## Transport Protocol, Serialization, and Framing

### Transport Protocol:

This tic-tac-toe application will use TCP as its transport protocol.

### Serialzitiaon

This application will use JSON to serialize the messages.

### Framing 

Each message is one JSON object that is terminated with a \n character. 

FSM Specification:

## Schema Definitions

| Message Type | Direction | Description |
| -------- | -------- | -------- |
| CONNECT | Client $\rightarrow$ Server | Client requests to join the room with a gamer tag. |
| LOBBY_WAIT | Server $\rightarrow$ Client | Server notifies Client that it is waiting for other Client. |
| GAME_START | Server $\rightarrow$ Client | Server notifies Client that the game has started and assigns sides. |
| MOVE | Client $\rightarrow$ Server | Client notifies the Server that it wants to make a move. |
| STATE_UPDATE | Server $\rightarrow$ Client | Server notifies the Client of a move made by the opponent and this change is reflected locally. |
| ERROR | Server $\rightarrow$ Client | Server notifies the Client that a move was invalid or a message was malformed. |
| DISCONNECT | Client $\rightarrow$ Server | Client notifies the Server that it is quitting. |
| GAME_OVER | Server $\rightarrow$ Client | Server notifies the client that the game is over and what the results are. |

### CONNECT
**Format:**
``` json
{
  "msg_type": "CONNECT",
  "player_id": "<PLAYER_ID>",
  "timestamp": <TIMESTAMP>
}
```
**Example**
``` json
{
  "msg_type": "CONNECT",
  "player_id": "CoolMan123",
  "timestamp": 1727000005
}
```
Fields:
  - MSG_TYPE   (string)  : "CONNECT"
  - PLAYER_ID  (string)  : Alphanumeric alias of active player (e.g. "Player_1")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds

### LOBBY_WAIT
**Format:**
```json
{
  "msg_type": "LOBBY_WAIT",
  "timestamp": <TIMESTAMP>
}
```
**Example:**
``` json
{
  "msg_type": "LOBBY_WAIT",
  "timestamp": 1727000006
}
```
Fields:
  - MSG_TYPE   (string)  : "LOBBY_WAIT"
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds


### GAME_START
**Format:**
```json
{
  "msg_type": "GAME_START",
  "role": "<ROLE>",
  "timestamp": <TIMESTAMP>
}
```
**Example:**
```json
{
  "msg_type": "GAME_START",
  "role": "X",
  "timestamp": 1727000007
}
```
Fields:
  - MSG_TYPE   (string)  : "GAME_START"
  - ROLE  (string)  : Alphanumeric role of player (e.g. "O", or "X:)
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds

### MOVE
**Format:**
```json
{
  "msg_type": "MOVE",
  "player_id": "<PLAYER_ID>",
  "payload": {
    "row": <ROW>,
    "col": <COL>
  },
  "timestamp": <TIMESTAMP>
}
```
**Example:**
```json
{
  "msg_type": "MOVE",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000008
}
```
Fields:
  - MSG_TYPE   (string)  : "MOVE"
  - PLAYER_ID  (string)  : Alphanumeric alias of active player (e.g. "Player_1")
  - PAYLOAD    (integers): <row>,<col> zero-indexed grid coordinates (e.g. "0,2")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds

### STATE_UPDATE

**Behavior Note:** Upon a valid `MOVE`, the Server sends `STATE_UPDATE` to **BOTH** connected clients (`O` and `X`). Both clients maintain a local 3x3 board and track the current active turn (starting with `"O"` on turn 1, alternating between `"O"` and `"X"` on every `STATE_UPDATE` received). When a client receives `STATE_UPDATE`, it places the current turn's symbol (`"O"` or `"X"`) at `(row, col)` on its local board and switches its local active-turn tracker to the other role.

**Format:**
```json
{
  "msg_type": "STATE_UPDATE",
  "payload": {
    "row": <ROW>,
    "col": <COL>
  },
  "timestamp": <TIMESTAMP>
}
```
**Example:**
```json
{
  "msg_type": "STATE_UPDATE",
  "payload": {
    "row": 0,
    "col": 1
  },
  "timestamp": 1727000009
}
```
Fields:
  - MSG_TYPE   (string)  : "STATE_UPDATE"
  - PAYLOAD    (integers): <row>,<col> zero-indexed grid coordinates (e.g. "0,1")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds


### ERROR

**Format:**
```json
{
  "msg_type": "ERROR",
  "error_code": <ERROR_CODE>,
  "timestamp": <TIMESTAMP>
}
```
**Example:**
```json
{
  "msg_type": "ERROR",
  "error_code": 112,
  "timestamp": 1727000009
}
```
Fields:
  - MSG_TYPE   (string)  : "ERROR"
  - ERROR_CODE    (integer): Describes the specific error (e.g. 112)
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds

Defined Error Codes:
  - 100 : Malformed JSON or invalid message schema
  - 111 : Out of turn move (Player attempted a MOVE when it is not their turn)
  - 112 : Invalid move coordinates (Row/Col outside 0-2 or cell is already occupied)


### DISCONNECT

**Format:**
```json
{
  "msg_type": "DISCONNECT",
  "player_id": "<PLAYER_ID>",
  "timestamp": <TIMESTAMP>
}
```
**Example:**
```json
{
  "msg_type": "DISCONNECT",
  "player_id": "Player_1",
  "timestamp": 1727000005
}
```
Fields:
  - MSG_TYPE   (string)  : "DISCONNECT"
  - PLAYER_ID  (string)  : Alphanumeric alias of active player (e.g. "Player_1")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds

### GAME_OVER
**Format:**
```json
{
  "msg_type": "GAME_OVER",
  "result": "<RESULT>",
  "timestamp": <TIMESTAMP>
}
```
**Example:**
```json
{
  "msg_type": "GAME_OVER",
  "result": "WIN",
  "timestamp": 1727000005
}
```
Fields:
  - MSG_TYPE   (string)  : "GAME_OVER"
  - RESULT  (string)  : Result of match for player (e.g. "WIN")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds

Defined Result Strings:
  - "WIN" : Sent to the winning player (3-in-a-row)
  - "LOSE" : Sent to the losing player (opponent got 3-in-a-row)
  - "DRAW" : Sent to both players when all 9 cells are filled with no winner
  - "WIN_FORFEIT" : Sent to the remaining player when the opponent disconnects or times out (60s)
  - "LOSE_FORFEIT" : Sent to the player who exceeded the 60-second turn timeout


## Error Handling

You are to handle errors in case of abrupt termination, such as client crashing, wifi/ethernet disconnecting, TCP RST, kill -9, etc. This means that no 4-way TCP FIN handshake is completed, and a TCP timeout or RST will occur. When a connection is terminated cleanly, recv() will return 0 bytes, or b"" in Python. This represents the End-Of-File (EOF). It MUST be detected so the server is not stuck in an infinite loop. The program must also handle ConnectionResetError, BrokenPipeError, and TimeoutError. 

## Server Concurrency Architecture (Mandatory)
- The server (`server.py`) MUST be single-threaded and use Python's `selectors` module (`selectors.DefaultSelector()`) for Non-Blocking I/O Multiplexing. Do NOT use the `threading` or `asyncio` modules on the server.
- All server sockets (`server_sock` and accepted client sockets) MUST be set to non-blocking mode via `sock.setblocking(False)`.
- The `selectors` event loop must use a short timeout (e.g., `sel.select(timeout=1.0)`) so it can continuously check the 60-second turn timer during `PLAYER_TURN`. If the active player takes more than 60 seconds to send a valid `MOVE`, the server transitions to `GAME_OVER`, sends `"LOSE_FORFEIT"` to the timed-out player and `"WIN_FORFEIT"` to the waiting player, and transitions to `CLEANUP` -> `WAITING_FOR_PLAYERS`.

## FSM Specification

``` mermaid
stateDiagram-v2

    [*] --> INIT

    INIT --> WAITING_FOR_PLAYERS: Server Started and Listening

    WAITING_FOR_PLAYERS --> GAME_START: Two Clients Connected
    WAITING_FOR_PLAYERS --> WAITING_FOR_PLAYERS: One Client Connected

    GAME_START --> PLAYER_TURN: Initialize Board. Assign Player 1 (O) and Player 2 (X) where Player 1 starts first

    PLAYER_TURN --> EVALUATE_MOVE: Current Player Sends MOVE
    PLAYER_TURN --> PLAYER_TURN: Out of turn MOVE - ERROR Sent to Client
    PLAYER_TURN --> GAME_OVER: Client sends DISCONNECT - Game is forfeit
    PLAYER_TURN --> GAME_OVER: Client times out - Game is forfeit
    PLAYER_TURN --> GAME_OVER: Client unexpectedly disconnects - Game is forfeit

    EVALUATE_MOVE --> PLAYER_TURN: Valid Move - Game Continues
    EVALUATE_MOVE --> PLAYER_TURN: Invalid Move - ERROR Sent to Client
    EVALUATE_MOVE --> GAME_OVER: Victory or Draw Detected

    GAME_OVER --> CLEANUP: Broadcast Results

    CLEANUP --> WAITING_FOR_PLAYERS: Close Sockets and Reset Game
```
## CLI Argument Parsing & DNS Resolution Requirements
1. `server.py` CLI:
   - Use `argparse` to parse `-h` (help) and `-p` (port, required integer).
   - Validate that `-p` is between `1024` and `65535`. If missing or out of range, display usage syntax and exit cleanly.
   - Bind the listening TCP socket (`socket.AF_INET`, `socket.SOCK_STREAM`) to `('0.0.0.0', args.port)`.
2. `client.py` CLI & DNS Resolution:
   - Use `argparse` to parse `-h` (help), `-i` (server hostname/IP, required string), and `-p` (server port, required integer validated between `1024` and `65535`).
   - Resolve `-i` using the exact DNS resolution block below before connecting:
     ```python
     try:
         server_ip = socket.gethostbyname(args.hostname)
     except socket.gaierror as e:
         print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
         print("Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.")
         sys.exit(1)
     ```

