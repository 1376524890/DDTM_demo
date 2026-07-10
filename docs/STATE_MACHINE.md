# Executable V1 state machine

```text
LISTED -> ESCROWED -> QUALITY_VERIFIED -> DELIVERED -> KEY_RELEASED -> CONFIRMED
              |               |              |              |
              +-- timeout ----+--------------+--------------+--> REFUNDED
                                                             |
                                                             +--> DISPUTED
                                                                   |-- seller wins --> CONFIRMED
                                                                   |-- buyer wins  --> REFUNDED
                                                                   +-- timeout     --> REFUNDED
LISTED -- seller abort --> ABORTED
```

Only `CONFIRMED`, `REFUNDED` and `ABORTED` are terminal states. Settlement uses pull payments so an external recipient cannot re-enter the state transition.
