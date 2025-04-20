from typing import IO, Sequence
from bmesh.types import BMesh
import bpy
from bpy.types import Image, Mesh, MeshLoopColor
from mathutils import Matrix, Vector

COLOR_LAYER = "tint"

def add_mesh(mesh1: BMesh, mesh2: Mesh, matrix: Matrix=Matrix.Identity(4), color: list[float]=[1,1,1,1]):
    """将一个网格的内容添加到另一个网格中。

    参数:
        mesh1 (Mesh): 基础网格。
        mesh2 (Mesh): 要添加的网格。
        offset (Sequence[float, float, float]): 偏移向量
    """
    if not COLOR_LAYER in mesh2.vertex_colors:
        mesh2.vertex_colors.new(name=COLOR_LAYER)
    
    vcolors = mesh2.vertex_colors[COLOR_LAYER]
    i = 0
    for poly in mesh2.polygons.values():
        for idx in poly.loop_indices:
            vcolors.data[idx].color = (color[0], color[1], color[2], color[3])

    mesh2.transform(matrix)
    mesh1.from_mesh(mesh2)
    mesh2.transform(matrix.inverted())

def import_image(file: IO[bytes], name: str, alpha=True, is_data=False) -> Image:
    """将IO流中的图像打包到当前blend文件中。

    参数:
        file (IO[bytes]): PNG文件的原始数据。
        name (str): 给数据块的名称。
        alpha (bool, optional): 使用透明通道。默认为True。
        is_data (bool, optional): 使用非颜色数据颜色空间创建图像。默认为False。

    返回:
        [type]: 加载的图像数据块。
    """
    data = file.read()

    image = bpy.data.images.new(name, 1024, 1024, alpha=alpha, is_data=is_data)
    image.file_format = 'PNG'
    image.pack(data=data, data_len=len(data))
    image.source = 'FILE'

    return image