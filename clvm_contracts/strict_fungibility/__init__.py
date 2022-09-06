from typing import Callable, List

from chia.types.blockchain_format.coin import Coin, coin_as_list
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.blockchain_format.program import Program

from clvm_contracts.load_clvm import load_clvm
from clvm_contracts.validating_meta_puzzle import AssetType, TypeChange, VMPSpend, VMP_MOD_HASH

PRE_VALIDATOR = load_clvm(
    "pre_validator.clsp", package_or_requirement="clvm_contracts.strict_fungibility"
)
CAT_VALIDATOR = load_clvm(
    "cat_validator.clsp",
    package_or_requirement="clvm_contracts.strict_fungibility",
)
NFT_VALIDATOR = load_clvm(
    "nft_validator.clsp",
    package_or_requirement="clvm_contracts.strict_fungibility",
)
CAT_PRE_VALIDATOR = PRE_VALIDATOR.curry(CAT_VALIDATOR.get_tree_hash())
NFT_PRE_VALIDATOR = PRE_VALIDATOR.curry(NFT_VALIDATOR.get_tree_hash())
SINGLETON_LAUNCHER = load_clvm(
    "singleton_launcher.clsp",
    package_or_requirement="clvm_contracts.strict_fungibility",
)
P2_SINGLETON = load_clvm(
    "p2_singleton.clsp",
    package_or_requirement="clvm_contracts.strict_fungibility",
)


def previous_index(i: int, length: int) -> int:
    return i - 1


def next_index(i: int, length: int) -> int:
    if i == length - 1:
        return 0
    else:
        return i + 1


def get_unique_fungible_types(spend: VMPSpend, pre_validator: Program, validator: Program) -> List[AssetType]:
    fungible_types: List[AssetType] = []
    launchers: List[bytes32] = []
    for typ in spend.types:
        if (
            typ.pre_validator == pre_validator
            and typ.validator == validator
            and typ.launcher_hash not in launchers
        ):
            fungible_types.append(typ)
            launchers.append(typ.launcher_hash)
    return fungible_types

def solve_fungible_type(
    spends: List[VMPSpend],
    subtotal_func: Callable[[Program], int],
    pre_validator: Program,
    validator: Program,
) -> List[VMPSpend]:
    subtotal_dict: Dict[bytes32, int] = {}
    morphed_vmps: List[VMPSpend] = []
    for i, spend in enumerate(spends):
        for typ in get_unique_fungible_types(spend, pre_validator, validator):
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
                    subtotal_dict[typ.launcher_hash] += subtotal_func(condition)

            spend.unsafe_solutions[spend.index_of(typ)] = Program.to(
                [
                    previous_spend.coin.name(),
                    coin_as_list(spend.coin),
                    coin_as_list(next_spend.coin),
                    prev_subtotal,
                    subtotal_dict[typ.launcher_hash],
                ]
            )
            spend.type_proofs.append(next_spend.puzzle.get_type_proof([]))

    return spends


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
        return solve_fungible_type(
            spends,
            lambda c: c.at("rrf").as_int(),
            CAT_PRE_VALIDATOR,
            CAT_VALIDATOR,
        )


class NFTType:
    @staticmethod
    def new(
        launcher_hash: bytes32,
        remover_hash: bytes32,
        enivronment: Program,
    ) -> AssetType:
        return AssetType(
            launcher_hash,
            enivronment,
            NFT_PRE_VALIDATOR,
            NFT_VALIDATOR,
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
        return solve_fungible_type(
            spends,
            lambda c: 1,
            NFT_PRE_VALIDATOR,
            NFT_VALIDATOR,
        )


class SingletonType:
    @staticmethod
    def new(
        coin_id: bytes32,
        remover_hash: bytes32,
        enivronment: Program,
    ) -> AssetType:
        return AssetType(
            SINGLETON_LAUNCHER.curry(coin_id).get_tree_hash(),
            enivronment,
            NFT_PRE_VALIDATOR,
            NFT_VALIDATOR,
            remover_hash,
        )

    @staticmethod
    def launch(typ: AssetType, **kwargs) -> TypeChange:
        return TypeChange(
            typ,
            SINGLETON_LAUNCHER.curry(kwargs["coin_id"]),
            Program.to([typ.as_program().rest(), kwargs["conditions"]]),
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
        return solve_fungible_type(
            spends,
            lambda c: 1,
            NFT_PRE_VALIDATOR,
            NFT_VALIDATOR,
        )

    @staticmethod
    def p2(**kwargs) -> Program:
        return P2_SINGLETON.curry(
            VMP_MOD_HASH,
            NFT_PRE_VALIDATOR.get_tree_hash(),
            kwargs["launcher_hash"],
        )

    @staticmethod
    def solve_p2(**kwargs) -> Program:
        return Program.to(
            [
                [
                    kwargs["vmp_spend"].coin.parent_coin_info,
                    kwargs["vmp_spend"].puzzle.get_types_hash(),
                    kwargs["vmp_spend"].puzzle.inner_puzzle.get_tree_hash(),
                    kwargs["vmp_spend"].coin.amount,
                ],
                kwargs["coin"].name(),
                kwargs["puzzle"],
                kwargs["solution"],
            ]
        )