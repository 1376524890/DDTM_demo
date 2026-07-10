# V1 circuit data model

The V1 quality experiment uses four records. Each record occupies four BN254 field elements:

```text
[value, timestamp, present, reserved]
```

`present` is Boolean and a missing record must carry value zero. `reserved` must be zero. The quality circuit derives the number of present records, checks the minimum count, value upper bound and age bound, then commits the derived count. This deliberately small, fixed model allows reproducible end-to-end verification; later experiments can parameterize record count or aggregate recursive proofs.
