import bpy
from bpy.types import Scene

def register():
    bpy.types.Scene.vcap_offset = bpy.props.IntVectorProperty(
        name="Vcap偏移", default=[0,0,0],
        description="我的世界坐标和Blender坐标之间的关系（不考虑空间转换）")

def unregister():
    del bpy.types.Scene.vcap_offset

def vcap_offset(scene: Scene) -> list[int]:
    """获取场景的当前vcap偏移。

    Args:
        scene (Scene): 要使用的场景。

    Returns:
        list[float]: 在Blender坐标空间中的当前偏移。
    """
    return scene.vcap_offset

def vcap_offset_mc(scene: Scene):
    """获取场景的当前vcap偏移（MC坐标）。

    Args:
        scene (Scene): 要使用的场景。

    Returns:
        list[float]: 在我的世界坐标空间中的当前偏移。
    """
    offset = vcap_offset(scene)
    return [offset[0], offset[2], -offset[1]]