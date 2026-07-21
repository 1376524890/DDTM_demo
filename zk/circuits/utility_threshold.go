package circuits

import "github.com/consensys/gnark/frontend"

// UtilityThresholdCircuit proves that committed private metrics satisfy the
// public ARUC policy. Signed utility values use offset encoding v + 2^62.
type UtilityThresholdCircuit struct {
	// Private metrics.
	UMomEnc      frontend.Variable
	MAD          frontend.Variable
	Shift        frontend.Variable
	LinearError  frontend.Variable
	UCertEnc     frontend.Variable
	MetricsBlind frontend.Variable

	// Public transaction and policy binding.
	TID               frontend.Variable `gnark:",public"`
	DataRoot          frontend.Variable `gnark:",public"`
	ModelCommitment   frontend.Variable `gnark:",public"`
	ValidationRoot    frontend.Variable `gnark:",public"`
	MetricsCommitment frontend.Variable `gnark:",public"`
	PolicyHash        frontend.Variable `gnark:",public"`
	SessionHash       frontend.Variable `gnark:",public"`
	MinUtilityEnc     frontend.Variable `gnark:",public"`
	MaxLinearError    frontend.Variable `gnark:",public"`
	MaxShift          frontend.Variable `gnark:",public"`
	LambdaMAD         frontend.Variable `gnark:",public"`
	LambdaShift       frontend.Variable `gnark:",public"`
	LambdaLinear      frontend.Variable `gnark:",public"`
}

func (c *UtilityThresholdCircuit) Define(api frontend.API) error {
	commitment, err := Hash(api,
		TagMetrics, c.TID, c.DataRoot, c.ModelCommitment, c.ValidationRoot,
		c.PolicyHash, c.SessionHash, c.UMomEnc, c.MAD, c.Shift,
		c.LinearError, c.UCertEnc, c.MetricsBlind,
	)
	if err != nil {
		return err
	}
	api.AssertIsEqual(commitment, c.MetricsCommitment)

	penalty := api.Add(
		api.Mul(c.LambdaMAD, c.MAD),
		api.Mul(c.LambdaShift, c.Shift),
		api.Mul(c.LambdaLinear, c.LinearError),
	)
	api.AssertIsEqual(c.UCertEnc, api.Sub(c.UMomEnc, penalty))

	// All metrics and policy constants are explicitly range constrained.
	AssertBits(api, c.UMomEnc, 64)
	AssertBits(api, c.UCertEnc, 64)
	AssertBits(api, c.MAD, 48)
	AssertBits(api, c.Shift, 48)
	AssertBits(api, c.LinearError, 48)
	AssertBits(api, c.MinUtilityEnc, 64)
	AssertBits(api, c.MaxLinearError, 48)
	AssertBits(api, c.MaxShift, 48)
	AssertBits(api, c.LambdaMAD, 24)
	AssertBits(api, c.LambdaShift, 24)
	AssertBits(api, c.LambdaLinear, 24)

	api.AssertIsLessOrEqual(c.MinUtilityEnc, c.UCertEnc)
	api.AssertIsLessOrEqual(c.LinearError, c.MaxLinearError)
	api.AssertIsLessOrEqual(c.Shift, c.MaxShift)
	return nil
}
