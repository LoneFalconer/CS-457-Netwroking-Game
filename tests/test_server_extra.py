"""
test_server_extra.py - Additional edge-case tests for server.py

Tests:
  - Occupied cell returns ERROR 112
  - DISCONNECT during game sends WIN_FORFEIT to remaining player
  - DRAW scenario
"""

import json
import socket
import subprocess
import sys
import time

PYTHON = sys.executable
SERVER_PATH = r"c:\Users\wyatt\Desktop\School\CS457\full_project\CS-457-Netwroking-Game\server.py"
HOST = "127.0.0.1"
PORT = 54322
TIMEOUT = 5


def send_msg(sock, msg):
    raw = json.dumps(msg) + "\n"
    sock.sendall(raw.encode("utf-8"))


def recv_msg(sock):
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


def connect_two(host, port):
    """Connect two clients and complete CONNECT handshake. Returns (c1, c2)."""
    c1 = socket.create_connection((host, port))
    c2 = socket.create_connection((host, port))
    send_msg(c1, {"msg_type": "CONNECT", "player_id": "P1", "timestamp": ts()})
    recv_msg(c1)  # LOBBY_WAIT
    send_msg(c2, {"msg_type": "CONNECT", "player_id": "P2", "timestamp": ts()})
    recv_msg(c1)  # GAME_START
    recv_msg(c2)  # GAME_START
    return c1, c2


def main():
    srv = subprocess.Popen(
        [PYTHON, SERVER_PATH, "-p", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    time.sleep(0.5)

    try:
        # --- Test: occupied cell → ERROR 112 ---
        c1, c2 = connect_two(HOST, PORT)
        # O plays (0,0)
        send_msg(c1, {"msg_type": "MOVE", "player_id": "P1", "payload": {"row": 0, "col": 0}, "timestamp": ts()})
        recv_msg(c1); recv_msg(c2)  # STATE_UPDATE
        # X plays (1,0)
        send_msg(c2, {"msg_type": "MOVE", "player_id": "P2", "payload": {"row": 1, "col": 0}, "timestamp": ts()})
        recv_msg(c1); recv_msg(c2)  # STATE_UPDATE
        # O tries (0,0) again — occupied
        send_msg(c1, {"msg_type": "MOVE", "player_id": "P1", "payload": {"row": 0, "col": 0}, "timestamp": ts()})
        err = recv_msg(c1)
        assert err["msg_type"] == "ERROR" and err["error_code"] == 112, f"Expected ERR 112 for occupied: {err}"
        print("[OK] Occupied cell rejected with ERROR 112")
        c1.close(); c2.close()
        time.sleep(0.3)

        # --- Test: DISCONNECT during game → WIN_FORFEIT to remaining player ---
        c1, c2 = connect_two(HOST, PORT)
        send_msg(c1, {"msg_type": "DISCONNECT", "player_id": "P1", "timestamp": ts()})
        # c2 (X) should receive WIN_FORFEIT
        go = recv_msg(c2)
        assert go["msg_type"] == "GAME_OVER" and go["result"] == "WIN_FORFEIT", f"Expected WIN_FORFEIT: {go}"
        print("[OK] DISCONNECT during game → remaining player gets WIN_FORFEIT")
        c1.close(); c2.close()
        time.sleep(0.3)

        # --- Test: DRAW scenario ---
        # Draw board (no 3-in-a-row):
        #   O X O
        #   X O X
        #   X O X  <- Wait, col 2 is X X X — that's a win for X
        #
        # Correct draw (no winner):
        #   O X O     turn 1=O, 2=X, 3=O
        #   X X O     turn 4=X, 5=X... no, must alternate
        #
        # Proper alternating sequence (O=c1 on odd turns, X=c2 on even turns):
        # Move 1: O(0,0)  Move 2: X(1,1)  Move 3: O(0,1)
        # Move 4: X(0,2)  Move 5: O(2,0)  Move 6: X(1,0)
        # Move 7: O(1,2)  Move 8: X(2,2)  Move 9: O(2,1)
        # Board:
        #   O O X
        #   X X O
        #   O O X   <- no row/col/diag all same → DRAW
        c1, c2 = connect_two(HOST, PORT)
        # (player_sock, row, col) — strictly alternating O/X
        moves = [
            (c1, 0, 0), (c2, 1, 1), (c1, 0, 1),
            (c2, 0, 2), (c1, 2, 0), (c2, 1, 0),
            (c1, 1, 2), (c2, 2, 2), (c1, 2, 1),
        ]
        for sock, r, c in moves:
            pid = "P1" if sock is c1 else "P2"
            send_msg(sock, {"msg_type": "MOVE", "player_id": pid, "payload": {"row": r, "col": c}, "timestamp": ts()})
            su_c1 = recv_msg(c1)
            su_c2 = recv_msg(c2)
            # On the last move both STATE_UPDATE and GAME_OVER arrive
            if su_c1["msg_type"] == "GAME_OVER":
                # This was actually the GAME_OVER (last move sent STATE then GAME_OVER)
                go1 = su_c1
                go2 = su_c2
                break
            # Check if next message is GAME_OVER (last move)
            # (server sends STATE_UPDATE then GAME_OVER in sequence)
        else:
            go1 = recv_msg(c1)
            go2 = recv_msg(c2)

        assert go1["msg_type"] == "GAME_OVER" and go1["result"] == "DRAW", f"P1 expected DRAW: {go1}"
        assert go2["msg_type"] == "GAME_OVER" and go2["result"] == "DRAW", f"P2 expected DRAW: {go2}"
        print("[OK] Draw scenario → both players receive GAME_OVER DRAW")
        c1.close(); c2.close()

        print("\n=== ALL EXTRA TESTS PASSED ===")

    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback; traceback.print_exc()
    finally:
        srv.terminate()
        try:
            out, _ = srv.communicate(timeout=2)
            if out:
                print("\n--- Server output ---")
                print(out.decode("utf-8", errors="replace"))
        except Exception:
            pass


if __name__ == "__main__":
    main()
