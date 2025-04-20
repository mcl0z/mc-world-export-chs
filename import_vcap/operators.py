from os import name, path

from .vcap.context import VCAPSettings

from .vcap import vcap_importer, import_obj
from .replay import entity, replay_file
from . import camera_export
from bpy.types import Context, Operator, Object
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
import bpy

# ImportHelper是一个辅助类，定义了文件名和
# invoke()函数，用于调用文件选择器。

class ImportVcap(Operator, ImportHelper):
    """导入体素捕捉文件。在回放导入器内部使用。"""
    bl_idname = "vcap.import_vcap"
    bl_label = "导入VCAP"

    # ImportHelper混合类使用这个
    filename_ext = ".txt"

    filter_glob: StringProperty(
        default="*.vcap",
        options={'HIDDEN'},
        maxlen=255,  # 最大内部缓冲区长度，更长的将被截断。
    )

    # 操作符属性列表，这些属性将在调用前
    # 从操作符设置分配给类实例。
    use_vertex_colors: BoolProperty(
        name="使用方块颜色",
        description="是否从文件加载方块颜色。",
        default=True,
    )

    merge_verts: BoolProperty(
        name="合并顶点",
        description="导入完成后是否按距离合并顶点。",
        default=True,
    )

    def execute(self, context: Context):
        vcap_importer.load(
            self.filepath,
            context.view_layer.active_layer_collection.collection,
            context,
            name=path.basename(self.filepath),
            settings=VCAPSettings(use_vertex_colors=self.use_vertex_colors,
                                  merge_verts=self.merge_verts))
        return {'FINISHED'}


class ImportEntityOperator(Operator, ImportHelper):
    """导入单个回放实体。通常仅用于测试。"""
    bl_idname = "vcap.importentity"
    bl_label = "导入回放实体"

    # ImportHelper混合类使用这个
    filename_ext = ".txt"

    filter_glob: StringProperty(
        default="*.xml",
        options={'HIDDEN'},
        maxlen=255,  # 最大内部缓冲区长度，更长的将被截断。
    )

    def execute(self, context: Context):
        with open(self.filepath) as file:
            entity.load_entity(file, context, context.scene.collection)
        return {'FINISHED'}

class ExportCameraXMLOperator(Operator, ExportHelper):
    bl_idname = "vcap.exportcameraxml"
    bl_label = "导出相机XML"

    filename_ext = ".xml"
    
    def execute(self, context: Context):
        obj: Object = context.active_object
        if (obj == None):
            return self.fail("未选择相机。")
        elif (obj.type != 'CAMERA'):
            return self.fail("选定的对象必须是相机。")
        
            
        camera_export.write(self.filepath, obj, context)
        return {'FINISHED'}
    
    def fail(self, message: str):
        self.report({'ERROR'}, message)
        return {'CANCELLED'}


# 仅当你想添加到动态菜单时需要
def menu_func_import(self, context):
    self.layout.operator(ImportVcap.bl_idname,
                         text="体素捕捉 (.vcap)")

# 仅当你想添加到动态菜单时需要
def menu_func_import2(self, context):
    self.layout.operator(ImportEntityOperator.bl_idname,
                         text="测试回放实体 (.xml)")

def menu_func_camera_xml(self, context):
    self.layout.operator(ExportCameraXMLOperator.bl_idname,
                         text="相机动画 (.xml)")

def register():
    bpy.utils.register_class(ImportVcap)
    bpy.utils.register_class(ImportEntityOperator)
    bpy.utils.register_class(ExportCameraXMLOperator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    # bpy.types.TOPBAR_MT_file_import.append(menu_func_import2)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_camera_xml)


def unregister():
    bpy.utils.unregister_class(ImportVcap)
    bpy.utils.unregister_class(ImportEntityOperator)
    bpy.utils.unregister_class(ExportCameraXMLOperator)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    # bpy.types.TOPBAR_MT_file_import.remove(menu_func_import2)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_camera_xml)
