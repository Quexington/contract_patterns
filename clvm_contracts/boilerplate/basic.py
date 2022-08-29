from chia.types.blockchain_format.program import Program

from clvm_contracts.load_clvm import load_clvm
from clvm_contracts.validating_meta_puzzle import AssetType, TypeChange

LAUNCHER = load_clvm(
    "launcher.clsp", package_or_requirement="clvm_contracts.boilerplate"
)
ENVIRONMENT = Program.to(None)
PRE_VALIDATOR = load_clvm(
    "pre_validator.clsp", package_or_requirement="clvm_contracts.boilerplate"
)
VALIDATOR = load_clvm(
    "validator.clsp", package_or_requirement="clvm_contracts.boilerplate"
)
REMOVER = load_clvm(
    "remover.clsp", package_or_requirement="clvm_contracts.boilerplate"
)

class BasicType:
    @staticmethod
    def new() -> AssetType:
        return AssetType(
            LAUNCHER.get_tree_hash(),
            ENVIRONMENT,
            PRE_VALIDATOR,
            VALIDATOR,
            REMOVER.get_tree_hash(),
        )

    @staticmethod
    def launch(typ: AssetType, **kwargs) -> TypeChange:
        return TypeChange(
            typ,
            LAUNCHER,
            Program.to((typ.as_program().rest(), kwargs["conditions"])),
        )

    @staticmethod
    def remove(typ: AssetType, **kwargs) -> TypeChange:
        return TypeChange(
            typ,
            REMOVER,
            kwargs["conditions"],
        )
