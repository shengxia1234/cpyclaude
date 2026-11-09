import os

from dataclasses import dataclass, field
from dotenv import load_dotenv


_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 7437
_DEFAULT_LOG_LEVEL = "INFO"
_DEFAULT_LOG_FILE = "~/.cpyClaude/logs/core.log"
_DEFAULT_LOG_FORMAT = "text"
_DEFAULT_CONFIG_PATH = "~/.cpyClaude/config.toml"
_DEFAULT_MODEL = "..."
_DEFAULT_MAX_STEPS = 20
_DEFAULT_API = "anthropic"

@dataclass
class LoggingConfig:
    level : str = _DEFAULT_LOG_LEVEL
    file : str = _DEFAULT_LOG_FILE
    format : str = _DEFAULT_LOG_FORMAT

@dataclass
class LLMConfig:
    max_steps : int = _DEFAULT_MAX_STEPS
    model : str = _DEFAULT_MODEL
    which_api = _DEFAULT_API

@dataclass
class config:
    host : str = _DEFAULT_HOST
    port : int = _DEFAULT_PORT
    logging : LoggingConfig = field(default_factory=LoggingConfig)
    LLM : LLMConfig = field(default_factory=LLMConfig)

# 构建并返回运行时配置：默认值 → .env
def get_config() -> config:
    cf = config()
    load_dotenv("/home/chenxuexi/cpyClaude/.env",override=False)

    # 暂时不加载config.toml
    # config_path = ...
    # if config_path.exists():
    #     ...
    
    _apply_env(cf)
    return cf

# 加载.env
def _apply_env(cf : config):
    host = os.getenv("CPY_CLAUDE_HOST")
    if host is not None:
        cf.host = host

    port_str = os.getenv("CPY_CLAUDE_PORT")
    if port_str is not None:
        try:
            port = int(port_str)
        except ValueError:
            raise SystemError(f"Config error: PORT must be an integer, got: {port_str!r}")
        cf.port = port

    which_api = os.getenv("WHICH_API")
    if which_api is not None:
        cf.LLM.which_api = which_api

    logging_level = os.getenv("CPY_CLAUDE_LOG_LEVEL")
    if logging_level is not None:
        cf.logging.level = logging_level

    logging_file = os.getenv("CPY_CLAUDE_LOG_FILE")
    if logging_file is not None:
        cf.logging.file = logging_file

    logging_format = os.getenv("CPY_CLAUDE_LOG_FORMAT")
    if logging_format is not None:
        cf.logging.format = logging_format

    if cf.LLM.which_api == "anthropic":
        default_model = os.getenv("ANTHROPIC_LLM_DEFAULT_MODEL")
        if default_model is not None:
            cf.LLM.model = default_model

        LLM_max_steps = os.getenv("ANTHROPIC_LLM_MAX_STEPS")
        if LLM_max_steps is not None:
            try:
                val = int(LLM_max_steps)
                if val < 0:
                    raise SystemExit("ANTHROPIC_LLM_MAX_STEPS must be a postive Interger!")
                cf.LLM.max_steps = val
            except ValueError:
                raise SystemExit(
                    f"Config error: ANTHROPIC_LLM_MAX_STEPS must be an integer, got: {LLM_max_steps!r}"
                )
    elif cf.LLM.which_api == "openai":
        default_model = os.getenv("OPENAI_LLM_DEFAULT_MODEL")
        if default_model is not None:
            cf.LLM.model = default_model

        LLM_max_steps = os.getenv("OPENAI_LLM_MAX_STEPS")
        if LLM_max_steps is not None:
            try:
                val = int(LLM_max_steps)
                if val < 0:
                    raise SystemExit("OPENAI_LLM_MAX_STEPS must be a postive Interger!")
                cf.LLM.max_steps = val
            except ValueError:
                raise SystemExit(
                    f"Config error: OPENAI_LLM_MAX_STEPS must be an integer, got: {LLM_max_steps!r}"
                )       