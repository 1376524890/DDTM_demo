package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"math/big"
	"os"
	"path/filepath"

	"github.com/1376524890/ddtm-qas/zk/circuits"
	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
)

type UtilityWitness struct {
	TID               string `json:"tid"`
	DataRoot          string `json:"data_root"`
	ModelCommitment   string `json:"model_commitment"`
	ValidationRoot    string `json:"validation_root"`
	MetricsCommitment string `json:"metrics_commitment"`
	PolicyHash        string `json:"policy_hash"`
	SessionHash       string `json:"session_hash"`
	MinUtilityEnc     string `json:"min_utility_enc"`
	MaxLinearError    string `json:"max_linear_error"`
	MaxShift          string `json:"max_shift"`
	LambdaMAD         string `json:"lambda_mad"`
	LambdaShift       string `json:"lambda_shift"`
	LambdaLinear      string `json:"lambda_linear"`
	// Private
	UMomEnc      string `json:"umom_enc"`
	MAD          string `json:"mad"`
	Shift        string `json:"shift"`
	LinearError  string `json:"linear_error"`
	UCertEnc     string `json:"ucert_enc"`
	MetricsBlind string `json:"metrics_blind"`
}

func parseBig(s string) *big.Int {
	n := new(big.Int)
	if _, ok := n.SetString(s, 10); !ok {
		panic(fmt.Sprintf("invalid big int: %s", s))
	}
	return n
}

func main() {
	pkFile := flag.String("pk", "artifacts/utility.pk", "proving key")
	witnessFile := flag.String("witness", "", "witness JSON")
	proofFile := flag.String("proof", "utility.proof", "output proof")
	flag.Parse()
	if *witnessFile == "" {
		flag.Usage()
		os.Exit(2)
	}

	data, err := os.ReadFile(*witnessFile)
	must(err)
	var w UtilityWitness
	must(json.Unmarshal(data, &w))

	assignment := &circuits.UtilityThresholdCircuit{
		TID:               parseBig(w.TID),
		DataRoot:          parseBig(w.DataRoot),
		ModelCommitment:   parseBig(w.ModelCommitment),
		ValidationRoot:    parseBig(w.ValidationRoot),
		MetricsCommitment: parseBig(w.MetricsCommitment),
		PolicyHash:        parseBig(w.PolicyHash),
		SessionHash:       parseBig(w.SessionHash),
		MinUtilityEnc:     parseBig(w.MinUtilityEnc),
		MaxLinearError:    parseBig(w.MaxLinearError),
		MaxShift:          parseBig(w.MaxShift),
		LambdaMAD:         parseBig(w.LambdaMAD),
		LambdaShift:       parseBig(w.LambdaShift),
		LambdaLinear:      parseBig(w.LambdaLinear),
		UMomEnc:           parseBig(w.UMomEnc),
		MAD:               parseBig(w.MAD),
		Shift:             parseBig(w.Shift),
		LinearError:       parseBig(w.LinearError),
		UCertEnc:          parseBig(w.UCertEnc),
		MetricsBlind:      parseBig(w.MetricsBlind),
	}

	pkFd, err := os.Open(*pkFile)
	must(err)
	defer pkFd.Close()
	pk := groth16.NewProvingKey(ecc.BN254)
	_, err = pk.UnsafeReadFrom(pkFd)
	must(err)

	witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
	must(err)
	proof, err := groth16.Prove(nil, pk, witness) // nil ccs uses embedded constraint system
	must(err)

	must(os.MkdirAll(filepath.Dir(*proofFile), 0o755))
	f, err := os.Create(*proofFile)
	must(err)
	defer f.Close()
	_, err = proof.WriteTo(f)
	must(err)
	fmt.Printf("proof written to %s\n", *proofFile)
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
