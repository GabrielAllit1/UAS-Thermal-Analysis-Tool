# Security

Report security issues privately to the repository owner rather than opening a public issue with exploit details.

Never commit:

- license signing secrets or private keys
- API tokens or credentials
- customer inspection datasets
- proprietary vendor SDK binaries unless redistribution rights are explicitly documented

The legacy desktop licensing code uses symmetric HMAC verification and therefore requires a secret in the client package. That is a known architectural weakness. The modernization path is asymmetric signature verification: the client retains only a public verification key while signing remains offline/private.
