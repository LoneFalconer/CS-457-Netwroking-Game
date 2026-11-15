"""
server.py - Tic-Tac-Toe Game Server
CS457 Sprint 3

Single-threaded TCP server using Python's selectors module for non-blocking
I/O multiplexing. Implements the full FSM and wire protocol defined in:
  - protocol_blueprint.md
  - fsm_specification.md
  - concurrency_design.md
"""

import argparse
import json
import selectors
import socket
import sys
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TURN_TIMEOUT_SECONDS = 60  # Maximum seconds a player has to submit a MOVE

# FSM states
STATE_WAITING_FOR_PLAYERS = "WAITING_FOR_PLAYERS"
STATE_GAME_START = "GAME_START"
STATE_PLAYER_TURN = "PLAYER_TURN"
STATE_GAME_OVER = "GAME_OVER"
STATE_CLEANUP = "CLEANUP"

# Error codes (protocol_blueprint.md)
ERR_MALFORMED = 100   # Malformed JSON or missing required fields
ERR_OUT_OF_TURN = 111  # MOVE sent when it is not the sender's turn
ERR_INVALID_MOVE = 112  # Row/col out of 0-2 or cell already occupied

# ---------------------------------------------------------------------------
# Message Builders
# All helpers produce dicts with ONLY the fields defined in the protocol.
# ---------------------------------------------------------------------------


def _ts() -> int:
    """Return current Unix timestamp as an integer (seconds)."""
    return int(time.time())


def build_lobby_wait() -> dict:
    """Build a LOBBY_WAIT message."""
    return {"msg_type": "LOBBY_WAIT", "timestamp": _ts()}


def build_game_start(role: str) -> dict:
    """Build a GAME_START message for the given role ('O' or 'X')."""
    return {"msg_type": "GAME_START", "role": role, "timestamp": _ts()}


def build_state_update(row: int, col: int) -> dict:
    """Build a STATE_UPDATE message for the given board coordinates."""
    return {
        "msg_type": "STATE_UPDATE",
        "payload": {"row": row, "col": col},
        "timestamp": _ts(),
    }


def build_error(error_code: int) -> dict:
    """Build an ERROR message with the specified error code."""
    return {"msg_type": "ERROR", "error_code": error_code, "timestamp": _ts()}


def build_game_over(result: str) -> dict:
    """
    Build a GAME_OVER message.

    result must be one of: 'WIN', 'LOSE', 'DRAW', 'WIN_FORFEIT', 'LOSE_FORFEIT'
    """
    return {"msg_type": "GAME_OVER", "result": result, "timestamp": _ts()}


# ---------------------------------------------------------------------------
# Network Helpers
# ---------------------------------------------------------------------------


def send_msg(sock: socket.socket, msg: dict) -> None:
    """
    Serialize *msg* to JSON and send it over *sock* with a trailing newline.

    Framing: each message is one JSON object terminated with \\n encoded
    as UTF-8, as required by protocol_blueprint.md.
    """
    raw = json.dumps(msg) + "\n"
    try:
        sock.sendall(raw.encode("utf-8"))
    except (BrokenPipeError, ConnectionResetError, OSError):
        # Caller is responsible for detecting and handling broken connections;
        # silently swallow send errors here so we don't double-fault.
        pass


def parse_messages(buf: bytearray) -> tuple[list[dict], bytearray]:
    """
    Extract all complete newline-delimited JSON messages from *buf*.

    Returns (list_of_parsed_dicts, remaining_buf_with_partial_message).
    Implements the stream coalescing / fragmentation buffer described in
    protocol_blueprint.md: accumulate bytes from recv() calls, split on \\n,
    leave any partial trailing bytes in the buffer.
    """
    messages = []
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line.decode("utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Return None sentinel so caller can send ERR_MALFORMED
            messages.append(None)
    return messages, buf


# ---------------------------------------------------------------------------
# Game Logic
# ---------------------------------------------------------------------------


def make_board() -> list[list[str]]:
    """Return a fresh empty 3x3 board."""
    return [["" for _ in range(3)] for _ in range(3)]


def check_winner(board: list[list[str]]) -> str | None:
    """
    Check the board for a winner.

    Returns the winning symbol ('O' or 'X') or None if there is no winner yet.
    """
    lines = [
        # Rows
        [(0, 0), (0, 1), (0, 2)],
        [(1, 0), (1, 1), (1, 2)],
        [(2, 0), (2, 1), (2, 2)],
        # Columns
        [(0, 0), (1, 0), (2, 0)],
        [(0, 1), (1, 1), (2, 1)],
        [(0, 2), (1, 2), (2, 2)],
        # Diagonals
        [(0, 0), (1, 1), (2, 2)],
        [(0, 2), (1, 1), (2, 0)],
    ]
    for line in lines:
        symbols = [board[r][c] for r, c in line]
        if symbols[0] and symbols[0] == symbols[1] == symbols[2]:
            return symbols[0]
    return None


def is_draw(board: list[list[str]]) -> bool:
    """Return True when all 9 cells are filled (implies no winner)."""
    return all(board[r][c] != "" for r in range(3) for c in range(3))


# ---------------------------------------------------------------------------
# Server Class
# ---------------------------------------------------------------------------


class TicTacToeServer:
    """
    Single-threaded tic-tac-toe server.

    Uses selectors.DefaultSelector() for non-blocking I/O multiplexing
    (zero threading / asyncio) in accordance with concurrency_design.md.
    """

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

        # Selector (Criterion 4 — single-threaded multiplexing)
        self.sel = selectors.DefaultSelector()

        # FSM state
        self.state = STATE_WAITING_FOR_PLAYERS

        # Connected clients: {sock: {"player_id": str, "role": str, "buf": bytearray}}
        self.clients: dict[socket.socket, dict] = {}

        # Ordered list of client sockets so we know who is Player 1 (O) vs Player 2 (X)
        self.player_socks: list[socket.socket] = []

        # Game state
        self.board: list[list[str]] = make_board()
        self.active_turn: str = "O"      # 'O' always starts first
        self.turn_start_time: float = 0.0  # Reset at the start of every turn

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Bind the listening socket, register it with the selector, and
        enter the main event loop.
        """
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen()
        server_sock.setblocking(False)  # Non-blocking (Criterion 4)

        self.sel.register(server_sock, selectors.EVENT_READ, data="server")
        print(f"[SERVER] Listening on {self.host}:{self.port}")

        try:
            self._event_loop(server_sock)
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down.")
        finally:
            self.sel.close()
            server_sock.close()

    # ------------------------------------------------------------------
    # Event Loop
    # ------------------------------------------------------------------

    def _event_loop(self, server_sock: socket.socket) -> None:
        """
        Main selector event loop.

        Uses timeout=1.0 so the 60-second turn timer is checked at least
        once per second (Criterion 4, item 2.2.3).
        """
        while True:
            events = self.sel.select(timeout=1.0)  # 1-second timeout for timer checks

            for key, mask in events:
                if key.data == "server":
                    # New incoming connection
                    self._accept(server_sock)
                else:
                    # Data from an existing client
                    self._handle_client(key.fileobj)

            # Check the 60-second turn timeout during PLAYER_TURN
            if self.state == STATE_PLAYER_TURN:
                self._check_turn_timeout()

    # ------------------------------------------------------------------
    # Accept
    # ------------------------------------------------------------------

    def _accept(self, server_sock: socket.socket) -> None:
        """Accept a new client connection and register it with the selector."""
        try:
            conn, addr = server_sock.accept()
        except OSError:
            return

        conn.setblocking(False)  # Non-blocking (Criterion 4)
        self.sel.register(conn, selectors.EVENT_READ, data="client")
        self.clients[conn] = {
            "player_id": None,
            "role": None,
            "buf": bytearray(),
        }
        print(f"[SERVER] New connection from {addr}")

    # ------------------------------------------------------------------
    # Client I/O
    # ------------------------------------------------------------------

    def _handle_client(self, sock: socket.socket) -> None:
        """Read available data from *sock* and dispatch parsed messages."""
        if sock not in self.clients:
            return

        try:
            data = sock.recv(4096)
        except (ConnectionResetError, BrokenPipeError, TimeoutError, OSError):
            # Abrupt disconnect (2.4.3)
            print(f"[SERVER] Socket error on {sock.getpeername()!r} — treating as disconnect.")
            self._handle_abrupt_disconnect(sock)
            return

        if not data:
            # EOF — remote side closed the connection cleanly (2.4.3)
            print("[SERVER] EOF received — client disconnected.")
            self._handle_abrupt_disconnect(sock)
            return

        # Append to per-socket receive buffer (1.2 — fragmentation buffer)
        self.clients[sock]["buf"] += data

        # Extract complete newline-delimited messages (1.2 — coalescing)
        messages, self.clients[sock]["buf"] = parse_messages(
            self.clients[sock]["buf"]
        )

        for msg in messages:
            if msg is None:
                # Malformed JSON — send error code 100
                send_msg(sock, build_error(ERR_MALFORMED))
                continue
            self._dispatch(sock, msg)

    # ------------------------------------------------------------------
    # Message Dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, sock: socket.socket, msg: dict) -> None:
        """Route an incoming message to the appropriate FSM handler."""
        msg_type = msg.get("msg_type")

        if msg_type == "CONNECT":
            self._on_connect(sock, msg)
        elif msg_type == "MOVE":
            self._on_move(sock, msg)
        elif msg_type == "DISCONNECT":
            self._on_disconnect(sock, msg)
        else:
            # Unknown or unexpected message type
            send_msg(sock, build_error(ERR_MALFORMED))

    # ------------------------------------------------------------------
    # FSM: CONNECT
    # ------------------------------------------------------------------

    def _on_connect(self, sock: socket.socket, msg: dict) -> None:
        """
        Handle a CONNECT message.

        FSM: WAITING_FOR_PLAYERS
          - 1st client  → stores player_id, assigns role 'O', sends LOBBY_WAIT
          - 2nd client  → stores player_id, assigns role 'X', transitions to
                          GAME_START and then immediately to PLAYER_TURN
          - Extra clients (match already active) → ignored / rejected
        """
        # Validate required fields (1.3)
        if "player_id" not in msg or "timestamp" not in msg:
            send_msg(sock, build_error(ERR_MALFORMED))
            return

        player_id = msg["player_id"]

        if self.state != STATE_WAITING_FOR_PLAYERS:
            # Match is already active — reject extra connections (2.3.3)
            print(f"[SERVER] Rejecting extra CONNECT from {player_id!r} (game active).")
            return

        # Already registered this socket (duplicate CONNECT) — ignore
        if self.clients[sock]["player_id"] is not None:
            return

        if len(self.player_socks) == 0:
            # --- First player (O) ---
            self.clients[sock]["player_id"] = player_id
            self.clients[sock]["role"] = "O"
            self.player_socks.append(sock)
            send_msg(sock, build_lobby_wait())
            print(f"[SERVER] Player 1 '{player_id}' connected — role O. Waiting for Player 2.")

        elif len(self.player_socks) == 1:
            # --- Second player (X) → start game ---
            self.clients[sock]["player_id"] = player_id
            self.clients[sock]["role"] = "X"
            self.player_socks.append(sock)
            print(f"[SERVER] Player 2 '{player_id}' connected — role X. Starting game.")
            self._start_game()

    # ------------------------------------------------------------------
    # FSM: GAME_START → PLAYER_TURN
    # ------------------------------------------------------------------

    def _start_game(self) -> None:
        """
        Transition WAITING_FOR_PLAYERS → GAME_START → PLAYER_TURN.

        Resets the board, assigns turns, and broadcasts GAME_START to both
        clients (2.3.4).
        """
        self.state = STATE_GAME_START

        # Reset board and set active turn to 'O' (Player 1 always starts)
        self.board = make_board()
        self.active_turn = "O"

        # Send GAME_START to each player with their respective role
        sock_o = self.player_socks[0]  # Player 1 — O
        sock_x = self.player_socks[1]  # Player 2 — X
        send_msg(sock_o, build_game_start("O"))
        send_msg(sock_x, build_game_start("X"))

        # Start the 60-second turn timer
        self.turn_start_time = time.time()
        self.state = STATE_PLAYER_TURN
        print(f"[SERVER] Game started. {self.active_turn}'s turn.")

    # ------------------------------------------------------------------
    # FSM: MOVE
    # ------------------------------------------------------------------

    def _on_move(self, sock: socket.socket, msg: dict) -> None:
        """
        Handle a MOVE message during PLAYER_TURN.

        Validates turn ownership, coordinates, and cell availability.
        Applies the move, broadcasts STATE_UPDATE, then checks for
        win/draw/continue.
        """
        if self.state != STATE_PLAYER_TURN:
            # MOVE outside of an active game — ignore
            return

        # Validate required fields (1.3)
        if (
            "player_id" not in msg
            or "payload" not in msg
            or "timestamp" not in msg
            or not isinstance(msg.get("payload"), dict)
            or "row" not in msg["payload"]
            or "col" not in msg["payload"]
        ):
            send_msg(sock, build_error(ERR_MALFORMED))
            return

        sender_role = self.clients[sock]["role"]

        # Out-of-turn check (2.3.5)
        if sender_role != self.active_turn:
            send_msg(sock, build_error(ERR_OUT_OF_TURN))
            return

        # Coordinate validation (2.3.6)
        row = msg["payload"]["row"]
        col = msg["payload"]["col"]

        if (
            not isinstance(row, int)
            or not isinstance(col, int)
            or row not in range(3)
            or col not in range(3)
            or self.board[row][col] != ""
        ):
            send_msg(sock, build_error(ERR_INVALID_MOVE))
            return

        # --- Valid move: apply to board ---
        self.board[row][col] = self.active_turn
        print(
            f"[SERVER] {self.active_turn} played ({row},{col})."
        )

        # Broadcast STATE_UPDATE to BOTH clients (2.3.6)
        state_msg = build_state_update(row, col)
        for s in self.player_socks:
            send_msg(s, state_msg)

        # Win / draw / continue evaluation (2.3.7)
        winner = check_winner(self.board)
        if winner:
            # 3-in-a-row detected → GAME_OVER
            self._end_game_winner(winner)
        elif is_draw(self.board):
            # All 9 cells filled, no winner → DRAW
            self._end_game_draw()
        else:
            # Switch turn and reset the timer
            self.active_turn = "X" if self.active_turn == "O" else "O"
            self.turn_start_time = time.time()
            print(f"[SERVER] Turn switched. Now {self.active_turn}'s turn.")

    # ------------------------------------------------------------------
    # FSM: DISCONNECT (graceful)
    # ------------------------------------------------------------------

    def _on_disconnect(self, sock: socket.socket, msg: dict) -> None:
        """
        Handle a graceful DISCONNECT message from a client (2.4.2).

        If in an active game, award WIN_FORFEIT to the other player and
        trigger cleanup.
        """
        # Validate required fields (1.3)
        if "player_id" not in msg or "timestamp" not in msg:
            send_msg(sock, build_error(ERR_MALFORMED))

        player_id = self.clients[sock].get("player_id", "unknown")
        print(f"[SERVER] DISCONNECT received from '{player_id}'.")

        if self.state == STATE_PLAYER_TURN:
            # Award the remaining player a forfeit win (2.4.2)
            self._forfeit_for_disconnect(sock)
        else:
            # In lobby: just clean up the single client
            self._remove_client(sock)

    # ------------------------------------------------------------------
    # FSM: Abrupt Disconnect / EOF
    # ------------------------------------------------------------------

    def _handle_abrupt_disconnect(self, sock: socket.socket) -> None:
        """
        Handle an abrupt disconnect (EOF or socket error) (2.4.3).

        Awards WIN_FORFEIT to the remaining player if a game is active;
        cleans up the waiting client otherwise.
        """
        if sock not in self.clients:
            return

        if self.state == STATE_PLAYER_TURN:
            self._forfeit_for_disconnect(sock)
        else:
            self._remove_client(sock)

    # ------------------------------------------------------------------
    # Forfeit helpers
    # ------------------------------------------------------------------

    def _forfeit_for_disconnect(self, disconnecting_sock: socket.socket) -> None:
        """
        Transition to GAME_OVER due to a client disconnect / EOF.

        Sends LOSE_FORFEIT to the disconnecting player (best-effort) and
        WIN_FORFEIT to the remaining player.
        """
        self.state = STATE_GAME_OVER
        # Best-effort notification to the disconnecting client
        send_msg(disconnecting_sock, build_game_over("LOSE_FORFEIT"))

        for s in self.player_socks:
            if s is not disconnecting_sock:
                send_msg(s, build_game_over("WIN_FORFEIT"))

        self._cleanup()

    def _check_turn_timeout(self) -> None:
        """
        Check whether the active player has exceeded the 60-second turn limit
        (2.4.1).  Triggers GAME_OVER with LOSE_FORFEIT / WIN_FORFEIT if so.
        """
        if time.time() - self.turn_start_time > TURN_TIMEOUT_SECONDS:
            print(
                f"[SERVER] Turn timeout! {self.active_turn} took over 60 seconds."
            )
            self.state = STATE_GAME_OVER

            # Identify active (timed-out) and waiting sockets
            active_sock = None
            waiting_sock = None
            for s in self.player_socks:
                if self.clients[s]["role"] == self.active_turn:
                    active_sock = s
                else:
                    waiting_sock = s

            if active_sock:
                send_msg(active_sock, build_game_over("LOSE_FORFEIT"))
            if waiting_sock:
                send_msg(waiting_sock, build_game_over("WIN_FORFEIT"))

            self._cleanup()

    # ------------------------------------------------------------------
    # Game Over helpers
    # ------------------------------------------------------------------

    def _end_game_winner(self, winner_role: str) -> None:
        """
        Send WIN to the winning player and LOSE to the loser, then cleanup
        (2.3.7).
        """
        self.state = STATE_GAME_OVER
        print(f"[SERVER] {winner_role} wins!")

        for s in self.player_socks:
            role = self.clients[s]["role"]
            if role == winner_role:
                send_msg(s, build_game_over("WIN"))
            else:
                send_msg(s, build_game_over("LOSE"))

        self._cleanup()

    def _end_game_draw(self) -> None:
        """Send DRAW to both players, then cleanup (2.3.7)."""
        self.state = STATE_GAME_OVER
        print("[SERVER] Draw!")

        for s in self.player_socks:
            send_msg(s, build_game_over("DRAW"))

        self._cleanup()

    # ------------------------------------------------------------------
    # CLEANUP → WAITING_FOR_PLAYERS
    # ------------------------------------------------------------------

    def _cleanup(self) -> None:
        """
        Transition GAME_OVER → CLEANUP → WAITING_FOR_PLAYERS (2.4.4).

        Unregisters all client sockets from the selector, closes them, resets
        game state, and returns the server to WAITING_FOR_PLAYERS.
        """
        self.state = STATE_CLEANUP
        print("[SERVER] Cleaning up game state.")

        for s in list(self.player_socks):
            self._remove_client(s)

        # Also remove any connected sockets that never made it into a game
        for s in list(self.clients.keys()):
            self._remove_client(s)

        # Reset shared game state
        self.board = make_board()
        self.active_turn = "O"
        self.turn_start_time = 0.0
        self.player_socks = []

        self.state = STATE_WAITING_FOR_PLAYERS
        print("[SERVER] Reset complete. Waiting for new players.")

    def _remove_client(self, sock: socket.socket) -> None:
        """Unregister *sock* from the selector, close it, and remove metadata."""
        if sock not in self.clients:
            return
        try:
            self.sel.unregister(sock)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass
        del self.clients[sock]
        if sock in self.player_socks:
            self.player_socks.remove(sock)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Required:  -p / --port  (integer, 1024–65535)
    Optional:  -h           (auto-generated help)
    """
    parser = argparse.ArgumentParser(
        prog="server.py",
        description="Tic-Tac-Toe TCP Game Server",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        required=True,
        metavar="PORT",
        help="Port to listen on (1024–65535).",
    )
    args = parser.parse_args()

    # Port range validation (2.1.2)
    if not (1024 <= args.port <= 65535):
        parser.error(
            f"Port {args.port} is out of range. "
            "Please specify a port between 1024 and 65535.\n"
            f"Usage: python server.py -p <PORT>"
        )

    return args


def main() -> None:
    """Program entry point."""
    args = parse_args()
    server = TicTacToeServer(host="0.0.0.0", port=args.port)
    server.start()


if __name__ == "__main__":
    main()
