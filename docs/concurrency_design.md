# Rubric: Sprint 2 - Game Behavior & Server Concurrency Architecture Design

**Course:** CS 457 - Computer Networks  
**Deliverable:** Server Concurrency Architecture & Mermaid Sequence Diagram Specification (Markdown committed to Git)  
**Total Points:** 150 Points  

---

## Overview

Sprint 2 focuses on designing the server's concurrency model, thread safety, and client synchronization logic. Students select their concurrency architecture (multi-threading or non-blocking I/O multiplexing), define shared-state isolation / lock acquisition strategies, and document the client-server interaction flow using Mermaid sequence diagrams.

> [!IMPORTANT]
> **Mermaid Requirement:** All sequence diagrams **must be authored directly in Mermaid syntax (`sequenceDiagram`)** within the Markdown files. Diagrams must render cleanly in GitHub.

---

## Evaluation Criteria Breakdown

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        SPRINT 2 GRADING RUBRIC (150 POINTS)                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Server Concurrency Architecture & Connection Lifecycle                      050 pts │
│ 2. Thread Safety, Lock Acquisition & State Isolation Strategy                  050 pts │
│ 3. Mermaid Sequence Diagram (`sequenceDiagram`) Syntax & Rendering             025 pts │
│ 4. Move Validation, Turn Enforcement & State Broadcast Flow                    025 pts │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TOTAL                                                                         150 pts  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Grading Criteria

### Part 1: Server Concurrency & Thread-Safety Design (100 Points)

#### 1. Server Concurrency Architecture & Connection Lifecycle (50 Points)
- **50 Points (Full Credit):** Submits a comprehensive architecture document defining the chosen concurrency model (multi-threading with worker threads per client socket OR non-blocking I/O multiplexing using `selectors`/`select`). Details the complete connection lifecycle from listening socket accept, client registration, active game loop servicing, through to client socket teardown.
- **30 Points (Partial Credit):** Concurrency model is identified, but connection lifecycle, socket servicing mechanisms, or multi-client capacity planning are vague or underspecified.
- **10 Points (Minimal Credit):** High-level summary provided without clear architectural mechanics.
- **0 Points (No Credit):** Concurrency architecture document missing or relies on single-threaded blocking sockets without multiplexing.

#### 2. Thread Safety, Lock Acquisition & State Isolation Strategy (50 Points)
- **50 Points (Full Credit):** Explicitly documents shared resources (e.g., game board matrix, active turn state, connected client socket list, round scores) and specifies how race conditions are prevented. For multi-threading, details exact `threading.Lock` acquisition/release patterns (critical sections). For non-blocking event loops, details single-threaded execution state safety and event-driven isolation.
- **30 Points (Partial Credit):** Mentions locks or event loop, but lacks analysis of specific shared state variables or fails to define critical sections where race conditions could corrupt data.
- **10 Points (Minimal Credit):** Superficial mention of thread safety without actionable locking strategies.
- **0 Points (No Credit):** Thread safety / state isolation analysis is completely omitted.

---

### Part 2: State Synchronization & Mermaid Sequence Diagram (50 Points)

#### 3. Mermaid Sequence Diagram (`sequenceDiagram`) Syntax & Rendering (25 Points)
- **25 Points (Full Credit):** The sequence diagram is authored strictly in **Mermaid syntax (`sequenceDiagram`)** embedded in the Markdown file (`concurrency_design.md` or `sequence_diagram.md`). The diagram compiles without syntax errors and renders automatically on GitHub.
- **15 Points (Partial Credit):** Mermaid syntax is used, but contains syntax errors that prevent clean rendering, or uses static raster images/ASCII without providing valid Mermaid source code.
- **0 Points (No Credit):** Mermaid diagram missing, or diagram submitted only as an external PDF/unsupported binary format.

#### 4. Move Validation, Turn Enforcement & State Broadcast Flow (25 Points)
- **25 Points (Full Credit):** Sequence diagram and narrative accurately illustrate the complete round-trip flow: client sending move request $\rightarrow$ server validating active turn and move legality $\rightarrow$ state mutation $\rightarrow$ synchronous broadcast of `STATE_UPDATE` to all connected clients $\rightarrow$ score/leaderboard synchronization. Explicitly models branching logic (`alt` / `else`) for invalid/out-of-turn moves returning `ERROR`.
- **15 Points (Partial Credit):** Sequence diagram illustrates happy path move flow, but omits out-of-turn rejection, error responses, or simultaneous broadcast synchronization to the non-active client.
- **0 Points (No Credit):** State synchronization and message flow sequence missing.

---

## Submission Checklist

- [ ] All deliverables are Markdown (`.md`) files committed directly to the Git repository.
- [ ] No binary PDFs submitted in place of Markdown files.
- [ ] Public Git repository URL submitted to Canvas by **Sunday, October 18 at 11:59 PM**.
- [ ] Sequence diagram is rendered with native **Mermaid (`sequenceDiagram`)** syntax.
- [ ] Thread safety / locking strategy and turn broadcast synchronization are fully documented.
