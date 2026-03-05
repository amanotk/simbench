from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


def _clean_stream_text(text: str, *, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)] + "..."


def _collect_stream_text_fragments(
    value: Any, out: list[str], *, depth: int = 0, max_depth: int = 5
) -> None:
    if depth > max_depth:
        return
    if isinstance(value, str):
        cleaned = _clean_stream_text(value)
        if cleaned:
            out.append(cleaned)
        return
    if isinstance(value, list):
        for item in value[:8]:
            _collect_stream_text_fragments(item, out, depth=depth + 1)
        return
    if isinstance(value, dict):
        for key in (
            "text",
            "delta",
            "thinking",
            "reasoning",
            "message",
            "content",
            "parts",
            "chunk",
            "payload",
            "summary",
            "title",
        ):
            if key in value:
                _collect_stream_text_fragments(value[key], out, depth=depth + 1)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


_STREAM_LIFECYCLE_TYPES = {
    "message_start",
    "message_stop",
    "content_block_start",
    "content_block_stop",
    "response.created",
    "response.completed",
    "response.output_item.added",
    "response.output_item.done",
    "response.content_part.added",
    "response.content_part.done",
}


@dataclass
class _StreamPrettyState:
    agent_name: str
    claude_thinking_buf: str = ""
    claude_text_buf: str = ""


def _markdown_to_plain(text: str) -> str:
    return text.replace("**", "").strip()


def _summarize_tool_input(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    for key in ("command", "cmd", "shell_command", "file_path", "path", "url"):
        val = value.get(key)
        if isinstance(val, str) and val.strip():
            return _clean_stream_text(val)
    return ""


def _flush_claude_buffers(phase: str, state: _StreamPrettyState) -> str | None:
    thinking = _clean_stream_text(state.claude_thinking_buf)
    text = _clean_stream_text(state.claude_text_buf)
    state.claude_thinking_buf = ""
    state.claude_text_buf = ""

    if thinking and text:
        return f"[{phase}] thinking: {thinking} | text: {text}"
    if thinking:
        return f"[{phase}] thinking: {thinking}"
    if text:
        return f"[{phase}] text: {text}"
    return None


def flush_stream_state(phase: str, state: _StreamPrettyState) -> str | None:
    if state.agent_name == "claude":
        return _flush_claude_buffers(phase, state)
    return None


def _append_claude_delta(
    *,
    phase: str,
    state: _StreamPrettyState,
    kind: str,
    piece: str,
) -> str | None:
    if not piece:
        return None

    attr = "claude_thinking_buf" if kind == "thinking" else "claude_text_buf"
    buf = getattr(state, attr) + piece
    setattr(state, attr, buf)

    flush_now = False
    if "\n" in piece:
        flush_now = True
    if piece.strip().endswith((".", "!", "?")):
        flush_now = True
    if len(buf) >= 120:
        flush_now = True

    if not flush_now:
        return None

    msg = _clean_stream_text(buf)
    setattr(state, attr, "")
    if not msg:
        return None
    return f"[{phase}] {kind}: {msg}"


def _phase_agent_name(phase: str) -> str:
    if not phase.startswith("agent:"):
        return ""
    rest = phase.split(":", 1)[1]
    return rest.split(":", 1)[0].strip().lower()


def _extract_stream_text_parts(obj: dict[str, Any]) -> list[str]:
    fragments: list[str] = []
    for key in (
        "text",
        "delta",
        "thinking",
        "reasoning",
        "message",
        "content",
        "data",
        "summary",
        "title",
    ):
        if key in obj:
            _collect_stream_text_fragments(obj[key], fragments)
    return _dedupe_preserve_order(fragments)


def _extract_stream_status(obj: dict[str, Any]) -> str:
    for key in ("status", "state", "phase"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _extract_stream_tool_name(obj: dict[str, Any]) -> str:
    for key in ("tool_name", "function_name", "name"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    tool_obj = obj.get("tool")
    if isinstance(tool_obj, dict):
        nm = tool_obj.get("name")
        if isinstance(nm, str) and nm.strip():
            return nm.strip()
    return ""


def _extract_stream_command(obj: dict[str, Any]) -> str:
    for key in ("command", "cmd", "shell_command"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, list):
            parts = [str(x) for x in val if isinstance(x, (str, int, float))]
            if parts:
                return " ".join(parts)
    return ""


def _render_stream_event_generic(
    phase: str,
    obj: dict[str, Any],
    *,
    event_type: str,
    low_type: str,
    text_parts: list[str],
) -> tuple[str | None, bool]:
    kind = "event"
    if any(k in obj for k in ("thinking", "reasoning", "analysis")) or any(
        tok in low_type for tok in ("thinking", "reason", "analysis")
    ):
        kind = "thinking"
    elif any(tok in low_type for tok in ("tool", "function", "command", "call")) or any(
        k in obj for k in ("tool", "tool_name", "function", "function_name", "command")
    ):
        kind = "tool"
    elif any(tok in low_type for tok in ("error", "fail", "exception")):
        kind = "error"
    elif any(
        tok in low_type for tok in ("text", "message", "output", "content", "delta")
    ):
        kind = "text"

    status = _extract_stream_status(obj)
    msg = ""
    if kind == "tool":
        tool_name = _extract_stream_tool_name(obj)
        command = _extract_stream_command(obj)
        msg = command or tool_name
        if msg and status:
            msg += f" ({status})"

    if not msg and text_parts:
        msg = " | ".join(text_parts[:2])
    msg = _clean_stream_text(msg)

    if not msg:
        if "delta" in low_type:
            return None, True
        if low_type in _STREAM_LIFECYCLE_TYPES:
            return None, True
        if event_type:
            return None, False
        return None, False

    return f"[{phase}] {kind}: {msg}", True


def _render_stream_event_codex(
    phase: str,
    obj: dict[str, Any],
    *,
    event_type: str,
    low_type: str,
    text_parts: list[str],
) -> tuple[str | None, bool]:
    if low_type in _STREAM_LIFECYCLE_TYPES:
        return None, True

    if any(tok in low_type for tok in ("reason", "thinking", "analysis", "plan")):
        if text_parts:
            return f"[{phase}] plan: {text_parts[0]}", True
        return None, True

    command = _extract_stream_command(obj)
    if command or any(
        tok in low_type
        for tok in ("tool", "function", "command", "exec", "shell", "bash")
    ):
        msg = command or _extract_stream_tool_name(obj)
        msg = _clean_stream_text(msg)
        if msg:
            status = _extract_stream_status(obj)
            if status:
                msg += f" ({status})"
            return f"[{phase}] tool: {msg}", True
        return None, True

    if any(
        tok in low_type for tok in ("patch", "diff", "edit", "apply", "write", "file")
    ):
        target = ""
        for key in ("path", "file", "filename", "target"):
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                target = val.strip()
                break
        if not target and text_parts:
            target = text_parts[0]
        target = _clean_stream_text(target)
        if target:
            return f"[{phase}] patch: {target}", True
        return None, False

    if any(tok in low_type for tok in ("error", "fail", "exception")):
        msg = text_parts[0] if text_parts else _extract_stream_status(obj)
        msg = _clean_stream_text(msg)
        if msg:
            return f"[{phase}] error: {msg}", True
        return None, False

    if text_parts:
        return f"[{phase}] text: {' | '.join(text_parts[:2])}", True
    if event_type:
        return None, False
    return None, False


def _render_stream_event_copilot(
    phase: str,
    obj: dict[str, Any],
    *,
    event_type: str,
    low_type: str,
    text_parts: list[str],
) -> tuple[str | None, bool]:
    if low_type in _STREAM_LIFECYCLE_TYPES:
        return None, True

    if any(tok in low_type for tok in ("permission", "approval", "allow", "deny")):
        tool = _extract_stream_tool_name(obj) or _extract_stream_command(obj)
        status = _extract_stream_status(obj)
        msg = _clean_stream_text(tool)
        if status:
            msg = f"{msg} ({status})" if msg else status
        if not msg and text_parts:
            msg = text_parts[0]
        msg = _clean_stream_text(msg)
        if msg:
            return f"[{phase}] permission: {msg}", True
        return None, True

    command = _extract_stream_command(obj)
    if command or any(
        tok in low_type for tok in ("tool", "function", "command", "exec", "shell")
    ):
        msg = _clean_stream_text(command or _extract_stream_tool_name(obj))
        if msg:
            status = _extract_stream_status(obj)
            if status:
                msg += f" ({status})"
            return f"[{phase}] tool: {msg}", True
        return None, True

    if any(tok in low_type for tok in ("progress", "status", "step")):
        msg = text_parts[0] if text_parts else _extract_stream_status(obj)
        step = obj.get("step")
        if isinstance(step, (int, float)):
            step_s = str(
                int(step) if isinstance(step, float) and step.is_integer() else step
            )
            msg = f"step {step_s}: {msg}" if msg else f"step {step_s}"
        msg = _clean_stream_text(msg)
        if msg:
            return f"[{phase}] status: {msg}", True
        return None, False

    if any(tok in low_type for tok in ("thinking", "reason", "analysis", "plan")):
        if text_parts:
            return f"[{phase}] thinking: {text_parts[0]}", True
        return None, True

    if any(tok in low_type for tok in ("error", "fail", "exception")):
        msg = text_parts[0] if text_parts else _extract_stream_status(obj)
        msg = _clean_stream_text(msg)
        if msg:
            return f"[{phase}] error: {msg}", True
        return None, False

    if text_parts:
        return f"[{phase}] text: {' | '.join(text_parts[:2])}", True
    if event_type:
        return None, False
    return None, False


def _format_claude_stream_event(
    phase: str,
    obj: dict[str, Any],
    *,
    state: _StreamPrettyState,
) -> tuple[bool, str | None, bool]:
    top_type = str(obj.get("type", "")).strip().lower()

    if top_type == "system":
        return True, None, True

    if top_type == "stream_event" and isinstance(obj.get("event"), dict):
        event = obj["event"]
        event_type = str(event.get("type", "")).strip().lower()

        if event_type == "content_block_start":
            block = event.get("content_block")
            if isinstance(block, dict):
                block_type = str(block.get("type", "")).strip().lower()
                if block_type == "tool_use":
                    name = str(block.get("name", "")).strip()
                    if name:
                        return True, f"[{phase}] tool: {name} (start)", True
            return True, None, True

        if event_type in _STREAM_LIFECYCLE_TYPES:
            flushed = _flush_claude_buffers(phase, state)
            return True, flushed, True

        if event_type == "content_block_delta":
            delta = event.get("delta")
            if isinstance(delta, dict):
                delta_type = str(delta.get("type", "")).strip().lower()
                if delta_type == "thinking_delta":
                    piece = str(delta.get("thinking", ""))
                    line = _append_claude_delta(
                        phase=phase, state=state, kind="thinking", piece=piece
                    )
                    return True, line, True
                if delta_type == "text_delta":
                    piece = str(delta.get("text", ""))
                    line = _append_claude_delta(
                        phase=phase, state=state, kind="text", piece=piece
                    )
                    return True, line, True
                if delta_type == "input_json_delta":
                    return True, None, True
            return True, None, False

        if event_type == "message_delta":
            return True, None, True

        return True, None, False

    if top_type == "assistant" and isinstance(obj.get("message"), dict):
        msg = obj["message"]
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = str(block.get("type", "")).strip().lower()
                if block_type == "tool_use":
                    name = str(block.get("name", "")).strip()
                    summary = _summarize_tool_input(block.get("input"))
                    if name and summary:
                        return True, f"[{phase}] tool: {name} {summary}", True
                    if name:
                        return True, f"[{phase}] tool: {name}", True
                if block_type == "thinking":
                    text = _markdown_to_plain(str(block.get("thinking", "")))
                    text = _clean_stream_text(text)
                    if text:
                        return True, f"[{phase}] thinking: {text}", True
                if block_type == "text":
                    text = _clean_stream_text(str(block.get("text", "")))
                    if text:
                        return True, f"[{phase}] text: {text}", True
        return True, None, True

    if top_type == "user":
        tool_result = obj.get("tool_use_result")
        if isinstance(tool_result, str) and "error" in tool_result.lower():
            msg = _clean_stream_text(tool_result)
            if msg:
                return True, f"[{phase}] error: {msg}", True
        return True, None, True

    return False, None, False


def _format_codex_stream_event(
    phase: str,
    obj: dict[str, Any],
) -> tuple[bool, str | None, bool]:
    top_type = str(obj.get("type", "")).strip().lower()
    if top_type in {"thread.started", "turn.started", "turn.completed"}:
        return True, None, True

    normalized = obj
    if top_type.startswith("item.") and isinstance(obj.get("item"), dict):
        item = obj["item"]
        item_type = str(item.get("type", "")).strip().lower()

        if item_type == "reasoning":
            normalized = {
                "type": "reasoning",
                "thinking": _markdown_to_plain(str(item.get("text", ""))),
            }
        elif item_type == "command_execution":
            normalized = {
                "type": "command_execution",
                "command": item.get("command", ""),
                "status": item.get("status", ""),
            }
            exit_code = item.get("exit_code")
            if isinstance(exit_code, int) and exit_code != 0:
                normalized["status"] = (
                    f"{normalized['status']} exit={exit_code}".strip()
                )
        elif item_type == "file_change":
            paths: list[str] = []
            changes = item.get("changes")
            if isinstance(changes, list):
                for change in changes:
                    if not isinstance(change, dict):
                        continue
                    path = change.get("path")
                    if isinstance(path, str) and path.strip():
                        paths.append(path.strip())
            label = ", ".join(paths[:3])
            if len(paths) > 3:
                label += ", ..."
            normalized = {
                "type": "file_change",
                "text": label or "file change",
            }
        elif item_type == "agent_message":
            normalized = {
                "type": "agent_message",
                "text": _markdown_to_plain(str(item.get("text", ""))),
            }
        else:
            normalized = item

    event_type = ""
    for key in ("type", "event", "kind"):
        val = normalized.get(key)
        if isinstance(val, str) and val.strip():
            event_type = val.strip()
            break
    low_type = event_type.lower()
    text_parts = _extract_stream_text_parts(normalized)
    rendered, suppress_raw = _render_stream_event_codex(
        phase,
        normalized,
        event_type=event_type,
        low_type=low_type,
        text_parts=text_parts,
    )
    return True, rendered, suppress_raw


def _format_agent_stream_event(
    phase: str,
    line: str,
    *,
    state: _StreamPrettyState,
) -> tuple[bool, str | None, bool]:
    stripped = line.strip()
    if not stripped or not stripped.startswith("{"):
        return False, None, False

    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return False, None, False

    if not isinstance(obj, dict):
        return False, None, False

    agent_name = state.agent_name
    if agent_name == "claude":
        parsed, rendered, suppress_raw = _format_claude_stream_event(
            phase,
            obj,
            state=state,
        )
        if parsed:
            return parsed, rendered, suppress_raw

    if agent_name == "codex":
        parsed, rendered, suppress_raw = _format_codex_stream_event(phase, obj)
        if parsed:
            return parsed, rendered, suppress_raw

    event_type = ""
    for key in ("type", "event", "kind"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            event_type = val.strip()
            break
    low_type = event_type.lower()
    text_parts = _extract_stream_text_parts(obj)

    if agent_name == "codex":
        rendered, suppress_raw = _render_stream_event_codex(
            phase,
            obj,
            event_type=event_type,
            low_type=low_type,
            text_parts=text_parts,
        )
    elif agent_name == "copilot":
        rendered, suppress_raw = _render_stream_event_copilot(
            phase,
            obj,
            event_type=event_type,
            low_type=low_type,
            text_parts=text_parts,
        )
    else:
        rendered, suppress_raw = _render_stream_event_generic(
            phase,
            obj,
            event_type=event_type,
            low_type=low_type,
            text_parts=text_parts,
        )

    return True, rendered, suppress_raw


def _format_agent_plain_stream_line(phase: str, line: str) -> tuple[bool, str | None]:
    agent_name = _phase_agent_name(phase)
    stripped = line.strip()
    if not stripped:
        return False, None

    low = stripped.lower()
    if agent_name == "copilot":
        if low.startswith(("thinking", "analyzing", "planning")):
            msg = stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
            msg = _clean_stream_text(msg)
            return True, f"[{phase}] thinking: {msg}"
        if low.startswith(("using tool", "tool:", "running ", "executing ")):
            msg = _clean_stream_text(stripped)
            return True, f"[{phase}] tool: {msg}"
        if low.startswith(("status", "progress", "step")):
            msg = stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
            msg = _clean_stream_text(msg)
            return True, f"[{phase}] status: {msg}"
        if low.startswith("error"):
            msg = stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
            msg = _clean_stream_text(msg)
            return True, f"[{phase}] error: {msg}"

    return False, None
