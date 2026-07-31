package canonical

import (
	"crypto/sha256"
	"encoding/hex"
	"math/big"
	"os"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
)

// Domain tag source names (domain-tags-v1).
var domainNames = []string{
	"DDTM_ROW_V1",
	"DDTM_PADDING_V1",
	"DDTM_NODE_V1",
	"DDTM_SCHEMA_V1",
}

// SchemaDigest returns SHA-256 of the raw canonical schema file bytes.
func SchemaDigest(path string) ([]byte, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(raw)
	return sum[:], nil
}

// SchemaHalves returns (hi, lo) as two 128-bit big-endian field elements.
func SchemaHalves(path string) (fr.Element, fr.Element, error) {
	digest, err := SchemaDigest(path)
	if err != nil {
		return fr.Element{}, fr.Element{}, err
	}
	var hi, lo fr.Element
	hi.SetBigInt(new(big.Int).SetBytes(digest[:16]))
	lo.SetBigInt(new(big.Int).SetBytes(digest[16:]))
	return hi, lo, nil
}

// SchemaSHA256Hex returns the hex encoding of the schema digest.
func SchemaSHA256Hex(path string) (string, error) {
	d, err := SchemaDigest(path)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(d), nil
}

// DomainTags returns SHA-256(name) mod p for every tag name.
func DomainTags(modulus *big.Int) map[string]fr.Element {
	_ = modulus // modulus implied by fr.Element
	tags := make(map[string]fr.Element, len(domainNames))
	for _, name := range domainNames {
		sum := sha256.Sum256([]byte(name))
		var e fr.Element
		e.SetBigInt(new(big.Int).SetBytes(sum[:]))
		tags[name] = e
	}
	return tags
}
