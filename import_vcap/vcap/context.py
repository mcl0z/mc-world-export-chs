from zipfile import ZipFile

import bmesh
from bmesh.types import BMesh
from bpy.types import Collection, Context, Image, Material, Mesh, NodeTree, Object

class VCAPContext:
    archive: ZipFile
    """我们正在读取的zip文件。
    """

    collection: Collection
    """要导入到的集合。
    """

    context: Context
    """当前Blender上下文。
    """

    name: str
    """文件的名称。
    """

    materials: dict[str, Material] = {}
    material_groups: dict[str, NodeTree] = {}
    models: dict[str, Mesh] = {}

    textures: dict[str, Image]

    target: BMesh
    """我们正在构建最终网格的BMesh。
    """
    
    def __init__(self, archive: ZipFile, collection: Collection, context: Context, name: str) -> None:
        """创建VCAP上下文

        参数:
            archive (ZipFile): 已加载的VCAP存档。
            collection (Collection): 要导入到的集合。
            context (Context): Blender上下文。
        """
        self.archive = archive
        self.context = context
        self.name = name
        self.models = {}
        self.materials = {}
        self.material_groups = {}
        self.textures = {}

        self.collection = collection

        self.target = bmesh.new()

class VCAPSettings:
    __slots__ = (
        'use_vertex_colors',
        'merge_verts'
    )
    
    use_vertex_colors: bool
    merge_verts: bool

    def __init__(self, use_vertex_colors=True, merge_verts=True):
        self.use_vertex_colors = use_vertex_colors
        self.merge_verts = merge_verts