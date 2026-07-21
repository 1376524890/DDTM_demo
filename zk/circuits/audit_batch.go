package circuits

import "github.com/consensys/gnark/frontend"

type AuditRowWitness struct {
	Index          frontend.Variable
	Valid          frontend.Variable
	LabelBit       frontend.Variable // 1 => +1, 0 => -1
	Timestamp      frontend.Variable
	MaskBits       [FeatureCount]frontend.Variable
	FeaturesEnc    [FeatureCount]frontend.Variable // int32 + 2^31
	PackedFeatures [19]frontend.Variable
	MaskLo         frontend.Variable
	MaskHi         frontend.Variable
	Siblings       [MerkleDepth]frontend.Variable
}

// AuditBatchCircuit checks 64 deterministic rows. Integer score arithmetic is
// deliberately division-free: feature Q16.16 times weight Q8.8 is compared
// against thresholds calibrated in the same raw scale.
type AuditBatchCircuit struct {
	// Private audit probe.
	WeightEnc          [FeatureCount]frontend.Variable // int16 + 2^15
	BiasRaw            frontend.Variable
	CenterEnc          [FeatureCount]frontend.Variable // int32 + 2^31
	InvScaleSq         [FeatureCount]frontend.Variable // nonnegative integer coefficient
	MarginThresholdEnc frontend.Variable
	DistanceThreshold  frontend.Variable
	MissingThreshold   frontend.Variable
	AuditBlind         frontend.Variable

	Rows [AuditBatchSize]AuditRowWitness

	// Public state and commitments.
	TID              frontend.Variable `gnark:",public"`
	DataRoot         frontend.Variable `gnark:",public"`
	SchemaHash       frontend.Variable `gnark:",public"`
	DatasetVersion   frontend.Variable `gnark:",public"`
	RowCount         frontend.Variable `gnark:",public"`
	AuditCommitment  frontend.Variable `gnark:",public"`
	PolicyHash       frontend.Variable `gnark:",public"`
	SamplingSeed     frontend.Variable `gnark:",public"`
	BatchNumber      frontend.Variable `gnark:",public"`
	PreviousN        frontend.Variable `gnark:",public"`
	PreviousFailures frontend.Variable `gnark:",public"`
	NewN             frontend.Variable `gnark:",public"`
	NewFailures      frontend.Variable `gnark:",public"`
}

func (c *AuditBatchCircuit) Define(api frontend.API) error {
	probeValues := []frontend.Variable{TagAudit, c.TID, c.PolicyHash, c.BiasRaw, c.MarginThresholdEnc, c.DistanceThreshold, c.MissingThreshold}
	probeValues = append(probeValues, c.WeightEnc[:]...)
	probeValues = append(probeValues, c.CenterEnc[:]...)
	probeValues = append(probeValues, c.InvScaleSq[:]...)
	probeValues = append(probeValues, c.AuditBlind)
	commitment, err := Hash(api, probeValues...)
	if err != nil {
		return err
	}
	api.AssertIsEqual(commitment, c.AuditCommitment)

	AssertBits(api, c.RowCount, 18)
	AssertBits(api, c.PreviousN, 16)
	AssertBits(api, c.PreviousFailures, 16)
	AssertBits(api, c.MissingThreshold, 8)
	AssertBits(api, c.MarginThresholdEnc, 64)
	AssertBits(api, c.DistanceThreshold, 96)

	newN := c.PreviousN
	newFailures := c.PreviousFailures

	for i := 0; i < AuditBatchSize; i++ {
		expectedOrdinal := api.Add(api.Mul(c.BatchNumber, AuditBatchSize), i)
		expectedIndex, err := Feistel17(api, c.SamplingSeed, expectedOrdinal)
		if err != nil {
			return err
		}
		api.AssertIsEqual(c.Rows[i].Index, expectedIndex)
		api.AssertIsEqual(c.Rows[i].Valid, 1) // policy skips padding outside the proof schedule
		api.AssertIsBoolean(c.Rows[i].LabelBit)
		AssertBits(api, c.Rows[i].Index, 17)
		api.AssertIsLessOrEqual(c.Rows[i].Index, api.Sub(c.RowCount, 1))

		labelCode := api.Add(1, c.Rows[i].LabelBit) // -1=>1, +1=>2
		leaf, err := RowLeaf(api, c.SchemaHash, c.DatasetVersion, c.Rows[i].Index,
			c.Rows[i].Valid, labelCode, c.Rows[i].Timestamp,
			c.Rows[i].MaskLo, c.Rows[i].MaskHi, c.Rows[i].PackedFeatures)
		if err != nil {
			return err
		}
		if err := VerifyMerklePath(api, leaf, c.DataRoot, c.Rows[i].Index, c.Rows[i].Siblings); err != nil {
			return err
		}

		linear := c.BiasRaw
		distance := frontend.Variable(0)
		missingCount := frontend.Variable(0)
		for k := 0; k < FeatureCount; k++ {
			api.AssertIsBoolean(c.Rows[i].MaskBits[k])
			AssertBits(api, c.Rows[i].FeaturesEnc[k], 32)
			AssertBits(api, c.WeightEnc[k], 16)
			AssertBits(api, c.CenterEnc[k], 32)
			AssertBits(api, c.InvScaleSq[k], 20)

			x := api.Sub(c.Rows[i].FeaturesEnc[k], FeatureBias)
			w := api.Sub(c.WeightEnc[k], WeightBias)
			center := api.Sub(c.CenterEnc[k], FeatureBias)
			present := api.Sub(1, c.Rows[i].MaskBits[k])
			linear = api.Add(linear, api.Mul(present, w, x))
			delta := api.Sub(x, center)
			distance = api.Add(distance, api.Mul(present, delta, delta, c.InvScaleSq[k]))
			missingCount = api.Add(missingCount, c.Rows[i].MaskBits[k])
		}

		margin := SelectSignedLabel(api, c.Rows[i].LabelBit, linear)
		marginEnc := api.Add(margin, SignedMetricBias)
		lowMargin := api.Cmp(marginEnc, c.MarginThresholdEnc)  // -1 when margin<threshold
		highDistance := api.Cmp(c.DistanceThreshold, distance) // -1 when threshold<distance
		tooMissing := api.Cmp(c.MissingThreshold, missingCount)
		failed := api.Or(api.IsZero(api.Add(lowMargin, 1)), api.Or(
			api.IsZero(api.Add(highDistance, 1)),
			api.IsZero(api.Add(tooMissing, 1)),
		))
		api.AssertIsBoolean(failed)
		newN = api.Add(newN, 1)
		newFailures = api.Add(newFailures, failed)
	}

	api.AssertIsEqual(newN, c.NewN)
	api.AssertIsEqual(newFailures, c.NewFailures)
	return nil
}
