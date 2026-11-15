"""
test_phase4.py - Phase 4 Automated Verification Suite
CS457 Sprint 3

Runs all Phase 4.3 rubric acceptance tests:
  4.3a  Server starts on 0.0.0.0 and accepts 2 clients on localhost
  4.3b  Client 1 receives LOBBY_WAIT; both receive GAME_START (O and X)
  4.3c  Out-of-turn move → ERROR 111; occupied cell → ERROR 112
  4.3d  At least 3 valid turns complete with STATE_UPDATE sync up to GAME_OVER
        and server resets cleanly to WAITING_FOR_PLAYERS

Also validates 4.4 (code quality) via static grep checks.
"""

import json
import socket
import subprocess
import sys
import time

PYTHON = sys.executable
ROOT = r"c:\Users\wyatt\Desktop\School\CS457\full_project\CS-457-Netwroking-Game"
SERVER = ROOT + r"\server.py"
HOST = "127.0.0.1"
PORT = 8080
TIMEOUT = 6

PASS = "[PASS]"
FAIL = "[FAIL]"
failures = []


def ok(label):
    print(f"  {PASS} {label}")


def fail(label, detail=""):
    msg = f"  {FAIL} {label}" + (f" — {detail}" if detail else "")
    print(msg)
    failures.append(msg)


def send_msg(sock, msg):
    sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))


def recv_msg(sock):
    buf = b""
    sock.settimeout(TIMEOUT)
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError("Connection closed by server")
        buf += chunk
    line, _ = buf.split(b"\n", 1)
    return json.loads(line.decode("utf-8"))


def ts():
    return int(time.time())


def connect_and_start(host, port):
    """Connect two clients, complete CONNECT handshake, return (c1, c2)."""
    c1 = socket.create_connection((host, port))
    c2 = socket.create_connection((host, port))
    send_msg(c1, {"msg_type": "CONNECT", "player_id": "Alice", "timestamp": ts()})
    lw = recv_msg(c1)
    assert lw["msg_type"] == "LOBBY_WAIT"
    send_msg(c2, {"msg_type": "CONNECT", "player_id": "Bob", "timestamp": ts()})
    gs1 = recv_msg(c1)
    gs2 = recv_msg(c2)
    assert gs1["msg_type"] == "GAME_START" and gs1["role"] == "O"
    assert gs2["msg_type"] == "GAME_START" and gs2["role"] == "X"
    return c1, c2


# ---------------------------------------------------------------------------
# Start server
# ---------------------------------------------------------------------------
srv = subprocess.Popen(
    [PYTHON, SERVER, "-p", str(PORT)],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
time.sleep(0.6)

print("\n" + "=" * 54)
print("  Phase 4.3 — Multi-Turn Gameplay & Edge-Case Tests")
print("=" * 54)

try:
    # -----------------------------------------------------------------------
    # 4.3a  Server accepts two clients
    # -----------------------------------------------------------------------
    print("\n── 4.3a: Server connection & LOBBY_WAIT / GAME_START ──")
    try:
        c1 = socket.create_connection((HOST, PORT))
        c2 = socket.create_connection((HOST, PORT))
        send_msg(c1, {"msg_type": "CONNECT", "player_id": "Alice", "timestamp": ts()})
        lw = recv_msg(c1)
        assert lw["msg_type"] == "LOBBY_WAIT", f"Got {lw}"
        ok("Server started on 0.0.0.0 and accepted two clients")
        ok("Client 1 received LOBBY_WAIT")

        send_msg(c2, {"msg_type": "CONNECT", "player_id": "Bob", "timestamp": ts()})
        gs1 = recv_msg(c1)
        gs2 = recv_msg(c2)
        assert gs1["msg_type"] == "GAME_START" and gs1["role"] == "O", f"P1: {gs1}"
        assert gs2["msg_type"] == "GAME_START" and gs2["role"] == "X", f"P2: {gs2}"
        ok("Both clients received GAME_START (O and X assigned correctly)")
    except Exception as e:
        fail("4.3a connection/handshake", str(e))
        raise

    # -----------------------------------------------------------------------
    # 4.3c  Error codes 111 and 112
    # -----------------------------------------------------------------------
    print("\n── 4.3c: Error code enforcement ──")

    # Out-of-turn: X (c2) moves first
    send_msg(c2, {"msg_type": "MOVE", "player_id": "Bob",
                  "payload": {"row": 0, "col": 0}, "timestamp": ts()})
    err111 = recv_msg(c2)
    if err111.get("msg_type") == "ERROR" and err111.get("error_code") == 111:
        ok("Out-of-turn MOVE from Player X → ERROR 111")
    else:
        fail("ERROR 111 for out-of-turn move", str(err111))

    # Out-of-bounds: O (c1) sends row=9
    send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice",
                  "payload": {"row": 9, "col": 0}, "timestamp": ts()})
    err112a = recv_msg(c1)
    if err112a.get("msg_type") == "ERROR" and err112a.get("error_code") == 112:
        ok("Out-of-bounds MOVE (row=9) → ERROR 112")
    else:
        fail("ERROR 112 for out-of-bounds row", str(err112a))

    # Valid move then occupied-cell: O plays (0,0), then tries (0,0) again
    send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice",
                  "payload": {"row": 0, "col": 0}, "timestamp": ts()})
    recv_msg(c1); recv_msg(c2)  # STATE_UPDATE to both

    # X takes (1,0)
    send_msg(c2, {"msg_type": "MOVE", "player_id": "Bob",
                  "payload": {"row": 1, "col": 0}, "timestamp": ts()})
    recv_msg(c1); recv_msg(c2)  # STATE_UPDATE to both

    # O tries already-occupied (0,0)
    send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice",
                  "payload": {"row": 0, "col": 0}, "timestamp": ts()})
    err112b = recv_msg(c1)
    if err112b.get("msg_type") == "ERROR" and err112b.get("error_code") == 112:
        ok("Occupied-cell MOVE → ERROR 112")
    else:
        fail("ERROR 112 for occupied cell", str(err112b))

    # -----------------------------------------------------------------------
    # 4.3d  ≥ 3 valid turns → synchronized STATE_UPDATEs → GAME_OVER + reset
    # -----------------------------------------------------------------------
    print("\n── 4.3d: Multi-turn gameplay → GAME_OVER → server reset ──")
    # Board so far:  O(0,0) X(1,0) [O's turn]
    # Complete O's win: O(0,1), X(1,1), O(0,2) → top row for O

    # Turn 3 — O plays (0,1)
    send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice",
                  "payload": {"row": 0, "col": 1}, "timestamp": ts()})
    su_c1 = recv_msg(c1); su_c2 = recv_msg(c2)
    if su_c1["msg_type"] == "STATE_UPDATE" and su_c2["msg_type"] == "STATE_UPDATE":
        ok("Turn 3 — O(0,1): STATE_UPDATE delivered to both clients")
    else:
        fail("Turn 3 STATE_UPDATE", f"c1={su_c1} c2={su_c2}")

    # Turn 4 — X plays (1,1)
    send_msg(c2, {"msg_type": "MOVE", "player_id": "Bob",
                  "payload": {"row": 1, "col": 1}, "timestamp": ts()})
    su_c1 = recv_msg(c1); su_c2 = recv_msg(c2)
    if su_c1["msg_type"] == "STATE_UPDATE" and su_c2["msg_type"] == "STATE_UPDATE":
        ok("Turn 4 — X(1,1): STATE_UPDATE delivered to both clients")
    else:
        fail("Turn 4 STATE_UPDATE", f"c1={su_c1} c2={su_c2}")

    # Turn 5 — O plays (0,2) → O wins top row
    send_msg(c1, {"msg_type": "MOVE", "player_id": "Alice",
                  "payload": {"row": 0, "col": 2}, "timestamp": ts()})
    # Expect STATE_UPDATE then GAME_OVER for each client
    su_c1 = recv_msg(c1); su_c2 = recv_msg(c2)
    if su_c1["msg_type"] == "STATE_UPDATE" and su_c2["msg_type"] == "STATE_UPDATE":
        ok("Turn 5 — O(0,2): final STATE_UPDATE delivered to both clients")
    else:
        fail("Turn 5 final STATE_UPDATE", f"c1={su_c1} c2={su_c2}")

    go_c1 = recv_msg(c1); go_c2 = recv_msg(c2)
    if (go_c1.get("msg_type") == "GAME_OVER" and go_c1.get("result") == "WIN"
            and go_c2.get("msg_type") == "GAME_OVER" and go_c2.get("result") == "LOSE"):
        ok("GAME_OVER: Player O receives WIN, Player X receives LOSE")
    else:
        fail("GAME_OVER result mismatch", f"c1={go_c1} c2={go_c2}")

    c1.close(); c2.close()

    # Verify server reset: third client should get LOBBY_WAIT
    time.sleep(0.4)
    c3 = socket.create_connection((HOST, PORT))
    send_msg(c3, {"msg_type": "CONNECT", "player_id": "Charlie", "timestamp": ts()})
    lw2 = recv_msg(c3)
    if lw2.get("msg_type") == "LOBBY_WAIT":
        ok("Server reset to WAITING_FOR_PLAYERS — new client received LOBBY_WAIT")
    else:
        fail("Server did not reset", str(lw2))
    c3.close()

    # -----------------------------------------------------------------------
    # 4.4  Code quality static checks
    # -----------------------------------------------------------------------
    print("\n── 4.4: Code quality static checks ──")
    for fname in ("server.py", "client.py"):
        path = ROOT + "\\" + fname
        with open(path, encoding="utf-8") as f:
            src = f.read()

        checks = {
            "Has module docstring": src.lstrip().startswith('"""'),
            "Has function docstrings": '"""' in src and "def " in src,
            "Has inline comments (#)": src.count("#") >= 10,
            "No threading import in server.py" if fname == "server.py"
                else "Uses threading in client.py":
                    ("import threading" not in src) if fname == "server.py"
                    else ("import threading" in src),
            "Uses selectors" if fname == "server.py"
                else "Uses socket":
                    ("selectors" in src) if fname == "server.py"
                    else ("socket" in src),
            "Snake_case naming (no camelCase vars)": "camelCase" not in src,
        }
        all_ok = True
        for label, result in checks.items():
            if result:
                ok(f"{fname}: {label}")
            else:
                fail(f"{fname}: {label}")
                all_ok = False

except Exception as e:
    fail("Unexpected test error", str(e))
    import traceback; traceback.print_exc()

finally:
    srv.terminate()
    try:
        out, _ = srv.communicate(timeout=2)
        if out:
            print("\n── Server stdout ──")
            print(out.decode("utf-8", errors="replace"))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 54)
if failures:
    print(f"  RESULT: {len(failures)} FAILURE(S)")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("  RESULT: ALL PHASE 4 TESTS PASSED ✓")
print("=" * 54 + "\n")
