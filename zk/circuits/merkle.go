package circuits

import "github.com/consensys/gnark/frontend"

func RowLeaf(
	api frontend.API,
	schemaHash, datasetVersion, rowID, valid, labelCode, timestamp,
	maskLo, maskHi frontend.Variable,
	packedFeatures [19]frontend.Variable,
) (frontend.Variable, error) {
	values := []frontend.Variable{TagRow, schemaHash, datasetVersion, rowID, valid, labelCode, timestamp, maskLo, maskHi}
	values = append(values, packedFeatures[:]...)
	return Hash(api, values...)
}

func VerifyMerklePath(api frontend.API, leaf, root, index frontend.Variable, siblings [MerkleDepth]frontend.Variable) error {
	bits := api.ToBinary(index, MerkleDepth)
	current := leaf
	for level := 0; level < MerkleDepth; level++ {
		left := api.Select(bits[level], siblings[level], current)
		right := api.Select(bits[level], current, siblings[level])
		next, err := Hash(api, TagNode, level, left, right)
		if err != nil {
			return err
		}
		current = next
	}
	api.AssertIsEqual(current, root)
	return nil
}
