# 将导入回放操作符放在自己的文件中，因为它太大了。

from os import name, path

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Context, Operator, Panel
from bpy_extras.io_utils import ImportHelper

from .replay import replay_file
from .vcap.context import VCAPSettings


class ImportReplayOperator(Operator, ImportHelper):
    bl_idname = "vcap_import.replay"
    bl_label = "导入我的世界回放"

    # ImportHelper混合类使用这个
    filename_ext = ".txt"

    filter_glob: StringProperty(
        default="*.replay",
        options={'HIDDEN'},
        maxlen=255,  # 最大内部缓冲区长度，更长的将被截断。
    )
    
    import_world: BoolProperty(
        name="导入世界",
        description="导入世界方块（显著增加导入时间）",
        default=True
    )
        
    import_entities: BoolProperty(
        name="导入实体",
        description="导入我的世界实体及其动画",
        default=True
    )

    separate_parts: BoolProperty(
        name="分离实体部件",
        description="将实体中的每个模型部件作为单独的对象导入。仅适用于多部件实体。",
        default=False
    )
    
    use_vertex_colors: BoolProperty(
        name="使用方块颜色",
        description="从文件导入方块颜色（草地色调等）。如果取消选中，世界可能看起来非常灰暗",
        default=True,
    )
    
    merge_verts: BoolProperty(
        name="合并顶点",
        description="对导入的世界运行'按距离合并'操作。可能会表现出不可预测的行为",
        default=False
    )

    hide_entities: BoolProperty(
        name="自动隐藏实体",
        description="在实体生成前和被杀死后隐藏它们",
        default=True
    )

    automatic_offset: BoolProperty(
        name="自动偏移",
        description="从文件读取世界偏移，如果不存在则生成。如果取消选中，则使用场景范围的vcap偏移",
        default=True
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

    def execute(self, context: Context):
        settings = replay_file.ReplaySettings(
            world=self.import_world,
            entities=self.import_entities,
            separate_parts=self.separate_parts,
            hide_entities=self.hide_entities,
            automatic_offset=self.automatic_offset,

            vcap_settings=VCAPSettings(
                use_vertex_colors=self.use_vertex_colors,
                merge_verts=self.merge_verts
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
    
    def draw(self, context):
        pass

class REPLAY_PT_import_replay(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "回放"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context: Context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "VCAP_IMPORT_OT_replay"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        operator: ImportReplayOperator = context.space_data.active_operator

        layout.prop(operator, 'automatic_offset')

class REPLAY_PT_import_world(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "导入世界"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "VCAP_IMPORT_OT_replay"
    
    def draw_header(self, context):
        sfile = context.space_data
        operator = sfile.active_operator

        self.layout.prop(operator, "import_world", text='')
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        operator: ImportReplayOperator = context.space_data.active_operator
        layout.enabled = operator.import_world

        layout.prop(operator, 'use_vertex_colors')
        layout.prop(operator, 'merge_verts')

class REPLAY_PT_import_entities(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "导入实体"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "VCAP_IMPORT_OT_replay"
    
    def draw_header(self, context):
        sfile = context.space_data
        operator = sfile.active_operator

        self.layout.prop(operator, "import_entities", text='')
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        operator: ImportReplayOperator = context.space_data.active_operator
        layout.enabled = operator.import_entities

        layout.prop(operator, 'hide_entities')
        layout.prop(operator, 'separate_parts')

def _menu_func_replay(self, context):
    self.layout.operator(ImportReplayOperator.bl_idname,
                         text="我的世界回放文件 (.replay)")

classes = (
    ImportReplayOperator,
    REPLAY_PT_import_replay,
    REPLAY_PT_import_world,
    REPLAY_PT_import_entities
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(_menu_func_replay)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.types.TOPBAR_MT_file_import.remove(_menu_func_replay)