try:
    from .amulet_cy_nbt import (
        TAG_Byte,
        TAG_Short,
        TAG_Int,
        TAG_Long,
        TAG_Float,
        TAG_Double,
        TAG_Byte_Array,
        TAG_String,
        TAG_List,
        TAG_Compound,
        TAG_Int_Array,
        TAG_Long_Array,
        NBTFile,
        load,
        from_snbt,
        BaseValueType,
        BaseArrayType,
        AnyNBT,
        SNBTType,
    )
except (ImportError, ModuleNotFoundError) as e:
    print(
        "导入cython nbt库失败。回退到python版本。这将运行得慢得多。"
    )
    from .amulet_nbt_py import (
        TAG_Byte,
        TAG_Short,
        TAG_Int,
        TAG_Long,
        TAG_Float,
        TAG_Double,
        TAG_Byte_Array,
        TAG_String,
        TAG_List,
        TAG_Compound,
        TAG_Int_Array,
        TAG_Long_Array,
        NBTFile,
        load,
        from_snbt,
        BaseValueType,
        BaseArrayType,
        AnyNBT,
        SNBTType,
    )

from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions
