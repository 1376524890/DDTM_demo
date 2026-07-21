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

type AuditWitness struct {
	TID              string                         `json:"tid"`
	DataRoot         string                         `json:"data_root"`
	SchemaHash       string                         `json:"schema_hash"`
	DatasetVersion   string                         `json:"dataset_version"`
	RowCount         string                         `json:"row_count"`
	AuditCommitment  string                         `json:"audit_commitment"`
	PolicyHash       string                         `json:"policy_hash"`
	SamplingSeed     string                         `json:"sampling_seed"`
	BatchNumber      string                         `json:"batch_number"`
	PreviousN        string                         `json:"previous_n"`
	PreviousFailures string                         `json:"previous_failures"`
	NewN             string                         `json:"new_n"`
	NewFailures      string                         `json:"new_failures"`
	// Private
	WeightEnc          []string                    `json:"weight_enc"`
	BiasRaw            string                      `json:"bias_raw"`
	CenterEnc          []string                    `json:"center_enc"`
	InvScaleSq         []string                    `json:"inv_scale_sq"`
	MarginThresholdEnc string                      `json:"margin_threshold_enc"`
	DistanceThreshold  string                      `json:"distance_threshold"`
	MissingThreshold   string                      `json:"missing_threshold"`
	AuditBlind         string                      `json:"audit_blind"`
	Rows               []AuditRowJSON              `json:"rows"`
}

type AuditRowJSON struct {
	Index          string   `json:"index"`
	Valid          string   `json:"valid"`
	LabelBit       string   `json:"label_bit"`
	Timestamp      string   `json:"timestamp"`
	MaskBits       []string `json:"mask_bits"`
	FeaturesEnc    []string `json:"features_enc"`
	PackedFeatures []string `json:"packed_features"`
	MaskLo         string   `json:"mask_lo"`
	MaskHi         string   `json:"mask_hi"`
	Siblings       []string `json:"siblings"`
}

func parseBig(s string) *big.Int {
	n := new(big.Int)
	if _, ok := n.SetString(s, 10); !ok {
		panic(fmt.Sprintf("invalid big int: %s", s))
	}
	return n
}

func parseBigSlice(ss []string) []frontend.Variable {
	out := make([]frontend.Variable, len(ss))
	for i, s := range ss {
		out[i] = parseBig(s)
	}
	return out
}

func toFrontendSlice(ss []string, n int) [17]frontend.Variable {
	var out [17]frontend.Variable
	for i := 0; i < n; i++ {
		out[i] = parseBig(ss[i])
	}
	return out
}

func main() {
	pkFile := flag.String("pk", "artifacts/audit.pk", "proving key")
	witnessFile := flag.String("witness", "", "witness JSON")
	proofFile := flag.String("proof", "audit.proof", "output proof")
	flag.Parse()
	if *witnessFile == "" {
		flag.Usage()
		os.Exit(2)
	}

	data, err := os.ReadFile(*witnessFile)
	must(err)
	var w AuditWitness
	must(json.Unmarshal(data, &w))

	assignment := &circuits.AuditBatchCircuit{
		TID:              parseBig(w.TID),
		DataRoot:         parseBig(w.DataRoot),
		SchemaHash:       parseBig(w.SchemaHash),
		DatasetVersion:   parseBig(w.DatasetVersion),
		RowCount:         parseBig(w.RowCount),
		AuditCommitment:  parseBig(w.AuditCommitment),
		PolicyHash:       parseBig(w.PolicyHash),
		SamplingSeed:     parseBig(w.SamplingSeed),
		BatchNumber:      parseBig(w.BatchNumber),
		PreviousN:        parseBig(w.PreviousN),
		PreviousFailures: parseBig(w.PreviousFailures),
		NewN:             parseBig(w.NewN),
		NewFailures:      parseBig(w.NewFailures),
		BiasRaw:          parseBig(w.BiasRaw),
		MarginThresholdEnc: parseBig(w.MarginThresholdEnc),
		DistanceThreshold:  parseBig(w.DistanceThreshold),
		MissingThreshold:   parseBig(w.MissingThreshold),
		AuditBlind:       parseBig(w.AuditBlind),
	}
	// Copy arrays
	copy(assignment.WeightEnc[:], parseBigSlice(w.WeightEnc))
	copy(assignment.CenterEnc[:], parseBigSlice(w.CenterEnc))
	copy(assignment.InvScaleSq[:], parseBigSlice(w.InvScaleSq))

	for i := 0; i < circuits.AuditBatchSize && i < len(w.Rows); i++ {
		r := w.Rows[i]
		assignment.Rows[i] = circuits.AuditRowWitness{
			Index:          parseBig(r.Index),
			Valid:          parseBig(r.Valid),
			LabelBit:       parseBig(r.LabelBit),
			Timestamp:      parseBig(r.Timestamp),
			MaskLo:         parseBig(r.MaskLo),
			MaskHi:         parseBig(r.MaskHi),
		}
		copy(assignment.Rows[i].MaskBits[:], parseBigSlice(r.MaskBits))
		copy(assignment.Rows[i].FeaturesEnc[:], parseBigSlice(r.FeaturesEnc))
		copy(assignment.Rows[i].PackedFeatures[:], parseBigSlice(r.PackedFeatures))
		copy(assignment.Rows[i].Siblings[:], parseBigSlice(r.Siblings))
	}

	pkFd, err := os.Open(*pkFile)
	must(err)
	defer pkFd.Close()
	pk := groth16.NewProvingKey(ecc.BN254)
	_, err = pk.UnsafeReadFrom(pkFd)
	must(err)

	witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
	must(err)
	proof, err := groth16.Prove(nil, pk, witness)
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
