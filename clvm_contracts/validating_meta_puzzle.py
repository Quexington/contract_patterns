import dataclasses
import hashlib

from typing import List, Optional, Tuple

from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.program import Program
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.coin_spend import CoinSpend
from chia.util.ints import uint64

from clvm_contracts.load_clvm import load_clvm


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
                self.pre_validator.get_tree_hash(),
                self.validator.get_tree_hash(),
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
class TypeProof:
    puzzle_hash: bytes32
    inner_hash: bytes32
    type_hashes: List[bytes32]

    def as_program(self) -> Program:
        return Program.to([self.puzzle_hash, self.inner_hash, self.type_hashes])


@dataclasses.dataclass(frozen=True)
class TypeChange:
    type: AssetType
    puzzle: Program
    solution: Program

    def as_program(self) -> Program:
        return Program.to((self.puzzle, self.solution))


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

    def get_type_proof(self, types_to_prove: List[AssetType]) -> TypeProof:
        type_list = self.types
        trailing_hash = None
        while len(type_list) > 0 and type_list[-1] not in types_to_prove:
            if trailing_hash is None:
                trailing_hash = Program.to(None).get_tree_hash()
            trailing_hash = sha256(
                bytes([2]), type_list[-1].get_tree_hash(), trailing_hash
            )
            type_list = type_list[:-1]
        proof = Program.to(trailing_hash)
        while len(type_list) > 0:
            proof = Program.to(type_list[-1].get_tree_hash()).cons(proof)
            type_list = type_list[:-1]
        return TypeProof(self.get_tree_hash(), self.inner_puzzle.get_tree_hash(), proof)


class VMPSpend:
    def __init__(
        self,
        coin: Coin,
        puzzle: VMP,
        inner_solution: Program = Program.to(None),
        lineage_proof: Optional[LineageProof] = None,
        type_proofs: List[TypeProof] = [],
        unsafe_solutions: Optional[List[Program]] = None,
        type_additions: List[TypeChange] = [],
        type_removals: Optional[List[TypeChange]] = None,
        secure_solutions: Optional[List[Program]] = None,
    ) -> None:
        self.coin = coin
        self.puzzle = puzzle
        self.inner_solution = inner_solution
        self.lineage_proof = lineage_proof
        self.type_proofs = type_proofs
        self.unsafe_solutions = unsafe_solutions
        self.type_additions = type_additions
        self.type_removals = type_removals
        self.secure_solutions = secure_solutions

    def name(self) -> None:
        return self.coin.name()

    def _types_after_additions(self) -> List[AssetType]:
        new_types: List[AssetType] = [add.type for add in self.type_additions]
        new_types.reverse()  # simulates recursive prepending
        return [*new_types, *self.puzzle.types]

    def _align_type_removals(self) -> List[Program]:
        removable_type_hashes: List[bytes32] = [
            typ.get_tree_hash() for typ in self._types_after_additions()
        ]
        type_removals_dict: Dict[bytes32, TypeChange] = {}
        if self.type_removals is not None:
            type_removals_dict = {
                rem.type.get_tree_hash(): rem for rem in self.type_removals
            }
        type_removals_solution: List[Program] = []
        for type_hash in removable_type_hashes:
            if type_hash in type_removals_dict:
                type_removals_solution.append(
                    type_removals_dict[type_hash].as_program()
                )
            else:
                type_removals_solution.append(Program.to(None))

        return type_removals_solution

    @property
    def types(self) -> List[AssetType]:
        all_types: List[AssetType] = self._types_after_additions()
        removed_types: List[AssetType] = (
            []
            if self.type_removals is None
            else [rem.type for rem in self.type_removals]
        )
        return [typ for typ in all_types if typ not in removed_types]

    def __len__(self) -> int:
        return len(self.types)

    def _secured_information(self) -> Program:
        return Program.to(
            [
                [add.as_program() for add in self.type_additions],
                self._align_type_removals(),
                [None] * len(self)
                if self.secure_solutions is None
                else self.secure_solutions,
            ]
        )

    def security_hash(self) -> bytes32:
        return self._secured_information().get_tree_hash()

    def to_coin_spend(self) -> CoinSpend:
        solution = Program.to(
            [
                self.inner_solution,
                None if self.lineage_proof is None else self.lineage_proof.as_program(),
                [proof.as_program() for proof in self.type_proofs],
                [typ.pre_validator for typ in self.types],
                [typ.validator for typ in self.types],
                [None] * len(self)
                if self.unsafe_solutions is None
                else self.unsafe_solutions,
                self._secured_information(),
            ]
        )
        return CoinSpend(self.coin, self.puzzle.construct(), solution)
