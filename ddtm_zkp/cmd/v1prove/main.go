package main

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"math/big"
	"os"
	"path/filepath"

	"ddtm_zkp/v1/circuits"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
)

type request struct {
	Blocks     []string `json:"blocks"`
	EncRand    []string `json:"encRand"`
	Key        string   `json:"key"`
	RD         string   `json:"rD"`
	RQ         string   `json:"rQ"`
	RK         string   `json:"rK"`
	REnc       string   `json:"rEnc"`
	MinPresent string   `json:"minPresent"`
	MaxValue   string   `json:"maxValue"`
	MaxAge     string   `json:"maxAge"`
	AsOfTime   string   `json:"asOfTime"`
	Context    string   `json:"context"`
	BuyerKey   string   `json:"buyerKey"`
}

type commitments struct {
	CD     string `json:"cD"`
	CQ     string `json:"cQ"`
	CK     string `json:"cK"`
	ZKRoot string `json:"zkRoot"`
}

type response struct {
	Type         string      `json:"type"`
	Curve        string      `json:"curve"`
	Scheme       string      `json:"scheme"`
	Commitments  commitments `json:"commitments"`
	Proof        string      `json:"proof,omitempty"`
	PublicInputs []string    `json:"publicInputs,omitempty"`
	Binding      string      `json:"binding,omitempty"`
	KeyEnvelope  string      `json:"keyEnvelope,omitempty"`
}

type material struct {
	blocks  [circuits.BlockCount]*big.Int
	encRand [circuits.BlockCount]*big.Int
	key     *big.Int
	rD      *big.Int
	rQ      *big.Int
	rK      *big.Int
	rEnc    *big.Int
}

func main() {
	proofType := flag.String("type", "", "commitments, quality, key, or delivery")
	artifactsDir := flag.String("artifacts", "artifacts/v1", "directory containing setup artifacts")
	flag.Parse()

	var req request
	decoder := json.NewDecoder(os.Stdin)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		fatal(fmt.Errorf("decode request: %w", err))
	}

	mat, err := parseMaterial(req)
	if err != nil {
		fatal(err)
	}
	comm := computeCommitments(mat)
	out := response{Type: *proofType, Curve: "BN254", Scheme: "Groth16", Commitments: comm}

	switch *proofType {
	case "commitments":
		// No proof is generated. This operation is used before the buyer and transaction context are known.
	case "quality":
		if err := generateQuality(*artifactsDir, req, mat, &out); err != nil {
			fatal(err)
		}
	case "key":
		if err := generateKey(*artifactsDir, req, mat, &out); err != nil {
			fatal(err)
		}
	case "delivery":
		if err := generateDelivery(*artifactsDir, req, mat, &out); err != nil {
			fatal(err)
		}
	default:
		fatal(errors.New("--type must be commitments, quality, key, or delivery"))
	}

	encoded, err := json.Marshal(out)
	if err != nil {
		fatal(err)
	}
	fmt.Println(string(encoded))
}

func parseMaterial(req request) (material, error) {
	var out material
	if len(req.Blocks) != circuits.BlockCount {
		return out, fmt.Errorf("blocks must contain %d decimal field elements", circuits.BlockCount)
	}
	if len(req.EncRand) != circuits.BlockCount {
		return out, fmt.Errorf("encRand must contain %d decimal field elements", circuits.BlockCount)
	}
	var err error
	for i := 0; i < circuits.BlockCount; i++ {
		if out.blocks[i], err = scalar(req.Blocks[i]); err != nil {
			return out, fmt.Errorf("blocks[%d]: %w", i, err)
		}
		if out.encRand[i], err = scalar(req.EncRand[i]); err != nil {
			return out, fmt.Errorf("encRand[%d]: %w", i, err)
		}
	}
	if out.key, err = scalar(req.Key); err != nil {
		return out, fmt.Errorf("key: %w", err)
	}
	if out.rD, err = scalar(req.RD); err != nil {
		return out, fmt.Errorf("rD: %w", err)
	}
	if out.rQ, err = scalar(req.RQ); err != nil {
		return out, fmt.Errorf("rQ: %w", err)
	}
	if out.rK, err = scalar(req.RK); err != nil {
		return out, fmt.Errorf("rK: %w", err)
	}
	if out.rEnc, err = scalar(req.REnc); err != nil {
		return out, fmt.Errorf("rEnc: %w", err)
	}
	return out, nil
}

func computeCommitments(mat material) commitments {
	return commitments{
		CD:     circuits.DataCommitment(mat.blocks, mat.rD).String(),
		CQ:     circuits.QualityCommitment(mat.blocks, mat.rQ).String(),
		CK:     circuits.KeyCommitment(mat.key, mat.rK).String(),
		ZKRoot: circuits.DeliveryRoot(mat.blocks, mat.encRand, mat.key).String(),
	}
}

func generateQuality(artifactsDir string, req request, mat material, out *response) error {
	minPresent, err := scalar(req.MinPresent)
	if err != nil {
		return fmt.Errorf("minPresent: %w", err)
	}
	maxValue, err := scalar(req.MaxValue)
	if err != nil {
		return fmt.Errorf("maxValue: %w", err)
	}
	maxAge, err := scalar(req.MaxAge)
	if err != nil {
		return fmt.Errorf("maxAge: %w", err)
	}
	asOfTime, err := scalar(req.AsOfTime)
	if err != nil {
		return fmt.Errorf("asOfTime: %w", err)
	}
	context, err := scalar(req.Context)
	if err != nil {
		return fmt.Errorf("context: %w", err)
	}
	cD, _ := new(big.Int).SetString(out.Commitments.CD, 10)
	cQ, _ := new(big.Int).SetString(out.Commitments.CQ, 10)
	binding := circuits.QualityBinding(cD, cQ, context)

	assignment := &circuits.QualityCircuit{
		RD: mat.rD, RQ: mat.rQ,
		CD: cD, CQ: cQ, MinPresent: minPresent, MaxValue: maxValue,
		MaxAge: maxAge, AsOfTime: asOfTime, Context: context, Binding: binding,
	}
	for i := range mat.blocks {
		assignment.Blocks[i] = mat.blocks[i]
	}
	proofHex, err := prove(filepath.Join(artifactsDir, "pi_q"), assignment)
	if err != nil {
		return err
	}
	out.Proof = proofHex
	out.Binding = binding.String()
	out.PublicInputs = decimals(cD, cQ, minPresent, maxValue, maxAge, asOfTime, context, binding)
	return nil
}

func generateKey(artifactsDir string, req request, mat material, out *response) error {
	buyerKey, err := scalar(req.BuyerKey)
	if err != nil {
		return fmt.Errorf("buyerKey: %w", err)
	}
	context, err := scalar(req.Context)
	if err != nil {
		return fmt.Errorf("context: %w", err)
	}
	cK, _ := new(big.Int).SetString(out.Commitments.CK, 10)
	keyEnvelope := circuits.KeyEnvelope(buyerKey, mat.key, mat.rEnc, context)
	binding := circuits.KeyBinding(cK, buyerKey, keyEnvelope, context)
	assignment := &circuits.KeyCircuit{
		Key: mat.key, RK: mat.rK, REnc: mat.rEnc,
		CK: cK, BuyerKey: buyerKey, KEnc: keyEnvelope, Context: context, Binding: binding,
	}
	proofHex, err := prove(filepath.Join(artifactsDir, "pi_key"), assignment)
	if err != nil {
		return err
	}
	out.Proof = proofHex
	out.Binding = binding.String()
	out.KeyEnvelope = keyEnvelope.String()
	out.PublicInputs = decimals(cK, buyerKey, keyEnvelope, context, binding)
	return nil
}

func generateDelivery(artifactsDir string, req request, mat material, out *response) error {
	context, err := scalar(req.Context)
	if err != nil {
		return fmt.Errorf("context: %w", err)
	}
	cD, _ := new(big.Int).SetString(out.Commitments.CD, 10)
	cK, _ := new(big.Int).SetString(out.Commitments.CK, 10)
	root, _ := new(big.Int).SetString(out.Commitments.ZKRoot, 10)
	binding := circuits.DeliveryBinding(cD, cK, root, context)
	assignment := &circuits.DeliveryCircuit{
		Key: mat.key, RD: mat.rD, RK: mat.rK,
		CD: cD, CK: cK, Root: root, Context: context, Binding: binding,
	}
	for i := range mat.blocks {
		assignment.Blocks[i] = mat.blocks[i]
		assignment.EncRand[i] = mat.encRand[i]
	}
	proofHex, err := prove(filepath.Join(artifactsDir, "pi_deliver"), assignment)
	if err != nil {
		return err
	}
	out.Proof = proofHex
	out.Binding = binding.String()
	out.PublicInputs = decimals(cD, cK, root, context, binding)
	return nil
}

func prove(prefix string, assignment frontend.Circuit) (string, error) {
	cs := groth16.NewCS(ecc.BN254)
	if err := readObject(prefix+".r1cs", cs); err != nil {
		return "", err
	}
	pk := groth16.NewProvingKey(ecc.BN254)
	if err := readObject(prefix+".pk", pk); err != nil {
		return "", err
	}
	vk := groth16.NewVerifyingKey(ecc.BN254)
	if err := readObject(prefix+".vk", vk); err != nil {
		return "", err
	}

	witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
	if err != nil {
		return "", fmt.Errorf("build witness: %w", err)
	}
	proof, err := groth16.Prove(cs, pk, witness)
	if err != nil {
		return "", fmt.Errorf("prove: %w", err)
	}
	publicWitness, err := witness.Public()
	if err != nil {
		return "", fmt.Errorf("public witness: %w", err)
	}
	if err := groth16.Verify(proof, vk, publicWitness); err != nil {
		return "", fmt.Errorf("local verification: %w", err)
	}

	var raw bytes.Buffer
	if _, err := proof.WriteRawTo(&raw); err != nil {
		return "", fmt.Errorf("serialize proof: %w", err)
	}
	if raw.Len() < 256 {
		return "", fmt.Errorf("serialized proof is %d bytes, expected at least 256", raw.Len())
	}
	return "0x" + hex.EncodeToString(raw.Bytes()[:256]), nil
}

func readObject(path string, reader interface{ ReadFrom(r interface{ Read([]byte) (int, error) }) (int64, error) }) error {
	file, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("open %s: %w", path, err)
	}
	defer file.Close()
	if _, err := reader.ReadFrom(file); err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}
	return nil
}

func scalar(value string) (*big.Int, error) {
	if value == "" {
		return nil, errors.New("value is required")
	}
	parsed, ok := new(big.Int).SetString(value, 10)
	if !ok || parsed.Sign() < 0 || parsed.Cmp(ecc.BN254.ScalarField()) >= 0 {
		return nil, errors.New("must be a non-negative decimal BN254 scalar")
	}
	return parsed, nil
}

func decimals(values ...*big.Int) []string {
	out := make([]string, len(values))
	for i, value := range values {
		out[i] = value.String()
	}
	return out
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
