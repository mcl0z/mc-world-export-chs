import io
import json
from logging import warn, warning
import os
from re import S
import sys
import time
import traceback
from typing import IO, Callable, Union
from zipfile import ZipFile
import zipfile

import numpy as np
import bpy

from bpy.types import Collection, Context, Image, Material, Operator
from ..vcap import util
from . import entity
from ..vcap.context import VCAPSettings
from ..vcap import vcap_importer
from ..vcap import materials as matlib

do_profiling = False
LINE_CLEAR = '\x1b[2K'  # <-- ANSI序列


class ReplaySettings:
    __slots__ = (
        'world',
        'entities',
        'separate_parts',
        'vcap_settings',
        'hide_entities',
        'automatic_offset'
    )

    world: bool
    entities: bool
    separate_parts: bool
    vcap_settings: VCAPSettings
    hide_entities: bool
    automatic_offset: bool

    def __init__(self, world=True, entities=True, vcap_settings=VCAPSettings(merge_verts=False), separate_parts=False, hide_entities=True, automatic_offset=True) -> None:
        self.world = world
        self.entities = entities
        self.vcap_settings = vcap_settings
        self.separate_parts = separate_parts
        self.hide_entities = hide_entities
        self.automatic_offset = automatic_offset

class ExecutionHandle:
    __slots__ = (
        '__onProgress',
        '__onFeedback',
        '__onWarning',
        '__onError'
    )

    __onProgress: Callable[[float], None]
    __onFeedback: Callable[[str], None]
    __onWarning: Callable[[str], None]
    __onError: Callable[[str], None]

    def __default_progress(val):
        pass

    def __default_feedback(val):
        print(val)

    def __default_warning(val):
        warn(val)

    def __default_error(val):
        warn(val)

    def __init__(self, onProgress: Callable[[float], None] = __default_progress,
                 onFeedback: Callable[[str], None] = __default_feedback,
                 onWarning: Callable[[str], None] = __default_warning,
                 onError: Callable[[str], None] = __default_error) -> None:
        self.__onProgress = onProgress
        self.__onFeedback = onFeedback
        self.__onWarning = onWarning
        self.__onError = onError

    def progress(self, val: float):
        self.__onProgress(val)

    def feedback(self, message: str):
        self.__onFeedback(message)
    
    def warn(self, message: str):
        self.__onWarning(message)
    
    def error(self, message: str):
        self.__onError(message)


def load_replay(file: Union[str, IO[bytes]],
                context: Context,
                collection: Collection,
                handle: ExecutionHandle = ExecutionHandle(),
                settings: ReplaySettings = ReplaySettings()):
    if do_profiling:
        import cProfile
        import pstats
        pr = cProfile.Profile()
        pr.enable()
    
    textures: dict[str, Image] = {}
    materials: dict[str, Material] = {}

    handle.progress(0)
    start_time = time.time()
    with ZipFile(file, 'r') as archive:
        # 元数据
        with archive.open('meta.json', 'r') as meta_file:
            meta = json.load(meta_file)
            if settings.automatic_offset:
                if 'offset' in meta:
                    offset = meta['offset']
                else:
                    # TODO: 自动偏移检测
                    offset = [0, 0, 0]
                    handle.warn("回放文件中未找到世界偏移！")

                # 在data.py中注册的自定义属性
                context.scene.vcap_offset = [offset[0], -offset[2], offset[1]] # 切换坐标空间

        # 世界
        if settings.world:
            def wold_progress_function(progress):
                # context.window_manager.progress_update(progress * .5)
                handle.progress(progress * .5)

            world_collection = bpy.data.collections.new('world')
            collection.children.link(world_collection)
            with archive.open('world.vcap') as world_file:
                vcap_importer.load(world_file,
                                   world_collection,
                                   context,
                                   settings=settings.vcap_settings,
                                   progress_function=wold_progress_function)

        # 材质
        def load_texture(tex_name: str, is_data=False):
            if tex_name in textures:
                return textures[tex_name]

            filename = f'tex/{tex_name}.png'
            if filename not in archive.namelist():
                handle.warn(f'回放存档中缺少{tex_name}！')
                return None
            
            with archive.open(filename) as file:
                image = util.import_image(file, os.path.basename(tex_name), is_data=is_data)
                textures[tex_name] = image
                return image

        for entry in archive.filelist:
            n = entry.filename
            if n.startswith('mat/') and n.endswith('.json'):
                defname = os.path.splitext(n[(n.find('/') + 1):])[0] # 移除'mat/'
                materials[defname] = matlib.parse_raw(
                    json.load(archive.open(entry)),
                    os.path.basename(n), load_texture)


        # 实体
        if settings.entities:
            print("解析实体中...")
            ent_collection = bpy.data.collections.new('entities')
            collection.children.link(ent_collection)

            ent_folder = zipfile.Path(archive, 'entities/')
            if not ent_folder.is_dir():
                raise RuntimeError("回放中的'entities'条目必须是一个目录！")

            entity_files = [path for path in ent_folder.iterdir() if path.name.endswith('.xml')]
            # entity_files = [file for file in archive.filelist if file.filename.endswith(".xml")]

            size = len(entity_files)    
            for index, entry in enumerate(entity_files):
                handle.progress((.5 * index / size) + .5)
                try:
                    with entry.open('r') as e:
                        name = entity.load_entity(e, context, ent_collection, materials, separate_parts=settings.separate_parts, autohide=settings.hide_entities)
                        print(f"已加载实体 {index + 1}/{size}: {name}                    ", end='\r') # 可怕的黑客技巧来修复回车覆盖问题
                except Exception as ex:
                    handle.error(f"加载实体 {entry.name} 时出错。详情请查看控制台。")
                    traceback.print_exception(ex)
            print("实体加载完成。")

        handle.feedback(f"在 {round(time.time() - start_time, 2)} 秒内导入了回放。")

    if do_profiling:
        pr.disable()
        prof_savedir = os.path.join(os.path.dirname(__file__), "prof")
        prof_modelname = "replay"
        prof_savepath = os.path.join(prof_savedir, f"{prof_modelname}.prof")
        if not os.path.exists(prof_savedir):
            os.mkdir(prof_savedir)

        ps = pstats.Stats(pr, stream=sys.stdout).sort_stats('cumulative')
        print("")
        print("部分性能分析结果:")
        print("")
        ps.print_stats(20)

        pr.dump_stats(prof_savepath)
        print("")
        print(f"代码性能分析数据已保存到 {prof_savepath}")
        print(f"查看方式: snakeviz \"{prof_savepath}\"")