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

When the message is received we are able to coalesce these bytes into a string. This is becasue each message is terminated with a /n character. When we are reading the packet we can build a string until we reach a /n charcter. Once we reach a /n character we know that that message is complete and to move onto the next one.

### Example Wire Stream
Imagine this string of messages. 
``` JSON
{"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":0,"col":2},"timestamp":1727000005}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":1,"col":2},"timestamp":1727000010}\n
```

If the string above is split into multiple recv() chunks.
recv() 1:
``` code
{"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000}\n{"msg_type":"MOVE","player_id":"Alice","
```
recv() 2:
```code
payload":{"row":0,"col":2},"timestamp":1727000005}\n{"msg_type":"MOVE","player_id":"Alice","payload":{"row":1,"col":2},"timestamp":1727000010}\n
```

These would be sent seperately and then read in. It will see that they are not complete after the first one and so wait for the second one and then stich them together.
``` JSON
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

### Expected Termination

This occurs when the player sends the server a DISCONNECT to quit the game.



