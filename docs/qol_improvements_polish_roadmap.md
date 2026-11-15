# Sprint 3 Quality of Life (QOL) & Polish Checklist

> **Instructions for AI Assistant (Antigravity):**
> Read this file and apply the three Quality of Life (QOL) updates below to `client.py` and `server.py`. 
> **CRITICAL RULE:** Do NOT alter any wire protocol JSON schemas, message types, framing (`\n`), or server FSM rules. As you complete and verify each item, update this file by changing `- [ ]` to `- [x]`.

---

## 1. Complete Emoji Removal (`client.py` & `server.py`)
Remove every Unicode emoji/icon (such as hourglasses `⏳`, checkmarks, crosses, trophies, etc.) from all `print()` statements, prompts, banners, and log messages.

- [x] **1.1 Zero Emojis in `client.py`:** Replace all emojis in lobby messages, turn status prompts, error messages, and game-over banners with clean, plain-ASCII tags such as `[INFO]`, `[WAIT]`, `[TURN]`, `[ERROR]`, and `[GAME OVER]`.
- [x] **1.2 Zero Emojis in `server.py`:** Ensure all server console logs use clean plain-ASCII prefixes (e.g., `[INIT]`, `[CONNECT]`, `[STATE]`, `[ERROR]`, `[CLEANUP]`).

---

## 2. Fixed-Width ASCII Board Alignment (`client.py`)
**Root Cause of Bug:** Previously, empty cells rendered a 3-character coordinate string (like `0,1`) while occupied cells rendered a 1-character symbol (`O` or `X`), causing vertical pipe separators (`|`) to shift horizontally whenever a cell was filled.

### Specification for Fixed-Width Board Rendering:
Every cell MUST occupy the exact same horizontal width regardless of whether it contains a coordinate hint or a player mark, OR row/column indices should be displayed cleanly along the top and left borders so every cell is strictly 3 characters wide (` X `, ` O `, or ` . ` / `   `).

**Option A (Recommended — Border Coordinates + Uniform 3-Char Cells):**
```text
    0   1   2
  +---+---+---+
0 | O |   | X |
  +---+---+---+
1 | X | X | O |
  +---+---+---+
2 | O | O | X |
  +---+---+---+
```

**Option B (If keeping inline coordinate hints for empty cells — Strict 5-Char Padded Cells):**
If rendering `row,col` inside empty cells, format every cell to a fixed width of 5 characters (`f" {cell:^3} "`):
- Empty cell `(0,1)` renders as `" 0,1 "` (5 chars)
- Occupied cell `O` renders as `"  O  "` (5 chars)
- Occupied cell `X` renders as `"  X  "` (5 chars)
```text
  O  | 0,1 |  X  
-----+-----+-----
  X  |  X  |  O  
-----+-----+-----
  O  |  O  |  X  
```

- [x] **2.1 Uniform Cell Width:** Update the board rendering function in `client.py` so every row and column separator (`|` and `+---+` or `-----+-----+-----`) aligns vertically with zero horizontal shifting as moves are made.
- [x] **2.2 Verify Alignment:** Test rendering an empty board, a partially filled board, and a full board to confirm pipes (`|`) never shift position.

---

## 3. Post-Game Session Loop & Persistent Score History (`client.py`)
Currently, `client.py` exits immediately after `GAME_OVER`, making the session score tracker (`Wins / Losses / Draws`) reset after 1 game. Wrap the client connection and match lifecycle inside a persistent session loop so the player keeps their score history across multiple games.

### Post-Game Menu Specification:
When a match ends (`GAME_OVER` received or opponent forfeits):
1. Close the current game socket cleanly and stop the current match's receiver thread/loop.
2. Update and display the cumulative **Session Score Summary**:
   ```text
   ========================================
   SESSION SCORE SUMMARY (Player: <player_id>)
   Wins: <W> | Losses: <L> | Draws: <D>
   ========================================
   ```
3. Prompt the user with a **Post-Game Menu**:
   ```text
   What would you like to do next?
   [1] Reconnect to same server (<current_host>:<current_port>)
   [2] Connect to a new host and port
   [3] Quit
   Select an option (1-3): 
   ```
4. **Menu Behavior:**
   - **Option `1` (Reconnect):** Creates a fresh TCP socket, connects to the existing `(server_ip, port)`, sends `CONNECT` with the user's `player_id`, resets the local 3x3 board, and starts a new match while keeping the cumulative `Wins / Losses / Draws` tally intact.
   - **Option `2` (New Host & Port):** Prompts the user for a new hostname/IP and port:
     - Validates that the new port is an integer between `1024` and `65535` (re-prompting cleanly if invalid).
     - Resolves the new hostname using the mandatory `socket.gethostbyname()` `try/except socket.gaierror` logic (printing the router DNS error message and allowing the user to re-enter or exit if resolution fails).
     - Connects to the new server, sends `CONNECT`, and preserves the session score history.
   - **Option `3` (or `q` / `Ctrl+C`):** Prints final session totals and exits cleanly (`sys.exit(0)`).

- [ ] **3.1 Persistent Session Tracker:** Maintain `wins`, `losses`, and `draws` across multiple matches in `client.py`.
- [ ] **3.2 Clean Socket/Thread Reset Between Matches:** Ensure the previous match's socket and receiver thread are fully closed/joined before starting the post-game menu prompt so stdin input does not conflict with an old background thread.
- [ ] **3.3 Implement Option 1 (Reconnect to Same Server):** Reconnects cleanly to the same `(hostname, port)` and starts a new game.
- [ ] **3.4 Implement Option 2 (Change Host & Port):** Prompts for new hostname and port, validates port (`1024-65535`), resolves DNS via `socket.gethostbyname()` catching `socket.gaierror`, and connects.
- [ ] **3.5 Implement Option 3 (Quit):** Prints final session summary and exits cleanly.
