import dataclasses
import hashlib

from typing import List, Optional, Tuple

from chia.types.blockchain_format.program import Program
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.util.ints import uint64
from chia.wallet.puzzles.load_clvm import load_clvm


VMP_MOD = load_clvm(
    "validating_meta_puzzle.clsp", package_or_requirement="clvm_contracts"
)
NAMESPACE_PREFIX = b"namespaces"


def sha256(*args: bytes) -> bytes32:
    return bytes32(hashlib.sha256(b"".join(args)).digest())


@dataclasses.dataclass(frozen=True)
class AssetType:
    launcher_hash: bytes32
    environment: Program
    pre_validator: Program
    validator: Program
    remover_hash: bytes32

    def as_program(self) -> Program:
        return Program.to(
            [
                self.launcher_hash,
                self.environment,
                self.pre_validator,
                self.validator,
                self.remover_hash,
            ]
        )

    def get_tree_hash(self) -> bytes32:
        return self.as_program().get_tree_hash()


@dataclasses.dataclass(frozen=True)
class LineageProof:
    parent_id: bytes32
    types_hash: bytes32
    inner_puzzle_hash: bytes32
    amount: uint64

    def as_program(self) -> Program:
        return Program.to(
            [self.parent_id, self.types_hash, self.inner_puzzle_hash, self.amount]
        )


@dataclasses.dataclass(frozen=True)
class SecuredInformation:
    type_additions: List[Tuple[Program, Program]]
    type_removals: List[Optional[Tuple[Program, Program]]]
    secure_solutions: List[Program]

    def as_program(self) -> Program:
        return Program.to(
            [self.type_additions, self.type_removals, self.secure_solutions]
        )

    def get_tree_hash(self) -> bytes32:
        return self.as_program().get_tree_hash()


@dataclasses.dataclass(frozen=True)
class VMP:
    inner_puzzle: Program
    types: List[AssetType]

    def construct(self) -> Program:
        return VMP_MOD.curry(
            VMP_MOD.get_tree_hash(),
            [t.as_program() for t in self.types],
            self.inner_puzzle,
        )

    def get_tree_hash(self) -> bytes32:
        return self.construct().get_tree_hash()

    def get_types_hash(self) -> bytes32:
        return Program.to([t.as_program() for t in self.types]).get_tree_hash()

    def get_type_proof(self, types_to_prove: List[AssetType]) -> Program:
        type_list = self.types
        trailing_hash = None
        while len(type_list) > 0 and type_list[-1] not in types_to_prove:
            if trailing_hash is None:
                trailing_hash = Program.to(None).get_tree_hash()
            trailing_hash = sha256(bytes([2]), type_list[-1].get_tree_hash(), trailing_hash)
            type_list = type_list[:-1]
        proof = Program.to(trailing_hash)
        while len(type_list) > 0:
            proof = Program.to(type_list[-1].get_tree_hash()).cons(proof)
            type_list = type_list[:-1]
        return Program.to([self.get_tree_hash(), self.inner_puzzle.get_tree_hash(), proof])

    def solve(
        self,
        inner_solution: Program,
        lineage_proof: Optional[LineageProof],
        unsafe_solutions: List[Program],
        secured_information: SecuredInformation,
        type_proofs: Optional[List[Program]] = None,
    ) -> Program:
        return Program.to(
            [
                inner_solution,
                None if lineage_proof is None else lineage_proof.as_program(),
                type_proofs,
                unsafe_solutions,
                secured_information.as_program(),
            ]
        )
