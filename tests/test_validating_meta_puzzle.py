from unittest import TestCase

from clvm.EvalError import EvalError

from hsms.atoms import bytes32
from hsms.bls12_381.BLSSecretExponent import BLSSecretExponent
from hsms.puzzles.load_clvm import load_clvm

from hsms.puzzles.p2_delegated_puzzle_or_hidden_puzzle import (
    solution_for_conditions,
    MOD as P2DPOHP_MOD,
)
from hsms.streamables import Program

from clvm_contracts import composite_amount_validation, validating_meta_puzzle

ALLOW_EVERYTHING_MOD = load_clvm(
    "allow_everything.cl", package_or_requirement="clvm_contracts"
)


def create_inner_puzzle_layer():
    secret_exponent = BLSSecretExponent.from_int(1)
    public_key = secret_exponent.public_key()
    inner_layer = (P2DPOHP_MOD, [bytes(public_key)])
    return inner_layer


class Tests(TestCase):
    def test_just_inner(self):
        inner_layer = create_inner_puzzle_layer()
        all_layers = [inner_layer]
        contract = validating_meta_puzzle.puzzle_for_layers(all_layers)
        b32 = bytes32([0] * 32)
        inner_solution = solution_for_conditions([[51, b32, 1000]])
        solution = validating_meta_puzzle.create_solution([inner_solution])
        output = contract.run(solution)

    def test_just_composite_layer(self):
        composite_layer = composite_amount_validation.layer_puzzle()
        composite_puzzle = composite_layer.at("f")
        b32 = bytes32([0] * 32)
        conditions = Program.to([[51, b32, 1000], [51, b32, 1001], [1, "junk", 1001]])

        # success case
        composite_solution = composite_amount_validation.solution_for_layer(0, 20, 50)
        args = Program.to((conditions, composite_solution))
        r = composite_puzzle.run(args)
        assert r.as_int() == 1

        # failed due to non-proof (one factor is 1)
        composite_solution = composite_amount_validation.solution_for_layer(0, 1, 1000)
        args = Program.to((conditions, composite_solution))
        r = composite_puzzle.run(args)
        assert r.as_int() == 0

        # failed due to bad proof
        composite_solution = composite_amount_validation.solution_for_layer(0, 21, 50)
        args = Program.to((conditions, composite_solution))
        r = composite_puzzle.run(args)
        assert r.as_int() == 0

        # success for 1001
        composite_solution = composite_amount_validation.solution_for_layer(1, 11, 91)
        args = Program.to((conditions, composite_solution))
        r = composite_puzzle.run(args)
        assert r.as_int() == 1

        # failed due to indexed condition not `CREATE_COIN`
        composite_solution = composite_amount_validation.solution_for_layer(2, 11, 91)
        args = Program.to((conditions, composite_solution))
        self.assertRaises(EvalError, lambda: composite_puzzle.run(args))

    def test_allow_everything_and_inner_layers(self):
        inner_layer = create_inner_puzzle_layer()
        composite_layer = composite_amount_validation.layer_puzzle()
        all_layers = [(ALLOW_EVERYTHING_MOD, 0), inner_layer]
        contract = validating_meta_puzzle.puzzle_for_layers(all_layers)
        b32 = bytes32([0] * 32)
        inner_solution = solution_for_conditions([[51, b32, 1000]])
        allow_everything_solution = ["obj0", "obj1", "obj2"]
        solution = validating_meta_puzzle.create_solution(
            [allow_everything_solution, inner_solution]
        )
        output = contract.run(solution)

    def test_composite_and_inner_layers(self):
        inner_layer = create_inner_puzzle_layer()
        composite_layer = composite_amount_validation.layer_puzzle()
        all_layers = [composite_layer, inner_layer]
        contract = validating_meta_puzzle.puzzle_for_layers(all_layers)
        b32 = bytes32([0] * 32)
        inner_solution = solution_for_conditions([[51, b32, 1000]])
        composite_solution = composite_amount_validation.solution_for_layer(1, 20, 50)
        solution = validating_meta_puzzle.create_solution(
            [composite_solution, inner_solution]
        )
        output = contract.run(solution)
