# 本程序是自由软件；您可以根据自由软件基金会
# 发布的GNU通用公共许可证（GPL）的条款重新分发
# 和/或修改它；使用GPL第3版或（由您选择）
# 任何更新的版本。
#
# 本程序的分发是希望它能有用，但不提供任何
# 保证；甚至没有对适销性或特定用途适用性的
# 默示保证。有关更多详细信息，请参阅GNU
# 通用公共许可证。
#
# 您应该已经收到了与此程序一起的GNU通用公共
# 许可证的副本。如果没有，请参阅<http://www.gnu.org/licenses/>。

bl_info = {
    "name" : "导入我的世界replay文件",
    "author" : "Igrium",
    "description" : "Igrium的回放导出器的Blender组件",
    "blender" : (3, 6, 0),
    "version" : (0, 0, 0),
    "location" : "视图3D > 侧边栏 > MCreplay导入",
    "warning" : "此插件仍在开发中。Github:",
    "category" : "导入-导出"
}

from . import operators, import_replay_operator, data
from . import sidebar_panel

def register():
    data.register()
    operators.register()
    import_replay_operator.register()
    sidebar_panel.register()

def unregister():
    data.unregister()
    operators.unregister()
    import_replay_operator.unregister()
    sidebar_panel.unregister()
