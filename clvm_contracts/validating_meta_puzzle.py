import dataclasses

from typing import List, Optional, Tuple

from chia.types.blockchain_format.program import Program
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.util.ints import uint64
from chia.wallet.puzzles.load_clvm import load_clvm


VMP_MOD = load_clvm(
    "validating_meta_puzzle.clsp", package_or_requirement="clvm_contracts"
)


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

    def solve(
        self,
        inner_solution: Program,
        lineage_proof: Optional[LineageProof],
        unsafe_solutions: List[Program],
        secured_information: SecuredInformation,
    ) -> Program:
        return Program.to(
            [
                inner_solution,
                None if lineage_proof is None else lineage_proof.as_program(),
                unsafe_solutions,
                secured_information.as_program(),
            ]
        )
