import asyncio
from typing import Union

from clilte import BasePlugin, PluginMetadata
from arclet.alconna.tools import RichConsoleFormatter
from arclet.alconna import (
    Option,
    Alconna,
    Arparma,
    CommandMeta,
)

from ...log import tts_logger
from ...config import tts_config, model_config


class TTSUpdate(BasePlugin):
    def init(self) -> Union[Alconna, str]:
        return Alconna(
            "tts",
            Option("-uc|--update-cache", help_text="更新TTS模型列表"),
            meta=CommandMeta("DeepSeekTTS 相关指令"),
            formatter_type=RichConsoleFormatter,
        )

    def meta(self) -> PluginMetadata:
        return PluginMetadata("TTSUpdate", "0.0.1", "更新TTS模型配置缓存", ["tts"], ["FrostN0v0"])

    def dispatch(self, result: Arparma) -> Union[bool, None]:
        if result.find("tts.update-cache"):
            available_models = asyncio.run(tts_config.get_available_tts())
            if available_models:
                model_config.available_tts_models = [
                    f"{model}-{spk}" for model, speakers in available_models.items() for spk in speakers
                ]
                model_config.tts_model_dict = available_models
                model_config.save()
                tts_logger("DEBUG", f"update available TTS models: {available_models}")
            return
        if result.find("tts"):
            tts_logger("INFO", f"\n{self.command.get_help()}")
            return
        return True

    @classmethod
    def supply_options(cls) -> Union[list[Option], None]:
        return
