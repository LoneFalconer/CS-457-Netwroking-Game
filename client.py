"""
client.py - Tic-Tac-Toe Game Client
CS457 Sprint 3

Connects to the game server over TCP and plays tic-tac-toe interactively
via the CLI.  A daemon receiver thread handles all incoming server messages
so the display is always responsive, even while the user is typing.

Protocol, framing, and message schemas are defined in protocol_blueprint.md.
"""

import argparse
import json
import socket
import sys
import threading
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RECV_BUFFER = 4096  # bytes per recv() call

# Human-readable labels for every GAME_OVER result string
RESULT_BANNERS = {
    "WIN": "[GAME OVER] YOU WIN!",
    "LOSE": "[GAME OVER] YOU LOSE.",
    "DRAW": "[GAME OVER] IT'S A DRAW!",
    "WIN_FORFEIT": "[GAME OVER] YOU WIN BY FORFEIT! (Opponent disconnected/timed out)",
    "LOSE_FORFEIT": "[GAME OVER] YOU LOSE BY FORFEIT. (You exceeded the 60-second turn limit)",
}

# Human-readable descriptions for every ERROR code
ERROR_MESSAGES = {
    100: "[ERROR 100] Malformed message! The server could not parse your request.",
    111: "[ERROR 111] Out of turn! Please wait for your turn.",
    112: "[ERROR 112] Invalid move! Cell is occupied or out of bounds (0-2).",
}

# ---------------------------------------------------------------------------
# Board Rendering
# ---------------------------------------------------------------------------


def render_board(board: list[list[str]]) -> str:
    """
    Render a 3x3 tic-tac-toe board as a human-readable ASCII string.

    Empty cells are shown as their coordinate hint (row,col) so the player
    knows exactly what to type.

      O | 0,1 | X
     ---+-----+---
     1,0 | O  | 1,2
     ---+-----+---
     X  | 2,1 | 2,2
    """
    rows = []
    for r in range(3):
        cells = []
        for c in range(3):
            val = board[r][c]
            cells.append(f" {val if val else f'{r},{c}'} ")
        rows.append("|".join(cells))
    separator = "-" * len(rows[0])
    return f"\n{separator}\n".join(rows)


# ---------------------------------------------------------------------------
# Network Helpers
# ---------------------------------------------------------------------------


def send_msg(sock: socket.socket, msg: dict) -> None:
    """
    Serialize *msg* to JSON and send it over *sock* with a trailing newline.

    Framing (protocol_blueprint.md Section Framing): one JSON object per line,
    terminated with \\n, encoded as UTF-8.
    """
    raw = json.dumps(msg) + "\n"
    try:
        sock.sendall(raw.encode("utf-8"))
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass  # connection lost; caller handles exit


def ts() -> int:
    """Return current Unix epoch timestamp as an integer (seconds)."""
    return int(time.time())


# ---------------------------------------------------------------------------
# Receiver Thread
# ---------------------------------------------------------------------------


class ReceiverThread(threading.Thread):
    """
    Daemon thread that continuously reads from the server socket, parses
    newline-delimited JSON messages from the stream buffer, and queues
    them for the main thread to dispatch (3.2.2).

    Using a daemon thread keeps the client responsive to server events
    (LOBBY_WAIT, GAME_START, STATE_UPDATE, ERROR, GAME_OVER) even while
    the main thread is blocked on input().
    """

    def __init__(self, sock: socket.socket, on_message, on_disconnect) -> None:
        super().__init__(daemon=True)
        self.sock = sock
        self.on_message = on_message      # callable(dict)
        self.on_disconnect = on_disconnect  # callable()
        self._buf = bytearray()

    def run(self) -> None:
        """Read from socket, coalesce fragments, dispatch complete messages."""
        while True:
            try:
                data = self.sock.recv(RECV_BUFFER)
            except (ConnectionResetError, BrokenPipeError, TimeoutError, OSError):
                self.on_disconnect()
                return

            if not data:
                # EOF - server closed the connection (protocol_blueprint.md Section TCP 0-byte EOF)
                self.on_disconnect()
                return

            # Append to persistent stream buffer (1.2 - fragmentation buffer)
            self._buf += data

            # Extract all complete \n-delimited messages (1.2 - coalescing)
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                    self.on_message(msg)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Silently drop malformed server frames (shouldn't happen)
                    pass


# ---------------------------------------------------------------------------
# Game Client
# ---------------------------------------------------------------------------


class TicTacToeClient:
    """
    Interactive CLI tic-tac-toe client.

    Connects to the server, completes the CONNECT handshake, then enters a
    main loop that:
      - Reads user input (moves / quit) on the main thread.
      - Displays server events immediately via the receiver daemon thread.
    """

    def __init__(self, sock: socket.socket, player_id: str) -> None:
        self.sock = sock
        self.player_id = player_id

        # Local game state (3.2.3)
        self.my_role: str | None = None          # 'O' or 'X', set on GAME_START
        self.board: list[list[str]] = [["" for _ in range(3)] for _ in range(3)]
        self.current_turn: str = "O"             # 'O' always starts
        self.game_active: bool = False
        self.game_over: bool = False

        # Thread-safety: a simple flag + Event for game-over signalling
        self._stop_event = threading.Event()

        # Score tracking across possible future games (shown in GAME_OVER banner)
        self.wins = 0
        self.losses = 0
        self.draws = 0

    # ------------------------------------------------------------------
    # Entry Point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Send CONNECT, start receiver thread, then enter the input loop."""
        # Send CONNECT immediately upon connecting (3.2.1)
        send_msg(self.sock, {
            "msg_type": "CONNECT",
            "player_id": self.player_id,
            "timestamp": ts(),
        })

        # Start daemon receiver thread (3.2.2)
        receiver = ReceiverThread(
            self.sock,
            on_message=self._on_message,
            on_disconnect=self._on_server_disconnect,
        )
        receiver.start()

        print(f"\n[INFO] Connected as '{self.player_id}'. Waiting for server...\n")

        # Main input loop
        self._input_loop()

    # ------------------------------------------------------------------
    # Input Loop (main thread)
    # ------------------------------------------------------------------

    def _input_loop(self) -> None:
        """
        Block on user input, parse moves, and send MOVE or DISCONNECT to server.

        Accepts:
          - 'q' / 'quit'  -> send DISCONNECT and exit (3.2.4)
          - 'row col' or 'row,col' (e.g. '0 2' or '1,2') -> send MOVE
        """
        while not self._stop_event.is_set():
            try:
                raw = input()
            except EOFError:
                # Piped input exhausted
                break
            except KeyboardInterrupt:
                # Ctrl+C -> graceful quit (3.2.4)
                self._send_disconnect()
                break

            line = raw.strip()

            if not line:
                continue

            # Quit command (3.2.4)
            if line.lower() in ("q", "quit"):
                self._send_disconnect()
                break

            # Only accept move input when it's the user's turn
            if not self.game_active or self.game_over:
                # Silently ignore stray input while in lobby or after game
                continue

            if self.current_turn != self.my_role:
                print("  [WAIT] It's not your turn yet. Please wait.")
                continue

            # Parse 'row col' or 'row,col'
            parts = line.replace(",", " ").split()
            if len(parts) != 2:
                print("  [ERROR] Enter your move as: row col  (e.g. 0 2)")
                continue
            try:
                row, col = int(parts[0]), int(parts[1])
            except ValueError:
                print("  [ERROR] Row and column must be integers (0, 1, or 2).")
                continue

            # Send MOVE to server (3.2.4)
            send_msg(self.sock, {
                "msg_type": "MOVE",
                "player_id": self.player_id,
                "payload": {"row": row, "col": col},
                "timestamp": ts(),
            })

    # ------------------------------------------------------------------
    # Message Dispatcher (receiver thread calls this)
    # ------------------------------------------------------------------

    def _on_message(self, msg: dict) -> None:
        """Route an incoming server message to the appropriate handler."""
        msg_type = msg.get("msg_type")

        if msg_type == "LOBBY_WAIT":
            self._on_lobby_wait(msg)
        elif msg_type == "GAME_START":
            self._on_game_start(msg)
        elif msg_type == "STATE_UPDATE":
            self._on_state_update(msg)
        elif msg_type == "ERROR":
            self._on_error(msg)
        elif msg_type == "GAME_OVER":
            self._on_game_over(msg)
        else:
            print(f"\n[CLIENT] Unknown message type received: {msg_type!r}")

    # ------------------------------------------------------------------
    # Protocol Handlers
    # ------------------------------------------------------------------

    def _on_lobby_wait(self, msg: dict) -> None:
        """Display lobby waiting message."""
        print("[WAIT] Waiting for a second player to join...\n")

    def _on_game_start(self, msg: dict) -> None:
        """
        Handle GAME_START: store role, reset board, display initial state (3.2.3).
        """
        self.my_role = msg.get("role")
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.current_turn = "O"   # O always starts (spec Section 2.3.4)
        self.game_active = True
        self.game_over = False

        print("\n" + "=" * 44)
        print("           GAME STARTED!")
        print(f"  [INFO] You are playing as: {self.my_role}")
        print("=" * 44)
        print(render_board(self.board))
        print()
        self._print_turn_status()

    def _on_state_update(self, msg: dict) -> None:
        """
        Handle STATE_UPDATE: place symbol on local board, flip turn (3.2.3).

        The client tracks whose turn it is independently by flipping
        current_turn on every STATE_UPDATE received - matching the server's
        authoritative FSM.
        """
        payload = msg.get("payload", {})
        row = payload.get("row")
        col = payload.get("col")

        if row is None or col is None:
            return

        # Place the current turn's symbol (before flipping)
        self.board[row][col] = self.current_turn

        # Flip active turn (O <-> X)
        self.current_turn = "X" if self.current_turn == "O" else "O"

        print("\n" + render_board(self.board))
        print()
        self._print_turn_status()

    def _on_error(self, msg: dict) -> None:
        """Display a human-readable error message (3.2.5)."""
        code = msg.get("error_code")
        text = ERROR_MESSAGES.get(code, f"[ERROR {code}] An unknown error occurred.")
        print(f"\n  {text}")
        # Re-prompt if it's still our turn
        if self.game_active and self.current_turn == self.my_role:
            print(f"  [TURN] Enter your move (row col): ", end="", flush=True)

    def _on_game_over(self, msg: dict) -> None:
        """
        Display the game-over banner and session summary, then signal exit (3.2.5).
        """
        result = msg.get("result", "UNKNOWN")
        banner = RESULT_BANNERS.get(result, f"[GAME OVER] Result: {result}")

        # Update session score
        if result == "WIN" or result == "WIN_FORFEIT":
            self.wins += 1
        elif result == "LOSE" or result == "LOSE_FORFEIT":
            self.losses += 1
        elif result == "DRAW":
            self.draws += 1

        print("\n" + "=" * 44)
        print(f"  {banner}")
        print("=" * 44)
        print(render_board(self.board))
        print()
        print("  -- Session Summary --")
        print(f"  Wins: {self.wins}  |  Losses: {self.losses}  |  Draws: {self.draws}")
        print("=" * 44 + "\n")

        self.game_over = True
        self.game_active = False

        # Signal the input loop to exit, then close socket
        self._stop_event.set()
        try:
            self.sock.close()
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _print_turn_status(self) -> None:
        """Print whose turn it is and prompt for input if it's the user's turn."""
        if self.current_turn == self.my_role:
            print(f"  [TURN] Your Turn ({self.my_role}) - enter move (row col): ", end="", flush=True)
        else:
            print(f"  [WAIT] Waiting for Player {self.current_turn}...")

    def _send_disconnect(self) -> None:
        """Send DISCONNECT to the server and signal exit (3.2.4)."""
        send_msg(self.sock, {
            "msg_type": "DISCONNECT",
            "player_id": self.player_id,
            "timestamp": ts(),
        })
        print("\n[INFO] Disconnected. Goodbye!")
        self._stop_event.set()
        try:
            self.sock.close()
        except OSError:
            pass

    def _on_server_disconnect(self) -> None:
        """Called by the receiver thread when the server closes the connection."""
        if not self._stop_event.is_set():
            print("\n[INFO] Connection to server lost.")
            self._stop_event.set()


# ---------------------------------------------------------------------------
# CLI Argument Parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """
    Parse and validate CLI arguments (3.1.1).

    Required:
      -i / --hostname   server DNS name or IP
      -p / --port       server port (1024-65535)
    Optional:
      -h                auto-generated help
    """
    parser = argparse.ArgumentParser(
        prog="client.py",
        description="Tic-Tac-Toe TCP Game Client",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--hostname",
        required=True,
        metavar="HOST",
        help="Server hostname or IP address.",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        required=True,
        metavar="PORT",
        help="Server port (1024-65535).",
    )
    args = parser.parse_args()

    # Port range validation
    if not (1024 <= args.port <= 65535):
        parser.error(
            f"Port {args.port} is out of range. "
            "Please specify a port between 1024 and 65535.\n"
            f"Usage: python client.py -i <HOST> -p <PORT>"
        )

    return args


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """Program entry point."""
    args = parse_args()

    # --- Mandatory DNS resolution block (3.1.2) ---
    try:
        server_ip = socket.gethostbyname(args.hostname)
    except socket.gaierror as e:
        print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
        print(
            "Please check your Cisco router DNS configuration "
            "('ip dns server' / 'ip host') or verify domain spelling."
        )
        sys.exit(1)

    # --- Connect to server (3.1.3) ---
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((server_ip, args.port))
    except ConnectionRefusedError:
        print(
            f"[ERROR] Connection refused by {args.hostname}:{args.port}. "
            "Is the server running?"
        )
        sys.exit(1)
    except OSError as e:
        print(f"[ERROR] Could not connect to {args.hostname}:{args.port} - {e}")
        sys.exit(1)

    # --- Prompt for player ID (3.2.1) ---
    try:
        player_id = input("Enter your gamer tag (alphanumeric, leave blank for 'Player'): ").strip()
    except (EOFError, KeyboardInterrupt):
        player_id = ""

    if not player_id:
        player_id = "Player"

    # --- Start the game client ---
    client = TicTacToeClient(sock, player_id)
    client.run()


if __name__ == "__main__":
    main()
