# FSM Specification
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
