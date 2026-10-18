# Concurrency Architecture

## Concurrency Model:

I will be using Python's selectors for Non-Blocking I/O Multiplexing. This is ideal for my situation because my game is a two-player turn-based tic-tac-toe game. This means that there will not be a lot of clients at once.

The Selectors module allows a single thread to monitor connections and flag the socket when there is activity. This allows for both clients to send messages and for the server to process them without blocking and waiting for a specific client. The server will then handle any message based on the FSM specifications. This streamlines the process and reduces concerns about blocking, race conditions, and all the edge and error cases that come with multi-threading.

### Connection Lifecycle:

1. The server creates the selectors and a listening socket in non-blocking mode (socket.setblocking(False)). Then register the socket with the selector. Finally, the server starts the event loop.
2. The server accepts connections until there are two players.
2. A selector will be monitoring both of the client sockets for activity. In this case, Player 1 is the current player and Player 2 is waiting.
3. When one of the players sends data, the selector will flag the socket as readable.
4. The server will process the request in accordance with the FSM Specification. So if Player 2 sends an update, it won't apply it and send a message stating it was an out-of-turn move. If Player 1 sends an update, then it will process that and update the board if it is valid. If Player 1 waits too long to make a move, the server will end the game in a forfeit. Responses will be sent immediately; otherwise, they will be queued until the socket can accept the data.
5. Once the game is over, as determined by the server, it will move to evaluating the winner and broadcast this to each client. The server will then clean up the sockets and reset the game. If any unexpected timeouts or disconnects occur, such as recv() returning an empty byte string (b''), then the server will broadcast a forfeit to any remaining clients and enter cleanup.
6. Cleanup happens at the end of each game, no matter if there were unexpected disconnections or not. The server removes the socket's registration with the selector, and then the socket is removed from the socket list. Finally, the server closes the socket and resets the game board and state and readies itself for new clients to connect.

## Thread Safety and State Isolation

### State Safety

The server will be using Python's selectors module for single-threaded Non-Blocking I/O Multiplexing. Every message and change in game state will be processed by the event loop. This means that every event is handled sequentially and not concurrently.

### Shared Resources

The clients share the following resources that are maintained on the server side:
- Game board: The tic-tac-toe board with the moves of each player. The server will update the board upon a valid update and will evaluate the board after each move to check for a win, loss, or draw. 
- Active turn: The player who is expected to send an update with their move is always tracked by the server. The server will compare this value when deciding if an update is valid and will update this value at the end of a player's turn.
- Socket list: A list of the connected players. The server will update this when clients connect, disconnect, or clean up after a game.
- Timeout timer: This will start at the beginning of each player's turn to track how long they have taken to make a move. At the end of each turn, it will reset to track the other player. This will be checked by the event loop to decide if a player is active and if it has been over 60 seconds; then forfeit will be declared.

### Race Condition Prevention

The selector processes events sequentially and validates each move against the active turn. Therefore, if both active and non-active players send updates quickly in succession, the selector will flag that both sockets are ready to be read, and they will be processed sequentially. When a disconnect occurs, client sockets will be removed from the socket list, and the game-over conditions and cleanup will be handled sequentially according to the FSM specifications. This rigid sequential event-driven design protects the state of the game by validating before acting and keeping a strict sequential processing format using selectors.
