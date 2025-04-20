import bpy
from bpy.types import Panel, Operator
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty

from .replay import replay_file
from .vcap.context import VCAPSettings
from .import_replay_operator import ImportReplayOperator

class MINECRAFT_PT_import_panel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "我的世界导入"
    bl_label = "导入工具"

    def draw(self, context):
        layout = self.layout
        
        # 坐标偏移设置
        box = layout.box()
        box.label(text="坐标偏移")
        box.prop(context.scene, "vcap_offset")
        
        # 导入VCAP部分
        box = layout.box()
        row = box.row()
        row.label(text="导入体素捕捉")
        row = box.row()
        vcap_op = row.operator("vcap.import_vcap_sidebar", text="选择VCAP文件")
        
        # VCAP选项
        sub_box = box.box()
        sub_box.label(text="VCAP导入选项")
        col = sub_box.column()
        col.prop(context.scene, "vcap_use_vertex_colors", text="使用方块颜色")
        col.prop(context.scene, "vcap_merge_verts", text="合并顶点")
        
        # 导入回放部分
        box = layout.box()
        row = box.row()
        row.label(text="导入回放")
        row = box.row()
        replay_op = row.operator("vcap.import_replay_sidebar", text="选择回放文件")
        
        # 回放选项（按组划分）
        sub_box = box.box()
        sub_box.label(text="回放导入选项")
        
        # 回放常规选项
        col = sub_box.column()
        col.prop(context.scene, "replay_automatic_offset", text="自动偏移")
        
        # 世界选项
        world_box = sub_box.box()
        row = world_box.row()
        row.prop(context.scene, "replay_import_world", text="导入世界")
        
        col = world_box.column()
        col.active = context.scene.replay_import_world
        col.prop(context.scene, "replay_use_vertex_colors", text="使用方块颜色")
        col.prop(context.scene, "replay_merge_verts", text="合并顶点")
        
        # 实体选项
        entity_box = sub_box.box()
        row = entity_box.row()
        row.prop(context.scene, "replay_import_entities", text="导入实体")
        
        col = entity_box.column()
        col.active = context.scene.replay_import_entities
        col.prop(context.scene, "replay_hide_entities", text="自动隐藏实体")
        col.prop(context.scene, "replay_separate_parts", text="分离实体部件")

class ImportVcapSidebar(Operator, ImportHelper):
    """从侧边栏导入体素捕捉文件"""
    bl_idname = "vcap.import_vcap_sidebar"
    bl_label = "导入体素捕捉"

    filename_ext = ".vcap"

    filter_glob: StringProperty(
        default="*.vcap",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        from .vcap import vcap_importer
        from os import path
        
        vcap_importer.load(
            self.filepath,
            context.view_layer.active_layer_collection.collection,
            context,
            name=path.basename(self.filepath),
            settings=VCAPSettings(use_vertex_colors=context.scene.vcap_use_vertex_colors,
                                 merge_verts=context.scene.vcap_merge_verts))
        return {'FINISHED'}

class ImportReplaySidebar(Operator, ImportHelper):
    """从侧边栏导入我的世界回放文件"""
    bl_idname = "vcap.import_replay_sidebar"
    bl_label = "导入我的世界回放"

    filename_ext = ".replay"

    filter_glob: StringProperty(
        default="*.replay",
        options={'HIDDEN'},
        maxlen=255,
    )

    def __error(self, message: str):
        self.report({"ERROR"}, message)
        print("错误: "+message)
    
    def __warn(self, message: str):
        self.report({"WARNING"}, message)
        print("警告: "+message)
    
    def __feedback(self, message: str):
        self.report({"INFO"}, message)
        print("信息: "+message)

    def execute(self, context):
        settings = replay_file.ReplaySettings(
            world=context.scene.replay_import_world,
            entities=context.scene.replay_import_entities,
            separate_parts=context.scene.replay_separate_parts,
            hide_entities=context.scene.replay_hide_entities,
            automatic_offset=context.scene.replay_automatic_offset,

            vcap_settings=VCAPSettings(
                use_vertex_colors=context.scene.replay_use_vertex_colors,
                merge_verts=context.scene.replay_merge_verts
            )
        )
        
        handle = replay_file.ExecutionHandle(
            onProgress=lambda val : context.window_manager.progress_update(val),
            onFeedback=self.__feedback,
            onWarning=self.__warn,
            onError=self.__error
        )

        context.window_manager.progress_begin(min=0, max=1)
        replay_file.load_replay(self.filepath, context, context.scene.collection, handle=handle, settings=settings)
        context.window_manager.progress_end()
        return {'FINISHED'}

# 注册场景属性
def register_properties():
    # VCAP导入选项
    bpy.types.Scene.vcap_use_vertex_colors = BoolProperty(
        name="使用方块颜色",
        description="是否从文件加载方块颜色",
        default=True,
    )
    
    bpy.types.Scene.vcap_merge_verts = BoolProperty(
        name="合并顶点",
        description="导入完成后是否按距离合并顶点",
        default=True,
    )
    
    # 回放导入选项
    bpy.types.Scene.replay_import_world = BoolProperty(
        name="导入世界",
        description="导入世界方块（显著增加导入时间）",
        default=True
    )
        
    bpy.types.Scene.replay_import_entities = BoolProperty(
        name="导入实体",
        description="导入我的世界实体及其动画",
        default=True
    )

    bpy.types.Scene.replay_separate_parts = BoolProperty(
        name="分离实体部件",
        description="将实体中的每个模型部件作为单独的对象导入。仅适用于多部件实体。",
        default=False
    )
    
    bpy.types.Scene.replay_use_vertex_colors = BoolProperty(
        name="使用方块颜色",
        description="从文件导入方块颜色（草地色调等）。如果取消选中，世界可能看起来非常灰暗",
        default=True,
    )
    
    bpy.types.Scene.replay_merge_verts = BoolProperty(
        name="合并顶点",
        description="对导入的世界运行'按距离合并'操作。可能会表现出不可预测的行为",
        default=False
    )

    bpy.types.Scene.replay_hide_entities = BoolProperty(
        name="自动隐藏实体",
        description="在实体生成前和被杀死后隐藏它们",
        default=True
    )

    bpy.types.Scene.replay_automatic_offset = BoolProperty(
        name="自动偏移",
        description="从文件读取世界偏移，如果不存在则生成。如果取消选中，则使用场景范围的vcap偏移",
        default=True
    )

# 移除场景属性
def unregister_properties():
    del bpy.types.Scene.vcap_use_vertex_colors
    del bpy.types.Scene.vcap_merge_verts
    del bpy.types.Scene.replay_import_world
    del bpy.types.Scene.replay_import_entities
    del bpy.types.Scene.replay_separate_parts
    del bpy.types.Scene.replay_use_vertex_colors
    del bpy.types.Scene.replay_merge_verts
    del bpy.types.Scene.replay_hide_entities
    del bpy.types.Scene.replay_automatic_offset

# 所有需要注册的类
classes = (
    MINECRAFT_PT_import_panel,
    ImportVcapSidebar,
    ImportReplaySidebar
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_properties()

def unregister():
    unregister_properties()
    for cls in classes:
        bpy.utils.unregister_class(cls) 