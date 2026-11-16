"""
test_qol_session.py - Verification for QOL Section 3: Session Tracking & Post-Game Menu
"""

import json
import socket
import subprocess
import sys
import threading
import time

import client

PYTHON = sys.executable
HOST = "127.0.0.1"
PORT = 54323


def run_mock_server(port, stop_evt):
    """Simple single-threaded mock server to simulate 2 back-to-back games."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, port))
    server.listen(1)
    server.settimeout(2.0)

    try:
        # Match 1: Client connects, gets LOBBY_WAIT, then GAME_START 'O', then GAME_OVER 'WIN'
        while not stop_evt.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue

            conn.settimeout(2.0)
            raw = conn.recv(1024).decode("utf-8")
            connect_msg = json.loads(raw.strip())
            assert connect_msg["msg_type"] == "CONNECT"

            # Send GAME_START as role O
            conn.sendall((json.dumps({"msg_type": "GAME_START", "role": "O", "timestamp": int(time.time())}) + "\n").encode("utf-8"))
            time.sleep(0.2)

            # Send GAME_OVER WIN
            conn.sendall((json.dumps({"msg_type": "GAME_OVER", "result": "WIN", "timestamp": int(time.time())}) + "\n").encode("utf-8"))
            time.sleep(0.2)
            conn.close()
            break

        # Match 2: Client reconnects, gets GAME_START 'X', then GAME_OVER 'LOSE_FORFEIT'
        while not stop_evt.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue

            conn.settimeout(2.0)
            raw = conn.recv(1024).decode("utf-8")
            connect_msg = json.loads(raw.strip())
            assert connect_msg["msg_type"] == "CONNECT"

            # Send GAME_START as role X
            conn.sendall((json.dumps({"msg_type": "GAME_START", "role": "X", "timestamp": int(time.time())}) + "\n").encode("utf-8"))
            time.sleep(0.2)

            # Send GAME_OVER LOSE_FORFEIT
            conn.sendall((json.dumps({"msg_type": "GAME_OVER", "result": "LOSE_FORFEIT", "timestamp": int(time.time())}) + "\n").encode("utf-8"))
            time.sleep(0.2)
            conn.close()
            break

    finally:
        server.close()


def main():
    print("Starting QOL Session & Score Tracking Test...")
    stop_evt = threading.Event()
    srv_thread = threading.Thread(target=run_mock_server, args=(PORT, stop_evt), daemon=True)
    srv_thread.start()
    time.sleep(0.3)

    c = client.TicTacToeClient("TestPlayer", HOST, PORT)

    # --- Match 1 ---
    print("\n[TEST] Connecting to Match 1...")
    connected = c._connect_to_server(HOST, PORT)
    assert connected, "Failed to connect to mock server"
    assert c.sock is not None, "Socket was not created"

    # Simulate running match 1
    # We unblock input_loop by simulating stop event when game over received
    c.my_role = None
    c.board = [["" for _ in range(3)] for _ in range(3)]
    c.current_turn = "O"
    c.game_active = False
    c.game_over = False
    c._stop_event = threading.Event()

    client.send_msg(c.sock, {"msg_type": "CONNECT", "player_id": c.player_id, "timestamp": client.ts()})
    c.receiver = client.ReceiverThread(c.sock, on_message=c._on_message, on_disconnect=c._on_server_disconnect)
    c.receiver.start()

    # Wait for match 1 GAME_OVER to arrive
    for _ in range(20):
        if c.game_over:
            break
        time.sleep(0.1)

    assert c.game_over, "GAME_OVER was not received in Match 1"
    assert c.wins == 1, f"Expected wins=1, got {c.wins}"
    assert c.losses == 0, f"Expected losses=0, got {c.losses}"
    assert c.draws == 0, f"Expected draws=0, got {c.draws}"
    assert c.forfeits == 0, f"Expected forfeits=0, got {c.forfeits}"

    # Clean reset
    if c.receiver:
        c.receiver.join(timeout=1.0)
    if c.sock:
        c.sock.close()
        c.sock = None

    print("[PASS] Match 1 completed. Cumulative score: Wins=1, Losses=0, Draws=0, Forfeits=0")

    # --- Match 2: Reconnect (Option 1 behavior) ---
    print("\n[TEST] Reconnecting for Match 2 (verifying brand-new socket)...")
    connected2 = c._connect_to_server(HOST, PORT)
    assert connected2, "Failed to reconnect to mock server"
    assert c.sock is not None, "Brand-new socket was not created"

    c.my_role = None
    c.board = [["" for _ in range(3)] for _ in range(3)]
    c.current_turn = "O"
    c.game_active = False
    c.game_over = False
    c._stop_event = threading.Event()

    client.send_msg(c.sock, {"msg_type": "CONNECT", "player_id": c.player_id, "timestamp": client.ts()})
    c.receiver = client.ReceiverThread(c.sock, on_message=c._on_message, on_disconnect=c._on_server_disconnect)
    c.receiver.start()

    # Wait for match 2 GAME_OVER to arrive
    for _ in range(20):
        if c.game_over:
            break
        time.sleep(0.1)

    assert c.game_over, "GAME_OVER was not received in Match 2"
    assert c.wins == 1, f"Expected wins=1, got {c.wins}"
    assert c.losses == 1, f"Expected losses=1, got {c.losses}"
    assert c.draws == 0, f"Expected draws=0, got {c.draws}"
    assert c.forfeits == 1, f"Expected forfeits=1, got {c.forfeits}"

    if c.receiver:
        c.receiver.join(timeout=1.0)
    if c.sock:
        c.sock.close()
        c.sock = None

    print("[PASS] Match 2 completed. Cumulative score: Wins=1, Losses=1, Draws=0, Forfeits=1")

    # Test DNS check for invalid host
    print("\n[TEST] Testing DNS resolution check on invalid host...")
    failed_conn = c._connect_to_server("nonexistent.invalid.host.xyz", 8080)
    assert not failed_conn, "Expected failed connection for invalid host"
    print("[PASS] Invalid DNS correctly handled with error message")

    stop_evt.set()
    srv_thread.join(timeout=1.0)
    print("\nALL QOL SECTION 3 TESTS PASSED!")


if __name__ == "__main__":
    main()
