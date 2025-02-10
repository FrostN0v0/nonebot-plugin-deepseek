from importlib.util import find_spec

from nonebot import require
from nonebot.params import Depends
from nonebot.permission import SuperUser
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_waiter")
require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
from arclet.alconna import config as alc_config
from nonebot_plugin_alconna.builtins.extensions.reply import ReplyMergeExtension
from nonebot_plugin_alconna import (
    Args,
    Field,
    Match,
    Query,
    Option,
    Alconna,
    MultiVar,
    Namespace,
    Subcommand,
    CommandMeta,
    on_alconna,
)

from .config import Config
from .config import model_config
from .config import config as plugin_config

if plugin_config.enable_tts:
    from .config import preset_tts_list
else:
    preset_tts_list = []

if find_spec("nonebot_plugin_htmlrender") and plugin_config.md_to_pic:
    require("nonebot_plugin_htmlrender")
    from nonebot_plugin_htmlrender import md_to_pic as md_to_pic

    is_to_pic = True
else:
    is_to_pic = False

from .apis import API
from . import hook as hook
from .utils import DeepSeekHandler
from .exception import RequestException
from .extension import ParseExtension, CleanDocExtension

__plugin_meta__ = PluginMetadata(
    name="DeepSeek",
    description="接入 DeepSeek 模型，提供智能对话与问答功能",
    usage="/deepseek -h",
    type="application",
    config=Config,
    homepage="https://github.com/KomoriDev/nonebot-plugin-deepseek",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "unique_name": "DeepSeek",
        "author": "Komorebi <mute231010@gmail.com>",
        "version": "0.1.7",
    },
)


ns = Namespace("deepseek", disable_builtin_options=set())
alc_config.namespaces["deepseek"] = ns

deepseek = on_alconna(
    Alconna(
        "deepseek",
        Args["content?#内容", MultiVar("str")],
        Option(
            "--use-model",
            Args[
                "model#模型名称",
                plugin_config.get_enable_models(),
                Field(completion=lambda: f"请输入模型名，预期为：{plugin_config.get_enable_models()} 其中之一"),
            ],
            help_text="指定模型",
        ),
        Option("--use-tts", help_text="使用TTS回复"),
        Option("--with-context", help_text="启用多轮对话"),
        Subcommand("--balance", help_text="查看余额"),
        Subcommand(
            "model",
            Option("-l|--list", help_text="支持的模型列表"),
            Option(
                "--set-default",
                Args[
                    "model#模型名称",
                    plugin_config.get_enable_models(),
                    Field(completion=lambda: f"请输入模型名，预期为：{plugin_config.get_enable_models()} 其中之一"),
                ],
                dest="set",
                help_text="设置默认模型",
            ),
            help_text="模型相关设置",
        ),
        Subcommand(
            "tts",
            Option("-l|--list", help_text="支持的TTS模型列表"),
            Option(
                "--set-default",
                Args[
                    "model#模型名称",
                    preset_tts_list,
                    Field(
                        completion=lambda: f"请输入TTS模型预设名，预期为：{preset_tts_list[:10]}…… 其中之一\n"
                        "输入 `/deepseek tts -l` 查看所有TTS模型及角色"
                    ),
                ],
                dest="set",
                help_text="设置默认TTS模型",
            ),
            help_text="TTS模型相关设置",
        ),
        namespace=alc_config.namespaces["deepseek"],
        meta=CommandMeta(
            description=__plugin_meta__.description,
            usage=__plugin_meta__.usage,
        ),
    ),
    aliases={"ds"},
    use_cmd_start=True,
    skip_for_unmatch=False,
    comp_config={"lite": True},
    extensions=[ReplyMergeExtension, CleanDocExtension, ParseExtension],
)

deepseek.shortcut("多轮对话", {"command": "deepseek --with-context", "fuzzy": True, "prefix": True})
deepseek.shortcut("多轮语音对话", {"command": "deepseek --use-tts --with-context", "fuzzy": True, "prefix": True})
deepseek.shortcut("深度思考", {"command": "deepseek --use-model deepseek-reasoner", "fuzzy": True, "prefix": True})
deepseek.shortcut("余额", {"command": "deepseek --balance", "fuzzy": False, "prefix": True})
deepseek.shortcut("模型列表", {"command": "deepseek model --list", "fuzzy": False, "prefix": True})
deepseek.shortcut("设置默认模型", {"command": "deepseek model --set-default", "fuzzy": True, "prefix": True})
deepseek.shortcut("TTS模型列表", {"command": "deepseek tts --list", "fuzzy": False, "prefix": True})
deepseek.shortcut("设置默认TTS模型", {"command": "deepseek tts --set-default", "fuzzy": True, "prefix": True})


@deepseek.assign("balance")
async def _(is_superuser: bool = Depends(SuperUser())):
    if not is_superuser:
        await deepseek.finish("该指令仅超管可用")
    try:
        balances = await API.query_balance(model_config.default_model)

        await deepseek.finish(
            "".join(
                f"""
                货币：{balance.currency}
                总的可用余额: {balance.total_balance}
                未过期的赠金余额: {balance.granted_balance}
                充值余额: {balance.topped_up_balance}
                """
                for balance in balances.balance_infos
            )
        )
    except ValueError as e:
        await deepseek.finish(str(e))
    except RequestException as e:
        await deepseek.finish(str(e))


@deepseek.assign("model.list")
async def _():
    model_list = "\n".join(
        f"- {model}（默认）" if model == model_config.default_model else f"- {model}"
        for model in plugin_config.get_enable_models()
    )
    message = (
        f"支持的模型列表: \n{model_list}\n"
        "输入 `/deepseek [内容] --use-model [模型名]` 单次选择模型\n"
        "输入 `/deepseek model --set-default [模型名]` 设置默认模型"
    )
    await deepseek.finish(message)


@deepseek.assign("model.set")
async def _(
    is_superuser: bool = Depends(SuperUser()),
    model: Query[str] = Query("model.set.model"),
):
    if not is_superuser:
        await deepseek.finish("该指令仅超管可用")
    model_config.default_model = model.result
    model_config.save()
    await deepseek.finish(f"已设置默认模型为：{model.result}")


@deepseek.assign("tts.list")
async def _():
    model_list = ""
    spks_list = ""
    if not plugin_config.enable_tts:
        await deepseek.finish("当前未启用TTS功能")
    for model in await API.get_tts_models():
        default_model = await plugin_config.get_tts_model(model_config.default_tts_model)
        spks_list = "|".join(
            f"{spk}(默认)" if default_model.name == f"{model}-{spk}" else f"{spk}"
            for spk in await API.get_tts_speakers(model)
        )
        model_list += f"{model}\n - {spks_list}\n"
    custom_models = "\n".join(
        f"- {model}（默认）" if model == model_config.default_tts_model else f"- {model}"
        for model in plugin_config.get_enable_tts()
    )
    message = f"支持的TTS模型列表: \n{model_list}\n自定义预设:\n{custom_models}"
    await deepseek.finish(message)


@deepseek.assign("tts.set")
async def _(
    is_superuser: bool = Depends(SuperUser()),
    model: Query[str] = Query("tts.set.model"),
):
    if not plugin_config.enable_tts:
        await deepseek.finish("当前未启用TTS功能")
    if not is_superuser:
        await deepseek.finish("该指令仅超管可用")
    model_config.default_tts_model = model.result
    model_config.save()
    await deepseek.finish(f"已设置默认TTS模型为：{model.result}")


@deepseek.handle()
async def _(
    content: Match[tuple[str, ...]],
    model_name: Query[str] = Query("use-model.model"),
    use_tts: Query[bool] = Query("use-tts.value"),
    context_option: Query[bool] = Query("with-context.value"),
) -> None:
    tts_model = None
    if not model_name.available:
        model_name.result = model_config.default_model
    if use_tts.available and plugin_config.enable_tts:
        tts_model = await plugin_config.get_tts_model(model_config.default_tts_model)

    model = plugin_config.get_model_config(model_name.result)
    await DeepSeekHandler(
        model=model,
        is_to_pic=is_to_pic,
        is_contextual=context_option.available,
        tts_model=tts_model if use_tts.available and plugin_config.enable_tts else None,
    ).handle(" ".join(content.result) if content.available else None)
