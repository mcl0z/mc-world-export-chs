from email.mime import base
from enum import auto
from io import BytesIO
import math
import time
import itertools
from typing import IO, Generic, Iterable, Sequence, TypeVar
from collections import OrderedDict

from numpy import true_divide
from bpy.types import Mesh, Collection, Context, Material, Object, PoseBone, EditBone, Action
from mathutils import Euler, Matrix, Quaternion, Vector

from ..vcap.import_obj import load as load_obj
from .. import data
import xml.etree.ElementTree as ET
import bpy  

class AnimChannel:
    __slots__ = (
        # FCurve的数据路径
        'datapath',
        # 文件中的骨骼名称。ROOT表示根骨骼。
        'bone_name',
        # 包含通道中所有关键帧的字典。
        'keyframes'
    )
    
    datapath: str
    bone_name: str
    keyframes: dict[int, Sequence[float]]
    
    def __init__(self, bone_name: str, datapath: str) -> None:
        self.bone_name = bone_name
        self.datapath = datapath
        self.keyframes = {}

def _simple_load_obj(context: Context, file_contents: str, unique_materials: dict[str, Material]):
    obj = BytesIO(bytes(file_contents, 'utf-8'))
    return load_obj(context, obj, use_split_objects=False, use_split_groups=False, use_groups_as_vgroups=True, unique_materials=unique_materials)

def load_entity(file: IO[str], context: Context, collection: Collection, materials: dict[str, Material] = {}, separate_parts = False, autohide = True):
    """将回放实体加载到Blender中

    参数:
        file (IO[str]): 原始XML文件
        context (Context): Blender上下文
        collection (Collection): 要添加到的集合。

    抛出:
        Exception: 如果XML格式不正确
    """
    start_time = time.time()
    tree = ET.parse(file)
    entity = tree.getroot()
    name = entity.get('name')
    if not name:
        name = 'entity'
        
    anim = entity.find('anim')
    animtext = anim.text
    
    # 模型
    model = entity.find('model')
    if model is None:
        raise Exception("实体XML缺少model标签。")
    
    mesh_tag = model.find('mesh')
    parsed_objs: list[Object] = []

    multipart = ('rig-type' in model.attrib) and (model.attrib['rig-type'] == 'multipart')
    seperate = set()
    
    # 网格与其所属骨骼索引之间的可选映射。
    object_mapping: dict[Object, int] = {}
    
    if multipart:
        armature_obj, bone_def, meshes, seperate, override_channels = parse_multipart(model, context, collection, name=f'{name}.bones', materials=materials, animtext=animtext)

        for mesh in meshes.keys():
            obj = bpy.data.objects.new(f'{name}.{bone_def[meshes[mesh]]}.mesh', mesh)
            collection.objects.link(obj)

            group = obj.vertex_groups.new(name=bone_def[meshes[mesh]])
            group.add(range(0, len(mesh.vertices)), 1, type='REPLACE')

            parsed_objs.append(obj)
            
            # 仅当标记为seperate且稍后不会被删除时，才传输到对象映射中。
            if mesh in seperate:
                object_mapping[obj] = meshes[mesh]
            
        
    else:
        armature_obj, bone_def, override_channels = parse_armature(model, context, collection, name=f'{name}.bones')

        if mesh_tag is not None:
            meshes, mats, vertex_groups = _simple_load_obj(context, mesh_tag.text, materials)
            
            for obj in meshes:
                new_object = bpy.data.objects.new(f'{name}.mesh', obj)
                collection.objects.link(new_object)
                # new_object.rotation_euler[0] = math.radians(90) // 骨架负责处理这个
                
                for group_name, group_indices in vertex_groups.items():
                    group = new_object.vertex_groups.new(name=group_name.decode('utf-8', "replace"))
                    group.add(group_indices, 1.0, 'REPLACE')
                parsed_objs.append(new_object)
        else:
            print("警告：在实体XML中未找到网格。")
    
    override_channel_types = {}
    for channel, type in override_channels:
        override_channel_types[channel] = type
    
    # 将网格作为子对象附加到骨架
    def attach_armature(obj: Object, armature: Object):
        obj.parent = armature
        mod = obj.modifiers.new('Armature', 'ARMATURE')
        mod.object = armature

    final_objects: list[Object]
    
    if len(parsed_objs) > 0:
        if separate_parts:
            for obj in parsed_objs:
                attach_armature(obj, armature_obj)
            final_objects = parsed_objs
        else:
            final_objects = []
            
            base_mesh = bpy.data.meshes.new(f'{name}.mesh')
            base_object = bpy.data.objects.new(f'{name}.mesh', base_mesh)
            collection.objects.link(base_object)
            final_objects.append(base_object)
            
            bpy.ops.object.select_all(action='DESELECT')
            base_object.select_set(True)
            context.view_layer.objects.active = base_object
            for obj in parsed_objs:
                if obj.data in seperate:
                    final_objects.append(obj)
                else:
                    obj.select_set(True)

            bpy.ops.object.join()
            
            for obj in final_objects:
                attach_armature(obj, armature_obj)
    else:
        print(f"实体 {name} 没有网格！")
        final_objects = []
    
    # 动画
    if (anim is not None):
        root_pos = AnimChannel('ROOT', 'location')
        root_rot = AnimChannel('ROOT', 'rotation_quaternion')
        root_scale = AnimChannel('ROOT', 'scale')
        
        root_scale.keyframes[0] = [1, 1, 1] # 如果文件没有任何缩放关键帧。
        
        pos_channels: dict[PoseBone, AnimChannel] = {}
        rot_channels: dict[PoseBone, AnimChannel] = {}
        scale_channels: dict[PoseBone, AnimChannel] = {}
        
        vis_channels: dict[Object, list[tuple[float, float]]] = {}
        object_cache: dict[PoseBone, Object] = {} # 用于可见度动画的对象缓存
        
        bl_override_channels: dict[str, AnimChannel] = {}
        
        armature_obj.rotation_mode = 'QUATERNION'
        render = context.scene.render
        scene_framerate = render.fps / render.fps_base
        
        fps = anim.get('fps')
        anim_start_time = float(anim.get('start-time', "0"))

        if fps:
            framerate = float(fps)
        else:
            framerate = scene_framerate
        
        def convert_frame(frame: float):
            return (frame / framerate + anim_start_time) * scene_framerate
        
        total_frames = 0
        offset = data.vcap_offset(context.scene)
        for index, frame in enumerate(animtext.splitlines()):
            total_frames += 1
            frame = frame.strip()
            scene_frame = convert_frame(index)
            
            # scene_frame = index / framerate * scene_framerate
            # 注意：稍后必须支持帧率匹配。
            
            bones = frame.split(';')
            
            # 根变换
            root_str = bones[0].strip()
            if len(root_str) > 0:
                root_vals = list(map(lambda i: float(i), root_str.split(' ')))
                length = len(root_vals)
                if length >= 4:
                    rotation = Quaternion(root_vals[0:4])
                    rotation.rotate(Euler((math.radians(90), 0, 0)))

                    root_rot.keyframes[index] = rotation
                
                if length >= 7:
                    location = root_vals[4:7]
                    # Switch coordinate space
                    root_pos.keyframes[index] = (
                        location[0] + offset[0],
                        -location[2] + offset[1],
                        location[1] + offset[2]
                    )
                
                if length >= 10:
                    root_scale.keyframes[index] = root_vals[7:10]
            
            for def_index, bone_str in enumerate(bones[1:]):
                
                bone_str = bone_str.strip()
                if (len(bone_str) == 0): continue
                
                bone_vals = [float(i) for i in bone_str.split(' ')]
                if len(bone_vals) == 0: continue

                # Override Channels
                if (def_index >= len(bone_def)):
                    channel_name, channel_mode = override_channels[def_index - len(bone_def)]
                    if (channel_name in bl_override_channels):
                        channel = bl_override_channels[channel_name]
                    else:
                        channel = AnimChannel(channel_name, f'["replay.{channel_name}"]')
                        bl_override_channels[channel_name] = channel
                    
                    if (channel_mode == 'vector'):
                        channel.keyframes[index] = bone_vals[0:3]
                    else:
                        channel.keyframes[index] = [bone_vals[0]]
                    
                    continue    
                
                # Get the pose bone based on the definition order.
                bone = armature_obj.pose.bones[bone_def[def_index]]
                
                if len(bone_vals) >= 4:
                    if bone in rot_channels:
                        channel = rot_channels[bone]
                    else:
                        channel = AnimChannel(bone.name, f'pose.bones["{bone.name}"].rotation_quaternion')
                        rot_channels[bone] = channel
                    
                    rotation = Quaternion(bone_vals[0:4])

                    channel.keyframes[index] = rotation
                
                if len(bone_vals) >= 7:
                    if bone in pos_channels:
                        channel = pos_channels[bone]
                    else:
                        channel = AnimChannel(bone.name, f'pose.bones["{bone.name}"].location')
                        pos_channels[bone] = channel
                    
                    channel.keyframes[index] = bone_vals[4:7]      
                
                if len(bone_vals) >= 10:
                    if bone in scale_channels:
                        channel = scale_channels[bone]
                    else:
                        channel = AnimChannel(bone.name, f'pose.bones["{bone.name}"].scale')
                        channel.keyframes[0] = (1, 1, 1) # If the bone doesn't have have any scale keyframes.
                        scale_channels[bone] = channel
                    
                    channel.keyframes[index] = bone_vals[7:10]
                
                # Part visibility
                if len(bone_vals) >= 11:
                    obj = None
                    
                    # Find bone mesh
                    if bone in object_cache:
                        obj = object_cache[bone]
                    else:
                        for c_obj, index in object_mapping.items():
                            if index == def_index:
                                obj = c_obj
                                break
                        object_cache[bone] = obj
                    
                    if obj is not None:
                        if obj not in vis_channels:
                            vis_channels[obj] = []
                        
                        vis_channels[obj].append((scene_frame, 1 - bone_vals[10]))
                        
                        ...
                    
                    
        anim_data = armature_obj.animation_data_create()
        action = bpy.data.actions.new(name=f"{name}_action")
        anim_data.action = action
        
        # Add F curves
        def add_curve(action: Action, channel: AnimChannel, index: int = 0):
            curve = action.fcurves.new(data_path=channel.datapath, index=index)
            keyframe_points = curve.keyframe_points
            
            # Gotta love data manipulation.
            keyframes = [(
                (frame / framerate + anim_start_time) * scene_framerate,
                val[index]
            ) for frame, val in channel.keyframes.items()]
            
            
            keyframe_points.add(len(keyframes))
            keyframe_points.foreach_set('co', list(itertools.chain.from_iterable(keyframes)))
            keyframe_points.foreach_set('interpolation', [1] * len(keyframes))
        
        for i in range(0, 3): add_curve(action, root_pos, i)
        for i in range(0, 4): add_curve(action, root_rot, i)
        for i in range(0, 3): add_curve(action, root_scale, i)
        
        for channel in pos_channels.values():
            for i in range(0, 3): add_curve(action, channel, i)
        
        for channel in rot_channels.values():
            for i in range(0, 4): add_curve(action, channel, i)
            
        for channel in scale_channels.values():
            for i in range(0, 3): add_curve(action, channel, i)
        
        actions: dict[Object, Action] = {}

        # MESH ACTIONS
        for obj in final_objects:
            obj: Object
            anim_data = obj.animation_data_create()
            actions[obj] = bpy.data.actions.new(name=f'{obj.name}_action')
            anim_data.action = actions[obj]

        # Deal with visibility
        if autohide:
            start_frame = anim_start_time * scene_framerate
            end_frame = convert_frame(total_frames)

            for obj in final_objects:
                use_start = False
                if obj not in vis_channels:
                    vis_channels[obj] = []
                    use_start = True
                if start_frame != 0:
                    vis_channels[obj].append((0, 1))

                # Objects with visibility anim handle this already.
                if use_start:
                    vis_channels[obj].append((start_frame, 0))
                    
                vis_channels[obj].append((end_frame, 1))

        for obj, keys in vis_channels.items():
            action = actions[obj]
            
            curve_render = action.fcurves.new('hide_render', index=0)
            curve_viewport = action.fcurves.new('hide_viewport', index=1)
            
            curve_render.keyframe_points.add(len(keys))
            curve_viewport.keyframe_points.add(len(keys))
            
            bkeys = list(itertools.chain.from_iterable(keys))
            
            curve_render.keyframe_points.foreach_set('co', bkeys)
            curve_viewport.keyframe_points.foreach_set('co', bkeys)
            
            curve_render.keyframe_points.foreach_set('interpolation', [0] * len(keys))
            curve_viewport.keyframe_points.foreach_set('interpolation', [0] * len(keys))
            
        # Override channels
        for obj, action in actions.items():
            for override_name, channel, in bl_override_channels.items():
                if override_channel_types[override_name] == 'vector':
                    obj[f'replay.{override_name}'] = [0.0, 0.0, 0.0]
                    for i in range(0, 3): add_curve(action, channel, index=i)
                else:
                    obj[f'replay.{override_name}'] = 0.0
                    add_curve(action, channel, index=0)
                ...

    return name

def parse_armature(model: ET.Element, context: Context, collection: Collection, name="entity"):
    """解析骨架数据"""
    armature = bpy.data.armatures.new(name)
    obj: Object = bpy.data.objects.new(name, armature)

    collection.objects.link(obj)
    context.view_layer.objects.active = obj
    
    definition_order: list[str] = []
    override_channels: list[tuple[str, str]] = []

    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.edit_bones
    id = 0
    
    def load_bone(element: ET.Element):
        if element.tag != 'bone': return
        nonlocal id

        attrib = element.attrib
        
        if 'name' in attrib.keys():
            name = attrib['name']
        else:
            name = f'bone{id}'
        
        if 'len' in attrib.keys():
            length = float(attrib['len'])
        else:
            length = '.16'

        bone = edit_bones.new(name)
        bone.head = [0, 0, 0]
        bone.tail = [0, length, 0]

        if 'pos' in attrib:
            pos = Vector(map(float, attrib['pos'].split(',')))
        else:
            pos = Vector()
        
        if 'rot' in attrib:
            rot = Quaternion(map(float, attrib['rot'].split(',')))
        else:
            rot = Quaternion()

        transformation: Matrix = Matrix.Translation(pos) @ rot.to_matrix().to_4x4()
        bone.transform(transformation)
        
        id += 1
        definition_order.append(name)
        
        for child in element:
            load_bone(child)
        
        
    for element in model:
        if (element.tag == 'override_channel'):
            override_channels.append((element.attrib['name'], element.attrib['type']))
        else:
            load_bone(element)

    bpy.ops.object.mode_set(mode='OBJECT')
    obj.rotation_euler[0] = math.radians(90)
    return (obj, definition_order, override_channels)
    
def parse_multipart(model: ET.Element,
                    context: Context,
                    collection: Collection,
                    name="entity",
                    materials: dict[str, Material] = {},
                    animtext: str=""):
    """解析多部件模型"""


    armature = bpy.data.armatures.new(name)
    obj: Object = bpy.data.objects.new(name, armature)

    collection.objects.link(obj)
    context.view_layer.objects.active = obj

    definition_order: list[str] = []
    meshes: dict[Mesh, int] = {}
    seperate: set[Mesh] = set()

    override_channels: list[tuple[str, str]] = []

    bpy.ops.object.mode_set(mode = 'EDIT')
    edit_bones = armature.edit_bones
    id = 0
    
    frames: list[list[str]] = []
    for frame in animtext.strip().splitlines():
        frames.append(frame.strip().split(';'))
        
    def load_bone(element: ET.Element, parent: EditBone | None = None):
        if element.tag != 'part': return
        nonlocal id

        attrib = element.attrib

        if 'name' in attrib.keys():
            name = attrib['name']
        else:
            name = f'bone{id}'
        
        length = 0.16

        bone = edit_bones.new(name)
        name = bone.name
        
        bone.parent = parent
        
        bone.head = [0, 0, 0]
        bone.tail = [0, length, 0]

        definition_order.append(name)

        # Not all model parts have meshes.
        mesh_tag = element.find('mesh')
        if (mesh_tag is not None) and (mesh_tag.text is not None):
            n_meshes, mats, vertex_groups = _simple_load_obj(context, mesh_tag.text, materials)
            for mesh in n_meshes:
                meshes[mesh] = id
        
        # Check if visibility gets changed
        for frame in frames:
            if len(frame) <= id + 1: continue
            transform = frame[id + 1].split(' ')
            if len(transform) <= 10: continue
            if transform[10] == '0':
                # This codebase gets more and more messy lol.
                try:
                    seperate.add(mesh)
                except NameError:
                    print("Bone " + name + " did not have a mesh.")
                continue
        
        
        id += 1
        for child in element:
            load_bone(child, bone)

    
    for element in model:
        if (element.tag == 'override_channel'):
            override_channels.append((element.attrib['name'], element.attrib['type']))
        else:
            load_bone(element)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.rotation_euler[0] = math.radians(90)
    return (obj, definition_order, meshes, seperate, override_channels)

