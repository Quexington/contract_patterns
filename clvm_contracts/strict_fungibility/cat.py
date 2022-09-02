from typing import List

from chia.types.blockchain_format.coin import Coin, coin_as_list
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.blockchain_format.program import Program

from clvm_contracts.load_clvm import load_clvm
from clvm_contracts.validating_meta_puzzle import AssetType, TypeChange, VMPSpend, get_type_proof

PRE_VALIDATOR = load_clvm(
    "pre_validator.clsp", package_or_requirement="clvm_contracts.strict_fungibility"
)
CAT_VALIDATOR = load_clvm(
    "cat_validator.clsp",
    package_or_requirement="clvm_contracts.strict_fungibility",
)
CAT_PRE_VALIDATOR = PRE_VALIDATOR.curry(CAT_VALIDATOR.get_tree_hash())


def previous_index(i: int, length: int) -> int:
    return i - 1


def next_index(i: int, length: int) -> int:
    if i == length - 1:
        return 0
    else:
        return i + 1


def get_unique_cat_types(spend: VMPSpend) -> List[AssetType]:
    cat_types: List[AssetType] = []
    launchers: List[bytes32] = []
    for typ in spend.types:
        if (
            typ.pre_validator == CAT_PRE_VALIDATOR
            and typ.validator == CAT_VALIDATOR
            and typ.launcher_hash not in launchers
        ):
            cat_types.append(typ)
            launchers.append(typ.launcher_hash)
    return cat_types


class CATType:
    @staticmethod
    def new(
        launcher_hash: bytes32, remover_hash: bytes32, enivronment: Program
    ) -> AssetType:
        return AssetType(
            launcher_hash,
            enivronment,
            CAT_PRE_VALIDATOR,
            CAT_VALIDATOR,
            remover_hash,
        )

    @staticmethod
    def launch(typ: AssetType, **kwargs) -> TypeChange:
        return TypeChange(
            typ,
            kwargs["launcher"],
            kwargs["launcher_solution"],
        )

    @staticmethod
    def remove(typ: AssetType, **kwargs) -> TypeChange:
        return TypeChange(
            typ,
            kwargs["remover"],
            kwargs["remover_solution"],
        )

    @staticmethod
    def solve(spends: List[VMPSpend]) -> List[VMPSpend]:
        subtotal_dict: Dict[bytes32, int] = {}
        morphed_vmps: List[VMPSpend] = []
        for i, spend in enumerate(spends):
            for typ in get_unique_cat_types(spend):
                prev_sibling_index = previous_index(i, len(spends))
                previous_spend = spends[prev_sibling_index]
                while not previous_spend.is_type(
                    typ, ignores=["environment", "remover_hash"]
                ):
                    prev_sibling_index = previous_index(prev_sibling_index, len(spends))
                    previous_spend = spends[prev_sibling_index]
                next_sibling_index = next_index(i, len(spends))
                next_spend = spends[next_sibling_index]
                while not next_spend.is_type(
                    typ, ignores=["environment", "remover_hash"]
                ):
                    next_sibling_index = next_index(next_sibling_index, len(spends))
                    next_spend = spends[next_sibling_index]

                subtotal_dict.setdefault(typ.launcher_hash, 0)
                prev_subtotal = subtotal_dict[typ.launcher_hash]

                conditions: Program = spend.puzzle.inner_puzzle.run(
                    spend.inner_solution
                )
                for condition in conditions.as_iter():
                    if condition.first() == Program.to(51):
                        subtotal_dict[typ.launcher_hash] += condition.at("rrf").as_int()

                spend.unsafe_solutions[spend.index_of(typ)] = Program.to(
                    [
                        previous_spend.coin.name(),
                        coin_as_list(spend.coin),
                        next_spend.coin.name(),
                        prev_subtotal,
                        subtotal_dict[typ.launcher_hash],
                    ]
                )

        return spends
