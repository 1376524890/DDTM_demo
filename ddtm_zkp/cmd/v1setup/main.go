package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"ddtm_zkp/v1/circuits"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
)

type manifestEntry struct {
	Name         string `json:"name"`
	Constraints  int    `json:"constraints"`
	PublicInputs int    `json:"publicInputs"`
	R1CSSHA256   string `json:"r1csSha256"`
	PKSHA256     string `json:"pkSha256"`
	VKSHA256     string `json:"vkSha256"`
	VerifierFile string `json:"verifierFile"`
}

type manifest struct {
	Version   string          `json:"version"`
	Curve     string          `json:"curve"`
	Scheme    string          `json:"scheme"`
	CreatedAt string          `json:"createdAt"`
	Circuits  []manifestEntry `json:"circuits"`
}

type circuitSpec struct {
	Name         string
	ContractName string
	PublicInputs int
	Circuit      frontend.Circuit
}

func main() {
	artifactsDir := flag.String("artifacts", "artifacts/v1", "directory for R1CS and proving/verifying keys")
	contractsDir := flag.String("contracts", "../ddtm_evm/contracts/generated", "directory for generated Solidity verifiers")
	flag.Parse()

	if err := os.MkdirAll(*artifactsDir, 0o755); err != nil {
		fatal(err)
	}
	if err := os.MkdirAll(*contractsDir, 0o755); err != nil {
		fatal(err)
	}

	specs := []circuitSpec{
		{Name: "pi_q", ContractName: "PiQVerifier", PublicInputs: 8, Circuit: &circuits.QualityCircuit{}},
		{Name: "pi_key", ContractName: "PiKeyVerifier", PublicInputs: 5, Circuit: &circuits.KeyCircuit{}},
		{Name: "pi_deliver", ContractName: "PiDeliverVerifier", PublicInputs: 5, Circuit: &circuits.DeliveryCircuit{}},
	}

	out := manifest{
		Version:   "ddtm-v1",
		Curve:     "BN254",
		Scheme:    "Groth16",
		CreatedAt: time.Now().UTC().Format(time.RFC3339),
	}

	for _, spec := range specs {
		entry, err := setupCircuit(spec, *artifactsDir, *contractsDir)
		if err != nil {
			fatal(fmt.Errorf("setup %s: %w", spec.Name, err))
		}
		out.Circuits = append(out.Circuits, entry)
		fmt.Printf("%-12s constraints=%d public=%d verifier=%s\n", entry.Name, entry.Constraints, entry.PublicInputs, entry.VerifierFile)
	}

	encoded, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		fatal(err)
	}
	if err := os.WriteFile(filepath.Join(*artifactsDir, "manifest.json"), append(encoded, '\n'), 0o644); err != nil {
		fatal(err)
	}
}

func setupCircuit(spec circuitSpec, artifactsDir, contractsDir string) (manifestEntry, error) {
	cs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, spec.Circuit)
	if err != nil {
		return manifestEntry{}, fmt.Errorf("compile: %w", err)
	}
	pk, vk, err := groth16.Setup(cs)
	if err != nil {
		return manifestEntry{}, fmt.Errorf("trusted setup: %w", err)
	}

	r1csPath := filepath.Join(artifactsDir, spec.Name+".r1cs")
	pkPath := filepath.Join(artifactsDir, spec.Name+".pk")
	vkPath := filepath.Join(artifactsDir, spec.Name+".vk")
	if err := writeObject(r1csPath, cs); err != nil {
		return manifestEntry{}, err
	}
	if err := writeObject(pkPath, pk); err != nil {
		return manifestEntry{}, err
	}
	if err := writeObject(vkPath, vk); err != nil {
		return manifestEntry{}, err
	}

	var verifier bytes.Buffer
	if err := vk.ExportSolidity(&verifier); err != nil {
		return manifestEntry{}, fmt.Errorf("export Solidity verifier: %w", err)
	}
	source := strings.Replace(verifier.String(), "contract Verifier", "contract "+spec.ContractName, 1)
	verifierPath := filepath.Join(contractsDir, spec.ContractName+".sol")
	if err := os.WriteFile(verifierPath, []byte(source), 0o644); err != nil {
		return manifestEntry{}, fmt.Errorf("write verifier: %w", err)
	}

	return manifestEntry{
		Name:         spec.Name,
		Constraints:  cs.GetNbConstraints(),
		PublicInputs: spec.PublicInputs,
		R1CSSHA256:   fileHash(r1csPath),
		PKSHA256:     fileHash(pkPath),
		VKSHA256:     fileHash(vkPath),
		VerifierFile: verifierPath,
	}, nil
}

func writeObject(path string, writer io.WriterTo) error {
	file, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create %s: %w", path, err)
	}
	defer file.Close()
	if _, err := writer.WriteTo(file); err != nil {
		return fmt.Errorf("write %s: %w", path, err)
	}
	return nil
}

func fileHash(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		fatal(err)
	}
	digest := sha256.Sum256(data)
	return hex.EncodeToString(digest[:])
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
