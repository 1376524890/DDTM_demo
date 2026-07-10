# Buyer verification

After `KEY_RELEASED`, the buyer retrieves the exact digest-checked ciphertext and key envelope, opens RSA-OAEP, authenticates AES-GCM and inspects the decrypted payload before calling `confirm`. Failure is evidence for `openDispute`; silence after successful delivery permits seller settlement when the dispute window expires.
