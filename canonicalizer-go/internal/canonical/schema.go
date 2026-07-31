package canonical

import (
	"crypto/sha256"
	"encoding/hex"
	"math/big"
	"os"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
)

// 域标签来源名（domain-tags-v1）。
var domainNames = []string{
	"DDTM_ROW_V1",
	"DDTM_PADDING_V1",
	"DDTM_NODE_V1",
	"DDTM_SCHEMA_V1",
}

// SchemaDigest 返回规范化 schema 文件原始字节的 SHA-256。
func SchemaDigest(path string) ([]byte, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(raw)
	return sum[:], nil
}

// SchemaHalves 返回 (hi, lo)——两个 128 位大端域整数。
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

// SchemaSHA256Hex 返回 schema 摘要的十六进制编码。
func SchemaSHA256Hex(path string) (string, error) {
	d, err := SchemaDigest(path)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(d), nil
}

// DomainTags 返回每个标签名的 SHA-256(name) mod p。
func DomainTags(modulus *big.Int) map[string]fr.Element {
	_ = modulus // 模数已由 fr.Element 隐含
	tags := make(map[string]fr.Element, len(domainNames))
	for _, name := range domainNames {
		sum := sha256.Sum256([]byte(name))
		var e fr.Element
		e.SetBigInt(new(big.Int).SetBytes(sum[:]))
		tags[name] = e
	}
	return tags
}
