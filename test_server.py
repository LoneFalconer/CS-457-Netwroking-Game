"""
test_server.py - Automated integration test for server.py

Spins up server.py in a subprocess and runs two socket clients through a
full game scenario:
  1. Both clients connect (Player 1 → LOBBY_WAIT, Player 2 → GAME_START)
  2. Out-of-turn MOVE from Player 2 → ERROR 111
  3. Invalid coord MOVE from Player 1 → ERROR 112
  4. Play 5 moves that result in Player 1 (O) winning (3-in-a-row top row)
  5. Assert both sides receive GAME_OVER (WIN / LOSE)
  6. Assert server resets and accepts new clients
"""

import json
import socket
import subprocess
import sys
import time

PYTHON = sys.executable
SERVER_PATH = r"c:\Users\wyatt\Desktop\School\CS457\full_project\CS-457-Netwroking-Game\server.py"
HOST = "127.0.0.1"
PORT = 54321
TIMEOUT = 5  # seconds per recv


def send_msg(sock, msg):
    raw = json.dumps(msg) + "\n"
    sock.sendall(raw.encode("utf-8"))


def recv_msg(sock):
    """Read until \\n and parse JSON."""
    buf = b""
    sock.settimeout(TIMEOUT)
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError("Connection closed")
        buf += chunk
    line, _ = buf.split(b"\n", 1)
    return json.loads(line.decode("utf-8"))


def ts():
    return int(time.time())


def main():
    errors = []

    # --- Start server subprocess ---
    srv = subprocess.Popen(
        [PYTHON, SERVER_PATH, "-p", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    time.sleep(0.5)  # Let server bind

    try:
        c1 = socket.create_connection((HOST, PORT))
        c2 = socket.create_connection((HOST, PORT))

        # === CONNECT handshake ===
        send_msg(c1, {"msg_type": "CONNECT", "player_id": "Alice", "timestamp": ts()})
        msg = recv_msg(c1)
        assert msg["msg_type"] == "LOBBY_WAIT", f"Expected LOBBY_WAIT, got {msg}"
        print("[OK] Player 1 received LOBBY_WAIT")

        send_msg(c2, {"msg_type": "CONNECT", "player_id": "Bob", "timestamp": ts()})

        gs1 = recv_msg(c1)
        gs2 = recv_msg(c2)
        assert gs1["msg_type"] == "GAME_START" and gs1["role"] == "O", f"P1 GAME_START: {gs1}"
        assert gs2["msg_type"] == "GAME_START" and gs2["role"] == "X", f"P2 GAME_START: {gs2}"
        print("[OK] Both players received GAME_START (O, X)")

        # === Out-of-turn move: Player 2 (X) moves first → ERROR 111 ===
        send_msg(c2, {"msg_type": "MOVE", "player_id": "Bob", "payload": {"row": 0, "col": 0}, "timestamp": ts()})
        err = recv_msg(c2)
        assert err["msg_type"] == "ERROR" and err["error_code"] == 111, f"Expected ERR 111, got {err}"
        print("[OK] Out-of-turn move rejected with ERROR 111")

        # === Invalid coord move: Player 1 (O) sends out-of-bounds → ERROR 112 ===
        send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice", "payload": {"row": 5, "col": 0}, "timestamp": ts()})
        err = recv_msg(c1)
        assert err["msg_type"] == "ERROR" and err["error_code"] == 112, f"Expected ERR 112, got {err}"
        print("[OK] Out-of-bounds move rejected with ERROR 112")

        # === Play toward O winning: top row (0,0), (0,1), (0,2) ===
        # Turn 1: O plays (0,0)
        send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice", "payload": {"row": 0, "col": 0}, "timestamp": ts()})
        su1 = recv_msg(c1); su2 = recv_msg(c2)
        assert su1["msg_type"] == "STATE_UPDATE", f"Expected STATE_UPDATE: {su1}"
        assert su2["msg_type"] == "STATE_UPDATE", f"Expected STATE_UPDATE: {su2}"
        print("[OK] Turn 1: O (0,0) — STATE_UPDATE to both")

        # Turn 2: X plays (1,0)
        send_msg(c2, {"msg_type": "MOVE", "player_id": "Bob", "payload": {"row": 1, "col": 0}, "timestamp": ts()})
        recv_msg(c1); recv_msg(c2)
        print("[OK] Turn 2: X (1,0)")

        # Turn 3: O plays (0,1)
        send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice", "payload": {"row": 0, "col": 1}, "timestamp": ts()})
        recv_msg(c1); recv_msg(c2)
        print("[OK] Turn 3: O (0,1)")

        # Turn 4: X plays (1,1)
        send_msg(c2, {"msg_type": "MOVE", "player_id": "Bob", "payload": {"row": 1, "col": 1}, "timestamp": ts()})
        recv_msg(c1); recv_msg(c2)
        print("[OK] Turn 4: X (1,1)")

        # Turn 5: O plays (0,2) → O wins top row!
        send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice", "payload": {"row": 0, "col": 2}, "timestamp": ts()})

        # Both players should get STATE_UPDATE then GAME_OVER
        m1a = recv_msg(c1)
        m2a = recv_msg(c2)
        assert m1a["msg_type"] == "STATE_UPDATE", f"Expected STATE_UPDATE before GAME_OVER: {m1a}"
        assert m2a["msg_type"] == "STATE_UPDATE", f"Expected STATE_UPDATE before GAME_OVER: {m2a}"

        m1b = recv_msg(c1)
        m2b = recv_msg(c2)
        assert m1b["msg_type"] == "GAME_OVER" and m1b["result"] == "WIN", f"P1 GAME_OVER: {m1b}"
        assert m2b["msg_type"] == "GAME_OVER" and m2b["result"] == "LOSE", f"P2 GAME_OVER: {m2b}"
        print("[OK] Turn 5: O (0,2) → GAME_OVER: P1=WIN, P2=LOSE")

        c1.close()
        c2.close()

        # === Verify server resets: new clients can connect ===
        time.sleep(0.3)
        c3 = socket.create_connection((HOST, PORT))
        send_msg(c3, {"msg_type": "CONNECT", "player_id": "Charlie", "timestamp": ts()})
        lw = recv_msg(c3)
        assert lw["msg_type"] == "LOBBY_WAIT", f"Server did not reset: {lw}"
        c3.close()
        print("[OK] Server reset to WAITING_FOR_PLAYERS — new client received LOBBY_WAIT")

        print("\n=== ALL TESTS PASSED ===")

    except Exception as e:
        print(f"\n[FAIL] {e}")
        errors.append(str(e))
    finally:
        srv.terminate()
        try:
            out, _ = srv.communicate(timeout=2)
            if out:
                print("\n--- Server output ---")
                print(out.decode("utf-8", errors="replace"))
        except Exception:
            pass

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
