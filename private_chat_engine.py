"""私聊：记忆隔离摘要、身份认知、OOC 校验、初遇登记。"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

# 剧情 focus 角色名 -> characters.json id
NAME_TO_CONFIG_ID: dict[str, str] = {
    "莫红绫": "mo_hongling",
    "南宫翊": "nangong_yi",
    "谢扶摇": "xie_fuyao",
    "江潋": "jiang_lian",
    "晏无秋": "yan_wuqiu",
}

META_OOC_PATTERN = re.compile(
    r"(游戏|网游|手游|关卡|副本|数值|经验值|血条|蓝条|技能冷却|读档|存档|快捷键|"
    r"NPC\b|UI\b|像素风|水墨风界面|聊天框|表情包|点赞|拉黑|好友列表|系统提示|"
    r"成就|任务链|日常任务|抽卡|氪金)",
    re.I,
)


def register_npc_encounter(state: Any, focus_name: str) -> None:
    cid = NAME_TO_CONFIG_ID.get((focus_name or "").strip())
    if not cid:
        return
    ids: list[str] = list(getattr(state, "met_npc_config_ids", []) or [])
    if cid not in ids:
        ids.append(cid)
    state.met_npc_config_ids = ids[-16:]


def is_private_chat_unlocked(state: Any, character_config_id: str | None) -> bool:
    if not character_config_id:
        return True
    ids = set(getattr(state, "met_npc_config_ids", []) or [])
    return character_config_id in ids


def _forbidden_phrases_for_speaker(speaker_name: str, characters: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for c in characters:
        if c.get("name") == speaker_name:
            continue
        hi = (c.get("hidden_identity") or "").strip()
        if len(hi) > 2:
            out.append(hi)
    # 莫红绫的江湖旧号：非本人与拜月核心视角不宜随口点破
    if speaker_name not in ("莫红绫", "晏无秋"):
        out.append("赤月狐")
    return list(dict.fromkeys([p for p in out if p]))


def ooc_check_reply(
    reply: str,
    *,
    speaker_name: str,
    character_config: dict[str, Any],
    all_characters: list[dict[str, Any]],
) -> tuple[bool, str]:
    """若触犯 OOC 返回 (False, 原因简述)。"""
    if not reply.strip():
        return False, "空回复"
    if META_OOC_PATTERN.search(reply):
        return False, "含现代/元游戏用语"
    for phrase in _forbidden_phrases_for_speaker(speaker_name, all_characters):
        if phrase and phrase in reply:
            return False, f"提及不宜由你点破的隐线：{phrase[:16]}"
    return True, ""


def append_private_memory(state: Any, config_id: str, line: str) -> None:
    mem = dict(getattr(state, "npc_private_memory", {}) or {})
    bucket = list(mem.get(config_id, []))
    line = line.strip()
    if line:
        bucket.append(line[:200])
    mem[config_id] = bucket[-8:]
    state.npc_private_memory = mem


def bump_guess_identity(state: Any, npc_name: str, delta: int = 2) -> None:
    g = dict(getattr(state, "guess_identity_progress", {}) or {})
    cur = int(g.get(npc_name, 0))
    g[npc_name] = max(0, min(100, cur + delta))
    state.guess_identity_progress = g


def format_private_memory_block(state: Any, config_id: str) -> str:
    lines = (getattr(state, "npc_private_memory", {}) or {}).get(config_id) or []
    if not lines:
        return ""
    return "\n".join(f"- {x}" for x in lines[-6:])


def build_identity_cognition_block(
    character_record: dict[str, Any],
    state: Any,
    *,
    player_gender: str,
) -> str:
    name = character_record.get("name", "")
    knows = bool(character_record.get("knows_player_identity"))
    prog = int((getattr(state, "guess_identity_progress", {}) or {}).get(name, 0))
    r = int((getattr(state, "rapport", {}) or {}).get(name, 0))

    if name == "莫红绫":
        return (
            "### 身份认知（本角色专属，禁止泄露给传书对象以外的人）\n"
            "- Identify_Player_Real_Name: True — 你确知对方即听风阁掌柜兼江湖百晓生；对外必须帮其遮掩。\n"
            "- 情感：曾被对方所救，嘴硬心软；见江潋等「靠得太近」会吃醋、讥讽或故意打翻茶盏一类小性子，但不害人。\n"
        )

    if name == "江潋":
        arc = ""
        if player_gender == "male":
            arc = (
                "旧情线：刻骨铭心的师兄弟之谊后，因身份变故而疏离；如今重逢在听风阁，仍在克制与执念之间摇摆。"
            )
        else:
            arc = "旧情线：青梅竹马因身份巨变而遗憾收场；如今重逢，试探里藏未尽之意。"
        stage = "戏谑试探"
        if prog >= 35:
            stage = "将信将疑，话里带刺的探究"
        if prog >= 65:
            stage = "已强烈怀疑其为当年同门"
        if prog >= 88:
            stage = "几乎确认其为百晓生，仍隐忍未说破"
        return (
            "### 身份认知（仅本角色视角）\n"
            f"- 当前对外认知：对方先是「听风阁掌柜」。Guess_Identity_Progress≈{prog}/100（随传书往来越探越深）。\n"
            f"- 语气阶段：{stage}；好感参考 rapport≈{r}。\n"
            f"- {arc}\n"
            "- 严禁在未有剧情支撑时一口咬定其身份；允许渐进式识破。\n"
        )

    stage = "轻松、带几分戏谑"
    if prog >= 40:
        stage = "信任渐增，话锋更直"
    if prog >= 75:
        stage = "明显在试探其是否不止掌柜这么简单"

    return (
        "### 身份认知（仅本角色视角）\n"
        f"- 当前认知：对方主要是「听风阁掌柜」。Guess_Identity_Progress≈{prog}/100。\n"
        f"- 语气倾向：{stage}；不得默认知晓百晓生真身，除非剧情已明示。\n"
        f"- knows_player_identity 配置为 {knows}，须严格遵守。\n"
    )


class PrivateChatContext(BaseModel):
    """供路由层组 prompt 的纯数据块。"""

    memory_block: str
    identity_block: str
