package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/1376524890/ddtm-qas/zk/circuits"
	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
)

func main() {
	name := flag.String("circuit", "utility", "utility|audit")
	out := flag.String("out", "artifacts", "output directory")
	unsafeDev := flag.Bool("unsafe-development-setup", false, "required acknowledgement")
	flag.Parse()
	if !*unsafeDev {
		panic("refusing single-party setup without --unsafe-development-setup")
	}
	var circuit frontend.Circuit
	switch *name {
	case "utility":
		circuit = &circuits.UtilityThresholdCircuit{}
	case "audit":
		circuit = &circuits.AuditBatchCircuit{}
	default:
		panic("unknown circuit")
	}
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, circuit)
	must(err)
	pk, vk, err := groth16.Setup(ccs)
	must(err)
	must(os.MkdirAll(*out, 0o755))
	write(filepath.Join(*out, *name+".r1cs"), ccs)
	write(filepath.Join(*out, *name+".pk"), pk)
	write(filepath.Join(*out, *name+".vk"), vk)
	sol, err := os.Create(filepath.Join(*out, *name+"Verifier.sol"))
	must(err)
	defer sol.Close()
	must(vk.ExportSolidity(sol))
	fmt.Printf("circuit=%s constraints=%d WARNING=UNSAFE_DEVELOPMENT_SETUP\n", *name, ccs.GetNbConstraints())
}

func write(path string, object interface {
	WriteTo(w io.Writer) (int64, error)
}) {
	f, err := os.Create(path)
	must(err)
	defer f.Close()
	_, err = object.WriteTo(f)
	must(err)
}
func must(err error) {
	if err != nil {
		panic(err)
	}
}
