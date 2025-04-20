from abc import abstractmethod, abstractproperty
from typing import Any, Callable

from numpy import ndarray
import bmesh
from bmesh.types import BMesh
import bpy
from bpy.types import Mesh, TimelineMarkers
from .context import VCAPContext, VCAPSettings
from mathutils import Matrix, Vector
from ..amulet_nbt import TAG_Compound, TAG_List, TAG_Int_Array, TAG_Byte_Array, TAG_String
from . import util
from .. import data

LINE_CLEAR = '\x1b[2K'  # <-- ANSI序列

def load_frame(nbt: TAG_Compound, index = 0, offset = Vector()):
    t = nbt["type"].value
    if t == 0:
        return IFrame(nbt, index, offset)
    elif t == 1:
        return PFrame(nbt, index, offset)
    else: raise RuntimeError(f"未知帧类型: {t}")


class VcapFrame:
    @abstractmethod
    def get_meshes(
            self,
            vcontext: VCAPContext,
            settings: VCAPSettings,
            progress_function: Callable[[float],
                                       None] = None) -> dict[Any, Mesh]:
        """生成此帧的网格。

        返回:
            dict[Any, Mesh]: 包含网格和负责它们的覆盖ID的字典。
            'base'是没有覆盖的基础网格。
        """
        raise RuntimeError("不能在基类上调用方法")

    @abstractmethod
    def get_declared_override(self) -> set[Vector]:
        raise RuntimeError("不能在基类上调用方法")

    time: float
    overrides: dict[Any, set[Vector]]
    """块覆盖及其ID的集合。由于它们随后被替换，
    覆盖是一组需要被分解成单独网格的体素。
    """


class PFrame(VcapFrame):
    __nbt__: TAG_Compound
    index: int = 0
    vcap_offset = Vector()

    def __init__(self, nbt: TAG_Compound, index: int = 0, vcap_offset = Vector()) -> None:
        """创建一个PFrame对象。

        参数:
            nbt (TAG_Compound): 帧NBT数据。
            index (int, optional): 放入网格名称的帧号。默认为0。
        """
        self.__nbt__ = nbt
        self.index = index
        self.time = nbt['time'].value
        self.overrides = dict()
        self.vcap_offset = vcap_offset

    def get_meshes(self, vcontext: VCAPContext, settings: VCAPSettings, progress_function=None):
        blocks: TAG_List = self.__nbt__['blocks']
        palette: TAG_List = self.__nbt__['palette']

        meshes: dict[any, BMesh] = {}
        meshes['base'] = bmesh.new()
        for id in self.overrides:
            meshes[id] = bmesh.new()

        block: TAG_Compound
        for block in blocks:
            state: int = block['state'].value
            pos: TAG_List = block['pos']
            x = pos[0].value
            y = pos[1].value
            z = pos[2].value
            position: Vector = Vector((x, y, z))
            position += self.vcap_offset
            position.freeze()

            model_id: TAG_String = palette[state]
            block_mesh = vcontext.models[model_id.value]
            if len(block_mesh.vertices) == 0:
                continue

            mesh_index = 'base'
            for id, vals in self.overrides.items():
                if position in vals:
                    mesh_index = id
                    break

            if settings.use_vertex_colors and 'color' in block:
                color_tag: TAG_List = block['color']
                r = _make_unsigned(color_tag[0].value) / 255
                g = _make_unsigned(color_tag[1].value) / 255
                b = _make_unsigned(color_tag[2].value) / 255
                color = [r, g, b, 1]
            else:
                color = [1, 1, 1, 1]


            util.add_mesh(meshes[mesh_index], block_mesh, Matrix.Translation(position), color)

        final_meshes: dict[Any, Mesh] = {}
        for id in meshes:
            mesh = meshes[id]
            if len(mesh.verts) == 0: continue
            outMesh = bpy.data.meshes.new(f'{vcontext.name}.f{self.index}')
            mesh.to_mesh(outMesh)
            final_meshes[id] = outMesh

        return final_meshes

    def get_declared_override(self) -> set[tuple[int, int, int]]:
        overrides = set()
        blocks: TAG_List = self.__nbt__['blocks']
        block: TAG_Compound
        for block in blocks:
            pos: TAG_List = block['pos']
            x = pos[0].value
            y = pos[1].value
            z = pos[2].value
            position = Vector((x, y, z))
            position += self.vcap_offset
            position.freeze()
            overrides.add(position)

        return overrides


class IFrame(VcapFrame):
    __nbt__: TAG_Compound
    index: int
    vcap_offset = Vector()

    def __init__(self, nbt: TAG_Compound, index: int = 0, vcap_offset = Vector([0, 0, 0])) -> None:
        """创建一个IFrame对象。

        参数:
            nbt (TAG_Compound): 帧NBT数据。
            index (int, optional): 放入网格名称的帧号。默认为0。
        """
        self.__nbt__ = nbt
        self.overrides = dict()
        self.index = index
        self.time = nbt['time'].value
        self.vcap_offset = vcap_offset

    def get_meshes(self, vcontext: VCAPContext, settings: VCAPSettings, progress_function: Callable[[float], None] = None) -> list[Mesh]:
        sections: TAG_List[TAG_Compound] = self.__nbt__['sections']
        meshes: dict[Any, BMesh] = {}
        meshes['base'] = bmesh.new() # 第一个网格没有覆盖。
        for id in self.overrides:
            meshes[id] = bmesh.new()

        section: TAG_Compound
        num_sections = len(sections)
        for i in range(0, num_sections):
            # 每10个区块打印一次，这样不会减慢程序运行速度
            if i % 10 == 0:
                print(f'正在写入区段 {i}/{num_sections}', end='\r')
                if(progress_function): progress_function(i / num_sections)
            
            section = sections[i]
            palette: TAG_List = section['palette']
            offset = (section['x'].value, section['y'].value, section['z'].value)
            blocks: TAG_Int_Array = section['blocks']
            bblocks = blocks.value
            use_colors = False
            if settings.use_vertex_colors and ('colors' in section) and ('colorPalette' in section):
                color_palette_tag: TAG_Byte_Array = section['colorPalette']
                color_palette = color_palette_tag.value
                colors_tag: TAG_Byte_Array = section['colors']
                colors = colors_tag.value
                use_colors = True

            for y in range(0, 16):
                for z in range(0, 16):
                    for x in range(0, 16):
                        index = bblocks.item((y * 16 + z) * 16 + x)
                        model_id: str = palette[index].value
                        block_mesh = vcontext.models[model_id]
                        if len(block_mesh.vertices) == 0:
                            continue
                        if use_colors:
                            i = colors.item((y * 16 + z) * 16 + x)
                            r = _read_unsigned(color_palette, i, 8) / 255
                            g = _read_unsigned(color_palette, i + 1, 8) / 255
                            b = _read_unsigned(color_palette, i + 2, 8) / 255
                            color = [r, g, b, 1]
                        else:
                            color = [1, 1, 1, 1]

                        world_pos = Vector((offset[0] * 16 + x, offset[1] * 16 + y, offset[2] * 16 + z))
                        world_pos += self.vcap_offset
                        world_pos.freeze()
                        mesh_index = 'base'

                        for id, vals in self.overrides.items():
                            if world_pos in vals:
                                mesh_index = id
                                break

                        util.add_mesh(meshes[mesh_index], block_mesh, Matrix.Translation(world_pos), color=color)
    
        final_meshes: dict[Any, Mesh] = {}
        for id in meshes:
            mesh = meshes[id]
            if len(mesh.verts) == 0: continue
            outMesh = bpy.data.meshes.new(f'{vcontext.name}.f{self.index}')
            mesh.to_mesh(outMesh)
            final_meshes[id] = outMesh

        return final_meshes

    def get_declared_override(self) -> set[Vector]:
        return set()

def _read_unsigned(array: ndarray, index: int, bit_depth: int = 8):
    item = array.item(index)
    if (item < 0):
        return item + 2**bit_depth
    else:
        return item

def _make_unsigned(val: int, bit_depth: int = 8):
    if (val < 0):
        return val + 2**bit_depth
    else:
        return val