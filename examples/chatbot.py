"""命令行聊天机器人示例。

环境变量：

- ``OPENAI_API_KEY``：必填。
- ``OPENAI_BASE_URL``：可选，例如 ``https://api.openai.com/v1`` 或兼容网关地址。
- ``OPENAI_MODEL``：可选，默认 ``gpt-4o-mini``。
- ``OPENAI_SYSTEM_PROMPT``：可选，默认英文助手提示词。
"""
from py2cpp import *
from py2cpp.core.exceptions import EOFError, OSError, ValueError
from py2cpp.system.environ import environ
from py2cpp.web.openai import OpenAI, OpenAIError


_DEFAULT_MODEL: str = "gpt-4o-mini"
_DEFAULT_SYSTEM: str = "You are a helpful assistant."
_MAX_HISTORY_CHARS: int = 12000


def _trim_history(history: str) -> str:
  if len(history) <= _MAX_HISTORY_CHARS:
    return history
  return history[len(history) - _MAX_HISTORY_CHARS :]


def _build_system_prompt(system_prompt: str, history: str) -> str:
  if not history:
    return system_prompt
  if system_prompt:
    return f"{system_prompt}\n\nConversation so far:\n{history}"
  return f"Conversation so far:\n{history}"


def main() -> int:
  api_key: str = environ.get("OPENAI_API_KEY", "")
  base_url: str = environ.get("OPENAI_BASE_URL", "")
  model: str = environ.get("OPENAI_MODEL", _DEFAULT_MODEL)
  system_prompt: str = environ.get("OPENAI_SYSTEM_PROMPT", _DEFAULT_SYSTEM)

  if not api_key:
    print("missing env: OPENAI_API_KEY or DEEPSEEK_API_KEY")
    return 2
  if not base_url:
    print("missing env: OPENAI_BASE_URL")
    return 2

  client: OpenAI = new(api_key=api_key, base_url=base_url, timeout=120.0)
  history: str = ""

  print("Py2Cpp Chatbot")
  print(f"model: {model}")
  print("type exit / quit / :q to leave")
  print("")

  while True:
    user: str = ""
    try:
      user = input("you> ")
    except EOFError:
      print("")
      return 0

    if user in {"exit", "quit", ":q"}:
      return 0
    if not user:
      continue

    prompt: str = _build_system_prompt(system_prompt, history)
    answer: str = ""
    print("bot> ", end="", flush=True)
    try:
      for token in client.chat_stream(model, user, system=prompt, temperature=0.7):
        print(token, end="", flush=True)
        answer += token
    except OpenAIError:
      print("")
      if client.last_error:
        print(f"[error] {client.last_error}")
      else:
        print("[error] OpenAI request failed")
      continue
    except OSError:
      print("")
      print("[error] network/TLS request failed; check OPENAI_BASE_URL and proxy")
      continue
    except ValueError:
      print("")
      print("[error] request setup/network failed; check OPENAI_BASE_URL")
      continue
    print("")

    history += f"User: {user}\nAssistant: {answer}\n"
    history = _trim_history(history)


if __name__ == "__main__":
  raise SystemExit(main())
