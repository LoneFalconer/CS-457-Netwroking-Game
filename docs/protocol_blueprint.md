# Application Protocol Blueprint

## Transport Protocol, Serialization, and Framing

### Transport Protocol:

This tic-tac-toe application will use TCP as its transport protocol.

### Serialzitiaon

This application will use JSON to serialize the messages.

### Framing 

Each message is one JSON object that is terminated with a \n character. 

### Fragmentation 

Messages will be fragmented up and packed inside a TCP packet. This packet is then sent over the wire to then be received dand coalesced. 

### Coalescing

When the message is received, we put these bytes into a stream/buffer. Because each message is terminated with a /n character, we can then coalesce the bytes. When we reach a /n character, we know that the message is complete; we then push the finished message to a queue and continue to receive more if there is more data.

### Example Wire Stream
Imagine this string of messages. 
```
{"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":0,"col":2},"timestamp":1727000005}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":1,"col":2},"timestamp":1727000010}\n
```

If the string above is split into multiple recv() chunks.
recv() 1:
```
{"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000}\n{"msg_type":"MOVE","player_id":"Alice","
```
recv() 2:
```
payload":{"row":0,"col":2},"timestamp":1727000005}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":1,"col":2},"timestamp":1727000010}\n
```

These would be sent seperately and then read into a bytestream or buffer and go through the process described above under **Coalescing**.
```
{"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":0,"col":2},"timestamp":1727000005}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":1,"col":2},"timestamp":1727000010}\n
```

## Schema Definitions

### Overview Table
| Message Type | Direction | Description |
| -------- | -------- | -------- |
| CONNECT | Client $\rightarrow$ Server | Client requests to join the room with a gammer tag. |
| LOBBY_WAIT | Server $\rightarrow$ Client | Server notifies Client that it is waiting for other Client. |
| GAME_START | Server $\rightarrow$ Client | Server notifies Client that the game has started and assigns sides. |
| MOVE | Client $\rightarrow$ Server | Client notifies the Server that it wants to make a move. |
| STATE_UPDATE | Server $\rightarrow$ Client | Server notifies the Client of an update in the game state. |
| ERROR | Server $\rightarrow$ Client | Server notifies the Client that a move was invalid or a message was malformed. |
| DISCONNECT | Client $\rightarrow$ Server | Client notifies the Server that it is quiting. |
| GAME_OVER | Server $\rightarrow$ Client | Server notifies the client that the game is over and what the results are. |

### CONNECT
```
Format: CONNECT|<PLAYER_ID>|<TIMESTAMP>\n
Example: CONNECT|Player_1|CoolMan123|1727000005\n
Fields:
  - MSG_TYPE   (string)  : "CONNECT"
  - PLAYER_ID  (string)  : Alphanumeric alias of active player (e.g. "Player_1")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds
```

### LOBBY_WAIT
```
Format: LOBBY_WAIT|<ROLE>|<TIMESTAMP>\n
Example: LOBBY_WAIT|"X"|1727000006\n
Fields:
  - MSG_TYPE   (string)  : "LOBBY_WAIT"
  - ROLE  (string)  : Alphanumeric role of player (e.g. "O", or "X:)
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds
```

### GAME_START
```
Format: GAME_START|<TIMESTAMP>\n
Example: GAME_START|1727000007\n
Fields:
  - MSG_TYPE   (string)  : "GAME_START"
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds
```

### MOVE
```
Format: MOVE|<PLAYER_ID>|<ROW>,<COL>|<TIMESTAMP>\n
Example: MOVE|Player_1|0,2|1727000008\n
Fields:
  - MSG_TYPE   (string)  : "MOVE"
  - PLAYER_ID  (string)  : Alphanumeric alias of active player (e.g. "Player_1")
  - PAYLOAD    (integers): <row>,<col> zero-indexed grid coordinates (e.g. "0,2")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds
```

### STATE_UPDATE
```
Format: STATE_UPDATE|<ROW>,<COL>|<TIMESTAMP>\n
Example: STATE_UPDATE|0,1|1727000009\n
Fields:
  - MSG_TYPE   (string)  : "STATE_UPDATE"
  - PAYLOAD    (integers): <row>,<col> zero-indexed grid coordinates (e.g. "0,1")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds
```


### ERROR
```
Format: ERROR|ERROR_CODE|<TIMESTAMP>\n
Example: ERROR|112|1727000009\n
Fields:
  - MSG_TYPE   (string)  : "ERROR"
  - ERROR_CODE    (integer): Describes the specific error (e.g. 112)
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds
```

### DISCONNECT
```
Format: DISCONNECT|<PLAYER_ID>|<TIMESTAMP>\n
Example: DISCONNECT|Player_1|CoolMan123|1727000005\n
Fields:
  - MSG_TYPE   (string)  : "DISCONNECT"
  - PLAYER_ID  (string)  : Alphanumeric alias of active player (e.g. "Player_1")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds
```

### GAME_OVER
```
Format: GAME_OVER|<RESULT>|<TIMESTAMP>\n
Example: GAME_OVER|WIN|CoolMan123|1727000005\n
Fields:
  - MSG_TYPE   (string)  : "GAME_OVER"
  - RESULT  (string)  : Result of match for player (e.g. "WIN")
  - TIMESTAMP  (integer) : Unix epoch timestamp in seconds
```

## Connection Termination and Lifecycle

### Application Disconnect

This occurs when the player sends the server a DISCONNECT to quit the game before terminating the connection. The server is then able to clean up the TCP connection via a TCP 4-way FIN handshake.

Flow:
1. User sends DISCONNECT to server.
2. Server sends GAME_OVER to any remaining clients.
3. Server closes the disconnected user's socket.
4. Clean up the game state.

### TCP 0-byte EOF Rule

If recv() is called after the server closes the socket connection cleanly, then it will return 0 bytes or b"" in Python. This value, b"", represents the End-Of-File (EOF), which indicates that the connection is closed on the other side. That means that when we are keeping the connection open with while True, we must check whether or not there is still data with a while not data: break line.

### Abrupt Termination

This happens when unexpected behaviour occurs that causes the termination of the game. This could be a client crashing, wifi/ethernet disconnecting, TCP RST, kill -9, etc. This means that no 4-way TCP FIN handshake is completed, and a TCP timeout or RST will occur.

Flow:

1. Error occurs, and connection is lost.
2. EOF socket exception occurs and is caught.
3. Forfeit any active game and send GAME_OVER to opponent.
4. Close the socket of the disconnected player.
5. Clean up game state.

Here are three examples of possible network link failures or crashes.

TCP RST:
This occurs when a connection is forcibly closed, or a crash occurs. A ConnectionResetError will be thrown, and we will handle that by treating the player as if they disconnected and clean up.

BrokenPipeError:
This occurs when a host tries to send data to a socket that is already closed. A BrokenPipeError will be thrown and will be caught and recovered from. Again, we will treat the player as disconnected and clean up.
