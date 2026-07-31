// Command export-poseidon-params 导出 gnark-crypto v0.20.1 所用的 BN254 Poseidon2
// width-4 精确参数，连同已知答案测试（KAT）向量。输出的 JSON 是 Python 与 Rust 参考
// 实现共同消费的唯一真相来源，使每种语言运行完全相同的置换、进而得到完全相同的
// Merkle 根。
//
// 我们刻意钉定 width=4。gnark-crypto 仅对 t∈{4,8,12,16} 硬编码了经审计的常量；
// t=2,3 在运行时经 Keccak 派生，会迫使每个重实现都复刻 gnark-crypto 基于 Keccak
// 的密钥排程。width 4 使用硬编码、经审计的常量，且是其中最小的宽度，把跨语言必须
// 保持同步的常量面降到最小。
package main

import (
	"encoding/json"
	"fmt"
	"math/big"
	"os"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr/poseidon2"
)

// ParamFile 是冻结的 Poseidon2 实例在磁盘上的表示。
type ParamFile struct {
	Protocol       string     `json:"protocol"`
	Version        int        `json:"version"`
	Field          string     `json:"field"`
	Modulus        string     `json:"modulus"`
	Width          int        `json:"width"`
	FullRounds     int        `json:"full_rounds"`
	PartialRounds  int        `json:"partial_rounds"`
	SBoxDegree     int        `json:"sbox_degree"`
	DiagM1         []string   `json:"diag_m1"`
	RoundKeys      [][]string `json:"round_keys"`
	RoundKeyWidths []int      `json:"round_key_widths"`
	KAT            []KAT      `json:"kat"`
	ParameterSource string    `json:"parameter_source"`
}

// KAT 是置换的一条已知答案测试向量。
type KAT struct {
	Input  []string `json:"input"`
	Output []string `json:"output"`
}

// elementHex 把 fr.Element 渲染为 0x 前缀的大端规范整数字符串
// （与 fr.Element.Bytes() 的字节序一致）。
func elementHex(e fr.Element) string {
	b := e.Bytes()
	return "0x" + new(big.Int).SetBytes(b[:]).Text(16)
}

func katFor(input []string) KAT {
	width := len(input)
	buf := make([]fr.Element, width)
	for i, s := range input {
		v, ok := new(big.Int).SetString(s, 0)
		if !ok {
			panic("bad input " + s)
		}
		buf[i].SetBigInt(v)
	}
	perm := poseidon2.NewPermutation(width, 8, 56)
	if err := perm.Permutation(buf); err != nil {
		panic(err)
	}
	out := make([]string, width)
	for i := range buf {
		out[i] = elementHex(buf[i])
	}
	return KAT{Input: input, Output: out}
}

func main() {
	const width = 4
	// NewParameters 返回导出的参数结构体（Width、RoundKeys、DiagM1……）。
	// 它读取 t=4 的硬编码经审计常量。
	params := poseidon2.NewParameters(width, 8, 56)

	// BN254 标量域模数。
	modulus := fr.Modulus()

	out := ParamFile{
		Protocol:        "DDTM-POSEIDON2-BN254",
		Version:         1,
		Field:           "BN254 scalar field",
		Modulus:         "0x" + modulus.Text(16),
		Width:           width,
		FullRounds:      params.NbFullRounds,
		PartialRounds:   params.NbPartialRounds,
		SBoxDegree:      poseidon2.DegreeSBox(),
		DiagM1:          make([]string, len(params.DiagM1)),
		RoundKeys:       make([][]string, len(params.RoundKeys)),
		RoundKeyWidths:  make([]int, len(params.RoundKeys)),
		ParameterSource: "gnark-crypto v0.20.1 hardcoded BN254 width-4 constants",
	}

	for i, e := range params.DiagM1 {
		out.DiagM1[i] = elementHex(e)
	}
	for i, round := range params.RoundKeys {
		out.RoundKeyWidths[i] = len(round)
		out.RoundKeys[i] = make([]string, len(round))
		for j, e := range round {
			out.RoundKeys[i][j] = elementHex(e)
		}
	}

	// KAT 向量：一组有代表性的输入。它们让 Python 与 Rust 重实现证明自己能精确
	// 重现 gnark-crypto。
	out.KAT = []KAT{
		katFor([]string{"0x0", "0x0", "0x0", "0x0"}),
		katFor([]string{"0x1", "0x2", "0x3", "0x4"}),
		katFor([]string{"0xa", "0xb", "0xc", "0xd"}),
		katFor([]string{
			"0x123456789abcdef0123456789abcdef0",
			"0xfedcba9876543210fedcba9876543210",
			"0x1",
			"0x2",
		}),
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(&out); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
