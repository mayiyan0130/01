import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
CONFIG_DIR = BASE_DIR / "config"
PROMPTS_DIR = BASE_DIR / "prompts"
CHARACTER_CONFIG_PATH = CONFIG_DIR / "characters.json"
STORY_SYSTEM_PROMPT_PATH = PROMPTS_DIR / "story_system_prompt.md"

load_dotenv(BASE_DIR / ".env")

AI_BASE_URL = os.getenv("AI_BASE_URL", "https://epone.ggb.today").rstrip("/")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
REQUEST_TIMEOUT = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))
CHAT_REPLY_TIMEOUT = float(os.getenv("AI_CHAT_TIMEOUT_SECONDS", "45"))
APP_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")

from game_secrets import (
    PlayerSecret,
    SecretContentGenerator,
    SecretType,
    append_definition_secrets,
    apply_intel_ledger_to_state,
    filter_valid_secrets,
    materialize_roster_for_secrets,
    migrate_legacy_player_intel_items,
    remove_secret_by_id,
    sale_summary_for_ai,
)
from private_chat_engine import (
    append_private_memory,
    build_identity_cognition_block,
    bump_guess_identity,
    format_private_memory_block,
    is_private_chat_unlocked,
    ooc_check_reply,
    register_npc_encounter,
)

INTENT_LABELS = {
    "steady": "稳住场面",
    "probe": "追问线索",
    "conceal": "隐藏身份",
    "trade": "做情报交易",
    "charm": "打动对方",
    "observe": "静观细节",
    "press": "强压试探",
    "deflect": "转移话题",
}


def load_story_system_prompt() -> str:
    return STORY_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def load_character_config() -> dict[str, Any]:
    payload = json.loads(CHARACTER_CONFIG_PATH.read_text(encoding="utf-8"))
    characters = payload.get("characters")
    if not isinstance(characters, list) or not characters:
        raise ValueError("Character config must contain a non-empty characters list.")
    return payload


def join_text(values: Any, separator: str = "、") -> str:
    if isinstance(values, list):
        return separator.join(str(value) for value in values if value)
    if values is None:
        return ""
    return str(values)


def format_character_cards(character_config: dict[str, Any]) -> str:
    sections: list[str] = []
    for character in character_config["characters"]:
        hidden_identity = character.get("hidden_identity") or "无"
        sections.append(
            "\n".join(
                [
                    f"【{character['name']}】",
                    f"- 明面身份：{character['public_identity']}",
                    f"- 暗线身份：{hidden_identity}",
                    f"- 阵营：{character['faction']}",
                    f"- 是否知晓玩家真实身份：{'知晓' if character.get('knows_player_identity') else '不知晓'}",
                    f"- 攻略定位：{character.get('core_route', '')}",
                    f"- 关系关键词：{join_text(character.get('relationship_keywords'))}",
                    f"- 核心性格：{join_text(character.get('core_traits'))}",
                    f"- 说话风格：{join_text(character.get('speech_style'), '；')}",
                    f"- 互动目标：{join_text(character.get('interaction_goals'), '；')}",
                    f"- 表现禁区：{join_text(character.get('taboos'), '；')}",
                    f"- 扮演指令：{join_text(character.get('prompt_directives'), '；')}",
                ]
            )
        )
        gl = join_text(character.get("gift_loved"))
        gk = join_text(character.get("gift_liked"))
        if gl or gk:
            sections[-1] += "\n" + "\n".join(
                [
                    f"- 心仪赠礼（传书相赠易动容）：{gl or '无'}",
                    f"- 尚可的赠礼：{gk or '无'}",
                ]
            )
    return "\n\n".join(sections)


def get_character_by_config_id(character_config: dict[str, Any], config_id: str) -> dict[str, Any] | None:
    for character in character_config.get("characters", []):
        if character.get("id") == config_id:
            return character
    return None


def format_focus_character_playbook(character_config: dict[str, Any], focus_name: str) -> str:
    for character in character_config["characters"]:
        if character.get("name") != focus_name:
            continue
        hidden_identity = character.get("hidden_identity") or "无"
        return "\n".join(
            [
                f"本场 narrative 与 dialogue 应让「{focus_name}」的立场与存在感落地，并严格执行其人设：",
                f"- 明面身份：{character['public_identity']}；暗线：{hidden_identity}",
                f"- 核心性格：{join_text(character.get('core_traits'))}",
                f"- 说话风格（句式/语气）：{join_text(character.get('speech_style'), '；')}",
                f"- 扮演指令（必须落实）：{join_text(character.get('prompt_directives'), '；')}",
                f"- 表现禁区（严禁）：{join_text(character.get('taboos'), '；')}",
                f"- 互动目标（潜台词方向）：{join_text(character.get('interaction_goals'), '；')}",
            ]
        )
    return (
        f"本场 focus_npc 为「{focus_name}」，但角色配置表中无同名条目：请按当前场面与身份合理推断，"
        "仍须避免与其他已配置角色人设混淆。"
    )


# 小游戏前至少经历若干次「抉择推进」（与玩家点击选项次数同步）
MIN_CHOICE_BEATS_BETWEEN_MINIGAMES = 6
# 禁止同一类小游戏（match3/snake）在缓冲不足时立刻再开
MIN_BEATS_BEFORE_REPEAT_SAME_MINIGAME = 8
DIALOGUE_MAX_LINES = 5
MAIN_CAST = ("莫红绫", "南宫翊", "谢扶摇", "江潋", "晏无秋")
SECT_KEYS = ("华山", "武当", "峨嵋", "药王谷", "唐门", "拜月", "五毒")


def default_sect_influence() -> dict[str, int]:
    return {
        "华山": 34,
        "武当": 28,
        "峨嵋": 18,
        "药王谷": 20,
        "唐门": 16,
        "拜月": 28,
        "五毒": 12,
    }


def clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


class GameState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chapter_id: str = "chapter-01"
    chapter_step: int = 0
    silver: int = 120
    intel: int = 1
    exposure: int = 18
    tavern_heat: int = 42
    focus_npc: str = "莫红绫"
    rapport: dict[str, int] = Field(
        default_factory=lambda: {
            "莫红绫": 78,
            "南宫翊": 28,
            "谢扶摇": 18,
            "江潋": 36,
            "晏无秋": 14,
        }
    )
    previous_beats: list[str] = Field(default_factory=list)
    unlocked_tags: list[str] = Field(default_factory=lambda: ["武林大比将近", "听风阁夜局"])
    last_mini_game_type: str = "none"
    last_mini_game_success: bool = False
    last_mini_game_score: int = 0
    opening_merge_resolved: bool = False
    sects_notice_unlocked: bool = False
    # 小游戏结算后至少先走一轮「抉择推进」，避免连续弹出多个小游戏而没有剧情
    narrative_only_until_choice: bool = False
    # 自上次小游戏结算以来，玩家完成「抉择推进」的次数（用于稀疏触发下一个小游戏）
    choices_since_last_minigame: int = 0
    # 七大门派声势，供剧情与「售卖情报」玩法读写
    sect_influence: dict[str, int] = Field(default_factory=default_sect_influence)
    # 玩家向门派出售情报的摘要，供下一幕 AI 自然呼应
    intel_trade_log: list[str] = Field(default_factory=list)
    # 结构化秘辛（仅 merged_secret 会出现在道具 UI）
    player_secrets: list[PlayerSecret] = Field(default_factory=list)
    # 对白中归入「剧情日志」的条目，不进道具栏
    story_logs: list[str] = Field(default_factory=list)
    # 主线中已「照面」过的角色 configId，未照面则传书锁定
    met_npc_config_ids: list[str] = Field(default_factory=list)
    # 每 NPC 独立传书记忆摘要（仅该 NPC 的 prompt 可见）
    npc_private_memory: dict[str, list[str]] = Field(default_factory=dict)
    # 非莫红绫角色对掌柜真实身份的揣测进度 0–100
    guess_identity_progress: dict[str, int] = Field(default_factory=dict)
    # 二合小游戏产出的可赠礼物件（非秘辛）
    player_merge_gifts: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate_intel_schema(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        migrate_legacy_player_intel_items(data)
        if data.get("story_logs") is None:
            data["story_logs"] = []
        if data.get("player_secrets") is None:
            data["player_secrets"] = []
        return data

    @model_validator(mode="after")
    def normalize_sect_and_intel_log(self) -> "GameState":
        base = default_sect_influence()
        merged = {**base, **(self.sect_influence or {})}
        self.sect_influence = {
            k: clamp_int(int(merged.get(k, base[k])), 0, 100) for k in SECT_KEYS
        }
        if not self.intel_trade_log:
            self.intel_trade_log = []
        else:
            self.intel_trade_log = list(self.intel_trade_log)[-8:]
        slog = [str(x).strip() for x in (self.story_logs or []) if str(x).strip()]
        self.story_logs = list(dict.fromkeys(slog))[-40:]
        self.player_secrets = filter_valid_secrets(self.player_secrets)
        self.met_npc_config_ids = list(dict.fromkeys(str(x).strip() for x in self.met_npc_config_ids if str(x).strip()))[
            -16:
        ]
        gifts = [str(x).strip() for x in (self.player_merge_gifts or []) if str(x).strip()]
        self.player_merge_gifts = list(dict.fromkeys(gifts))[-24:]
        gid = dict(self.guess_identity_progress or {})
        for k, v in list(gid.items()):
            try:
                gid[str(k)] = max(0, min(100, int(v)))
            except (TypeError, ValueError):
                gid[str(k)] = 0
        self.guess_identity_progress = gid
        return self


def normalize_sect_input(raw: str) -> str:
    s = raw.strip()
    if "峨眉" in s and "峨嵋" not in s:
        s = s.replace("峨眉", "峨嵋")
    return s


def resolve_buyer_sect(raw: str) -> str:
    s = normalize_sect_input(raw)
    if not s:
        raise HTTPException(status_code=400, detail="buyer_sect 不能为空。")
    for key in SECT_KEYS:
        if s == key or key in s:
            return key
    raise HTTPException(
        status_code=400,
        detail="buyer_sect 须为七派之一：" + "、".join(SECT_KEYS),
    )


class PlayerChoice(BaseModel):
    id: str | None = None
    label: str | None = None
    intent: Literal["steady", "probe", "conceal", "trade", "charm", "observe", "press", "deflect"] = "steady"
    risk_hint: str | None = None


class StartRequest(BaseModel):
    player_name: str = "言笑笑"
    player_gender: Literal["female", "male"] = "female"


class AdvanceRequest(BaseModel):
    player_name: str = "言笑笑"
    player_gender: Literal["female", "male"] = "female"
    state: GameState
    choice: PlayerChoice | None = None
    player_input: str = ""


class MiniGameResult(BaseModel):
    type: Literal["match3", "merge", "snake"]
    success: bool
    score: int = 0
    summary: str = ""
    achieved_level: int = 0
    triggered_event: str = ""


class MiniGameRequest(BaseModel):
    player_name: str = "言笑笑"
    player_gender: Literal["female", "male"] = "female"
    state: GameState
    result: MiniGameResult


class ChapterResponse(BaseModel):
    scene_title: str
    scene_phase: str
    narration: str
    dialogue: list[dict[str, str]]
    choices: list[PlayerChoice]
    focus_npc: str
    mini_game: dict[str, str]
    state_commentary: str
    beat_summary: str
    updated_at: str
    turn_label: str
    location: str
    character_status: str
    turn_report: str
    state: GameState
    using_fallback: bool = False


class PrivateChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(default="", max_length=4000)


class PrivateReplyRequest(BaseModel):
    player_name: str = "言笑笑"
    player_gender: Literal["female", "male"] = "female"
    character_config_id: str | None = None
    custom_npc: dict[str, str] | None = None
    story_context: dict[str, str] = Field(default_factory=dict)
    history: list[PrivateChatTurn] = Field(default_factory=list)
    message: str = Field(..., min_length=1, max_length=400)
    state: GameState | None = None


class PrivateReplyResponse(BaseModel):
    reply: str
    using_fallback: bool = False
    state: GameState | None = None


class PrivateGiftRequest(BaseModel):
    player_name: str = "言笑笑"
    player_gender: Literal["female", "male"] = "female"
    state: GameState
    character_config_id: str = Field(..., min_length=2, max_length=40)
    gift_label: str = Field(..., min_length=1, max_length=40)


class PrivateGiftResponse(BaseModel):
    reply: str
    state: GameState
    rapport_delta: int


class SellIntelRequest(BaseModel):
    player_name: str = "言笑笑"
    state: GameState
    secret_id: str = Field(..., min_length=2, max_length=80)
    buyer_sect: str = Field(..., min_length=2, max_length=12)


class SecretDetailRequest(BaseModel):
    player_name: str = "言笑笑"
    state: GameState
    secret_id: str = Field(..., min_length=2, max_length=80)


class SecretDetailResponse(BaseModel):
    id: str
    title: str
    tier: int
    body: str
    secret_type: str
    state: GameState


class SellIntelResponse(BaseModel):
    buyer_sect: str
    verdict: str
    value_tier: str
    silver_delta: int
    buyer_influence_delta: int
    exposure_delta: int
    hook_story: str
    state: GameState
    using_fallback: bool = False


app = FastAPI(title="Jianghu Baixiaosheng Prototype", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def clamp(value: int, min_value: int = 0, max_value: int = 100) -> int:
    return max(min_value, min(max_value, value))


def current_timestamp() -> str:
    return datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M")


def build_turn_label(step: int) -> str:
    turn_no = max(step + 1, 1)
    start = datetime(2026, 5, 7, 17, 10, tzinfo=APP_TIMEZONE)
    scene_time = start + timedelta(minutes=(turn_no - 1) * 18)
    return f"第{turn_no}回合 · {scene_time.strftime('%H:%M')}"


def infer_location(state: GameState, scene_phase: str, mini_game_type: str) -> str:
    if not state.opening_merge_resolved or "整编" in scene_phase:
        return "听风阁后账房"
    if mini_game_type == "snake":
        return "听风阁外街口"
    if "入楼" in scene_phase or "夜局" in scene_phase or "前厅" in scene_phase:
        return "听风阁前厅"
    return "听风阁内堂"


def infer_character_status(state: GameState, focus_npc: str) -> str:
    pressure = "你表面还稳得住，心里却一直记着门口那些眼神。" if state.exposure >= 24 else "你还能把场面兜住，只是每句话都得掂量着说。"
    intel = "手里线索多了些，说话能更有底气。" if state.intel >= 4 else "手头线索还不算多，得边听边记。"
    focus = f"{focus_npc}就在近处帮你盯着动静。" if focus_npc else "众人的视线都还落在你身上。"
    return f"{pressure}{intel}{focus}"


def ensure_dialogue_quotes(dialogue: list[dict[str, Any]], player_name: str = "") -> list[dict[str, str]]:
    blocked_speakers = {value for value in (player_name.strip(), "你", "玩家", "主角", "掌柜") if value}
    normalized: list[dict[str, str]] = []
    for item in dialogue:
        speaker = str(item.get("speaker", "旁白")).strip() or "旁白"
        if speaker in blocked_speakers:
            continue
        text = str(item.get("text", "")).strip()
        if text and not text.startswith(("“", '"', "「", "『")):
            text = f"“{text}”"
        normalized.append(
            {
                "speaker": speaker,
                "text": text or "“……”",
                "mood": str(item.get("mood", "")).strip(),
            }
        )
    return normalized[:DIALOGUE_MAX_LINES]


def build_turn_report(beat_summary: str, action_summary: str) -> str:
    event_line = beat_summary.strip() or "这一回合里，场子里又多了一层试探。"
    action_line = action_summary.strip() or "你先稳住手边的事，再看下一步怎么接。"
    return f"*本回合事件：{event_line}*\n*主要行动：{action_line}*"


def summarize_action(choice: PlayerChoice | None, player_input: str) -> str:
    intent = choice.intent if choice else "steady"
    choice_label = choice.label or INTENT_LABELS[intent] if choice else INTENT_LABELS[intent]
    free_text = player_input.strip()
    if free_text:
        return f"玩家选择“{choice_label}”，并补充发言：{free_text}"
    return f"玩家选择“{choice_label}”。"


def build_scene_instruction(state: GameState) -> str:
    if state.narrative_only_until_choice:
        outcome = "得手" if state.last_mini_game_success else "未完全得手"
        return (
            f"上一局小游戏已结算（{outcome}）。本回合必须只写纯剧情推进，"
            "**dialogue 仍须 4～5 条**，且至少两名固定名单角色（莫红绫、南宫翊、谢扶摇、江潋、晏无秋）有实质性对白或交锋，"
            "让玩家在三个选项里做出抉择；不要在本回合里铺垫或暗示新的小游戏。"
            "若上局失败，须写出相应的代价或更棘手的局面，但剧情必须可延续，不得写成死局或终章。"
        )

    expected_mini_game = choose_mini_game(state)

    if not state.opening_merge_resolved:
        return (
            "当前必须写第一章开场。地点固定在听风阁后账房，玩家正在开门前整编今晚第一批碎报，"
            "桌上有纸条、口信、折角信笺，莫红绫在旁压声提醒。气氛忙而不乱，不要直接跳到街口或大会现场。"
        )

    if state.last_mini_game_type == "merge" and state.chapter_step <= 2:
        return (
            "当前必须紧接开局整编后的第一场正篇戏。你已经从密报里确认拜月教与五毒教将首次参加本届武林大会，"
            "场景要从后账房自然转到前厅，客人开始入楼，莫红绫或酒客可以出声试探。"
        )

    if state.last_mini_game_type == "match3":
        if state.last_mini_game_success:
            return "上一回玩家用三消顺手压住了前厅的怀疑声，这一回可以稍微松一口气，但暗流还在。"
        return "上一回玩家没能完全压住前厅的闲话，这一回要写出场面更紧，但仍留给玩家周旋余地。"

    if state.last_mini_game_type == "snake":
        if state.last_mini_game_success:
            return "上一回玩家从街口追回了关键风声，这一回要把新线索自然带回听风阁里。"
        return "上一回玩家在街口只追回了部分风声，这一回要写回到阁中后的补救和继续试探。"

    if expected_mini_game["type"] == "none":
        return (
            "当前以人物互动与局势铺陈为主。系统判定本回合不会挂载小游戏，"
            "叙事中不要用「闯关」「消除」「小游戏」等机制语；专注江湖场面与人物动机即可。"
        )

    return (
        f"系统仅在剧情条件满足时才会挂载互动关卡。当前预期下一节点类型为「{expected_mini_game['type']}」，"
        "你只需用自然的冲突与场面把它铺垫出来，不要直白写规则或玩法；人物与人设优先。"
    )


def apply_rule_delta(state: GameState, choice: PlayerChoice | None, player_input: str) -> GameState:
    updated = state.model_copy(deep=True)
    updated.narrative_only_until_choice = False
    updated.chapter_step += 1
    updated.choices_since_last_minigame = state.choices_since_last_minigame + 1
    intent = choice.intent if choice else "steady"
    focus = updated.focus_npc
    rapport_bonus = 0

    if intent == "steady":
        updated.exposure -= 2
        updated.tavern_heat += 1
        rapport_bonus = 1
    elif intent == "probe":
        updated.intel += 2
        updated.exposure += 1
    elif intent == "conceal":
        updated.exposure -= 4
        rapport_bonus = 1 if focus == "莫红绫" else 0
    elif intent == "trade":
        updated.silver += 18
        updated.intel += 1
        updated.tavern_heat += 2
    elif intent == "charm":
        rapport_bonus = 2
        updated.exposure += 1
    elif intent == "observe":
        updated.intel += 1
        updated.exposure -= 1
    elif intent == "press":
        updated.intel += 2
        updated.exposure += 2
        rapport_bonus = -1
    elif intent == "deflect":
        updated.exposure -= 2
        updated.tavern_heat -= 1

    if player_input:
        lower = player_input.lower()
        if "百晓生" in player_input:
            updated.exposure += 4
        if "情报" in player_input:
            updated.intel += 1
        if any(token in lower for token in ["姑娘", "公子", "关心", "陪我", "信你"]):
            rapport_bonus += 1

    updated.rapport[focus] = clamp(updated.rapport.get(focus, 0) + rapport_bonus)
    updated.exposure = clamp(updated.exposure)
    updated.intel = clamp(updated.intel, 0, 999)
    updated.silver = clamp(updated.silver, 0, 9999)
    updated.tavern_heat = clamp(updated.tavern_heat)
    return updated


def determine_focus_npc(state: GameState) -> str:
    if state.exposure >= 40:
        return "晏无秋"
    if state.chapter_step <= 1:
        return "莫红绫"
    if state.chapter_step <= 3 and state.intel >= 4:
        return "南宫翊"
    if state.chapter_step >= 4 and state.rapport.get("江潋", 0) >= 35:
        return "江潋"
    # 中后期按回合轮换主轴，避免玩家长期只绑定一位「攻略位」视角
    if state.chapter_step >= 5:
        return MAIN_CAST[(state.chapter_step - 5) % len(MAIN_CAST)]
    return state.focus_npc or "莫红绫"


def choose_mini_game(state: GameState) -> dict[str, str]:
    if state.narrative_only_until_choice:
        return {
            "type": "none",
            "reason": "上一局小游戏刚结束，请先经多轮人物对白与抉择推进剧情，再考虑下一互动节点。",
            "stakes": "无。",
        }

    if not state.opening_merge_resolved:
        return {
            "type": "merge",
            "reason": "开局要先把散碎风声整编成案头可用的信笺，才能决定今夜先盯哪一路来客。",
            "stakes": "合成到 03“封蜡信笺”即可触发首条大会异讯，并顺势接入正篇剧情。成败都会影响后续气氛，但故事都会继续。",
        }

    beats_ok = state.choices_since_last_minigame >= MIN_CHOICE_BEATS_BETWEEN_MINIGAMES
    last_t = (state.last_mini_game_type or "").strip().lower()
    same_type_cooled = state.choices_since_last_minigame >= MIN_BEATS_BEFORE_REPEAT_SAME_MINIGAME
    match3_allowed = last_t != "match3" or same_type_cooled
    snake_allowed = last_t != "snake" or same_type_cooled

    # 仅当「已缓冲足够抉择回合」且数值与剧情压力达到阈值时才挂载；避免频繁或接连触发
    if (
        beats_ok
        and match3_allowed
        and state.chapter_step >= 10
        and state.exposure >= 30
        and state.tavern_heat >= 46
    ):
        return {
            "type": "match3",
            "reason": "前厅闲话与怀疑声叠在一起，场面需要你亲手理顺，才能把质疑压下去。",
            "stakes": "成败只影响局面松紧与数值余波，剧情仍会推进。",
        }

    if (
        beats_ok
        and snake_allowed
        and state.chapter_step >= 9
        and state.intel >= 7
        and state.tavern_heat >= 40
    ):
        return {
            "type": "snake",
            "reason": "街口线报正在散走，若现在追出去，还能截住一两句要紧的风声。",
            "stakes": "成败影响局面松紧与数值余波，不阻断主线。",
        }

    return {
        "type": "none",
        "reason": "当前以叙事与人物为主，系统未检测到需要挂载互动关卡的剧情条件。",
        "stakes": "无。",
    }


def summarize_minigame_result(result: MiniGameResult) -> str:
    outcome = "成功" if result.success else "失败"
    tail = "剧情必须照常推进，请写清余波与下一手周旋空间，不得终局。" if not result.success else "请自然承接局面，为下一回合留钩子。"
    if result.summary.strip():
        return f"玩家完成了{result.type}小游戏，结果{outcome}，得分 {result.score}。{result.summary.strip()} {tail}"
    return f"玩家完成了{result.type}小游戏，结果{outcome}，得分 {result.score}。{tail}"


def build_opening_merge_scene() -> dict[str, Any]:
    opening_state = GameState()
    return {
        "scene_title": "风起听风阁",
        "scene_phase": "开局整编",
        "narration": "天刚擦黑，前厅还没彻底热起来，后账房先忙成了一团。小伙计把一路捎来的纸条、口信和折角信笺全摊在长案上，油灯照得纸边发黄。你还没来得及喝口热茶，就得先把这些零碎消息理顺。今夜要迎的客不少，哪一路风先吹进门，得靠这会儿先摸清。",
        "dialogue": [
            {"speaker": "莫红绫", "text": "先别忙着去前厅，桌上这几份耳报你亲自看。南边来的消息，不太安生。", "mood": "🙂压声提醒"},
            {"speaker": "账房伙计", "text": "掌柜的，这几张纸条都提了大会，可落款都让人刮干净了。", "mood": "😓手忙脚乱"},
            {"speaker": "南宫翊", "text": "掌柜，我在廊下等座呢，顺耳听见两句——今夜来的可不止喝酒的。", "mood": "压低声音"},
            {"speaker": "谢扶摇", "text": "峨嵋弟子在门外递话：若见异动，先别惊动满座客人。", "mood": "冷静"},
        ],
        "choices": [
            {"id": "opening-merge", "label": "先把桌上的碎报理顺", "intent": "observe", "risk_hint": "先摸清今晚的来路"},
            {"id": "opening-ready", "label": "先去前厅看一眼", "intent": "steady", "risk_hint": "能稳场，但容易漏掉细节"},
            {"id": "opening-ask", "label": "先问莫红绫南边的消息", "intent": "probe", "risk_hint": "能更快抓线索"},
        ],
        "focus_npc": "莫红绫",
        "mini_game": choose_mini_game(opening_state),
        "state_commentary": "今晚的场子还没开，人心先乱了半分。你得先把消息拢住。",
        "beat_summary": "开局前，你在后账房整编今晚的第一批密报。",
        "location": "听风阁后账房",
        "character_status": "你刚坐下，手边茶还烫着，心思已经先落到那堆零碎纸片上。",
        "turn_report": "*本回合事件：账房里收到一批来路杂乱的风声。*\n*主要行动：你在开门前先整理今晚第一批消息。*",
    }


def build_opening_story_scene(state: GameState, result: MiniGameResult) -> dict[str, Any]:
    result_clause = (
        "你按住那封刚刚合成的封蜡信笺，红泥一裂，藏在里头的名字和门派终于露了出来。"
        if result.success
        else "你勉强从散乱纸片里拼出一封半残的密札，字缝里漏出的信息已经足够让人皱眉。"
    )
    event_line = (
        "本届武林大会的客席名录上，拜月教与五毒教将首次一同受邀入场。"
        if state.sects_notice_unlocked
        else "大会名录有异动，南路邪派似乎已经被人提前写进了今届席次。"
    )
    stakes_line = (
        "消息一旦坐实，今夜听风阁接待的就不只是寻常酒客，而是盯着邪道席位来的各派眼线与说客。"
        if state.sects_notice_unlocked
        else "哪怕消息还差一角，这也说明今夜来的客人绝不会只谈酒价与房钱。"
    )
    return {
        "scene_title": "风起听风阁",
        "scene_phase": "异讯入楼",
        "narration": f"{result_clause}{event_line}{stakes_line} 前厅那边已经有人在催酒，木门一开一合，风把外头的脚步声一阵阵送进来。你把信重新压在掌心里，知道今夜不会太清闲。",
        "dialogue": [
            {"speaker": "莫红绫", "text": "拜月和五毒都进大会？这份名录一亮，今晚怕是没几个人能安稳喝完一盏酒。", "mood": "😶神色发沉"},
            {"speaker": "南宫翊", "text": "有意思——那我把窗边的座让出来，看看谁先沉不住气。", "mood": "带笑"},
            {"speaker": "谢扶摇", "text": "前厅若起争执，我会先拦在门槛上，不让他们把火引到你脸上。", "mood": "克制"},
            {"speaker": "江潋", "text": "……灯挑亮些也好。暗处说话的人，往往比亮处多。", "mood": "淡淡"},
        ],
        "choices": [
            {"id": "story-steady", "label": "先把前厅座次稳下来", "intent": "steady", "risk_hint": "低风险，先控场"},
            {"id": "story-probe", "label": "顺手打听来客名单", "intent": "probe", "risk_hint": "中风险，能多拿线索"},
            {"id": "story-conceal", "label": "让莫红绫守门，你先退一步观察", "intent": "conceal", "risk_hint": "低风险，先保身份"},
        ],
        "focus_npc": "莫红绫",
        "mini_game": choose_mini_game(state),
        "state_commentary": "异讯一落地，今晚的客人就都不是只来喝酒的了。",
        "beat_summary": "你从开局密报里确认拜月教与五毒教将首次参加本届武林大会。",
        "location": "听风阁前厅",
        "character_status": "你手里攥着刚拆开的信，心口发紧，面上却还得照旧招呼来客。",
        "turn_report": "*本回合事件：你确认拜月教与五毒教会在本届大会露面。*\n*主要行动：你带着新消息回到前厅，准备接今晚第一拨客。*",
    }


def apply_mini_game_result(state: GameState, result: MiniGameResult) -> GameState:
    updated = state.model_copy(deep=True)
    updated.chapter_step += 1
    updated.last_mini_game_type = result.type
    updated.last_mini_game_success = result.success
    updated.last_mini_game_score = result.score

    if result.type == "match3":
        if result.success:
            updated.exposure -= 8 + min(result.score // 2, 6)
            updated.tavern_heat += 1
        else:
            updated.exposure += 6
            updated.tavern_heat -= 1
    elif result.type == "merge":
        if result.success:
            updated.intel += 3 + min(result.score // 4, 3)
            updated.silver += 16 + min(result.score, 18)
            gifts_add: list[str] = []
            if result.achieved_level >= 1:
                gifts_add.append("裁光纸条")
            if result.achieved_level >= 2:
                gifts_add.append("桃花笺")
            if result.achieved_level >= 3:
                gifts_add.extend(["青竹笛", "陈年酒坛", "封蜡信笺礼", "玲珑酒坛", "赤狐面具"])
            for g in gifts_add:
                if g not in updated.player_merge_gifts:
                    updated.player_merge_gifts.append(g)
        else:
            updated.intel += 1
            updated.silver += 4
    elif result.type == "snake":
        if result.success:
            updated.intel += 4 + min(result.score // 2, 4)
            updated.silver += 10 + min(result.score, 12)
        else:
            updated.intel += 1
            updated.exposure += 2

    if result.type == "merge" and not updated.opening_merge_resolved:
        updated.opening_merge_resolved = True
        if result.achieved_level >= 3 or result.triggered_event == "sects_joined":
            updated.sects_notice_unlocked = True
            synth = ["拜月教首次参会", "五毒教首次参会"]
            updated.unlocked_tags.extend(synth)
            updated.player_secrets = append_definition_secrets(
                list(updated.player_secrets),
                "merged_baiyue_entry",
                "merged_wudu_entry",
                "secret_baiyue_roster",
            )
    elif result.type == "merge" and result.achieved_level >= 3:
        updated.sects_notice_unlocked = True

    if updated.focus_npc in updated.rapport:
        rapport_delta = 1 if result.success else -1
        if result.type == "merge" and updated.focus_npc == "莫红绫":
            rapport_delta += 1
        updated.rapport[updated.focus_npc] = clamp(updated.rapport[updated.focus_npc] + rapport_delta)

    updated.exposure = clamp(updated.exposure)
    updated.intel = clamp(updated.intel, 0, 999)
    updated.silver = clamp(updated.silver, 0, 9999)
    updated.tavern_heat = clamp(updated.tavern_heat)
    updated.unlocked_tags = list(dict.fromkeys(updated.unlocked_tags))[-12:]
    updated.narrative_only_until_choice = True
    updated.choices_since_last_minigame = 0
    return updated


def extract_json_payload(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(cleaned[start : end + 1])


def build_messages(
    state: GameState,
    player_name: str,
    player_gender: str,
    action_summary: str,
) -> list[dict[str, str]]:
    story_system_prompt = load_story_system_prompt()
    character_config = load_character_config()
    character_cards = format_character_cards(character_config)
    focus_playbook = format_focus_character_playbook(character_config, state.focus_npc)
    scene_instruction = build_scene_instruction(state)
    expected_mini_game = choose_mini_game(state)
    chapter_rules = f"""
你当前负责《江湖百晓生》第一章“风起听风阁”的场景推进。

当前章节硬规则：
1. 玩家公开身份是听风阁掌柜，隐藏身份是百晓生。
2. 当前大背景是武林大比将近，各方势力都在探消息。
3. 只推进当前一小场，不要直接写完整季终局。
4. 剧情必须适合手机竖屏阅读：短段落、场景清楚、对白自然。
5. 你输出的是 JSON，不要加解释，不要加代码块。
6. choices 固定输出 3 个，每个 choice.intent 必须从下列枚举选择：
   steady, probe, conceal, trade, charm, observe, press, deflect
7. dialogue 须输出 **4～5 条**（不少于 4，不超过 5），以**对白与即时反应**推动剧情；每条字段为 speaker、text、mood；台词必须生活化，可含打断、抢话、留白，不要写成旁白总结。
8. **群像要求**：每回合 dialogue 中须出现 **至少两名** 不同的固定名单角色（莫红绫、南宫翊、谢扶摇、江潋、晏无秋）；**focus_npc** 可以占其中 1～2 条，但必须另有 **至少一位名单上的其他角色** 有独立台词或清晰在场的互动反应，禁止整回合只有 focus 一人开口、他人只当背景板。
9. 不要替玩家发台词，不要让玩家名字、玩家、你、掌柜作为 dialogue 里的 speaker。
10. narration（叙事正文）必须为 600 到 800 个汉字（含标点），可分 2–4 个短段；写清场面、动作与心绪，仍须适合竖屏分段阅读。
11. 是否出现 merge/match3/snake 由服务端根据剧情条件决定并已写入状态里的 expected_mini_game；你输出里的 mini_game 字段会被忽略。
12. 文中禁止写「三消」「闯关」「小游戏」「消除」等机制词，只用剧情内的行动与场面描写。
13. 文风必须通俗易懂，有市井烟火气，用白描和具体动作写场景、心理、情感。
14. 禁止华丽辞藻、隐喻轰炸、科幻、AI、量子、克苏鲁、生物拟态、灾难化、无逻辑设定。
15. 凡 dialogue 里点名的说话人若在下方「固定角色配置」中出现，必须严格遵循其说话风格、扮演指令与表现禁区，禁止 OOC 或千人一面。
16. 允许细腻，但全文不要一直堆氛围；重点场面再收紧情绪描写。
17. 采用小说场景写法，善用自然转场；不要三处以上回忆，不要暴力化描写。
18. 若 action_summary 表明玩家刚完成小游戏且失败，必须在叙事中体现代价或被动，但须给后续抉择留出口，不得写成故事无法继续。
19. **门派声势与情报交易**：`sect_influence` 为七派声势（0–100）；`intel_trade_log` 为玩家最近向门派出售情报的摘要。若 log 非空且含新条目，须在叙事或对白中**自然**体现其后果（某派得利、掌柜树敌、风声走漏、暴露升高等），勿机械复读 JSON，勿写成系统公告。
20. 额外输出：
   - location：简洁地点，如“听风阁前厅”
   - intel_ledger：字符串数组，**0～2** 条，每条 **4～28** 字。仅当本轮 **对白里名单角色明确说出** 可能改变局势的新事实（人名、门派动向、时辰地点、约期、暗号等）时写入，写成道具栏可用的短标签；禁止叙事总结、禁止写玩家内心、禁止以「玩家」「言笑」等开头；禁止与已有 `player_secrets` 标题重复；场面废话、进度描写会由服务端归入 story_logs 而非道具。若无则输出 []。

固定角色配置（全文人设依据）：
{character_cards}

{focus_playbook}
""".strip()
    rules = f"{story_system_prompt}\n\n{chapter_rules}"

    state_snapshot = {
        "player_name": player_name,
        "player_gender": player_gender,
        "chapter_id": state.chapter_id,
        "chapter_step": state.chapter_step,
        "silver": state.silver,
        "intel": state.intel,
        "exposure": state.exposure,
        "tavern_heat": state.tavern_heat,
        "focus_npc": state.focus_npc,
        "rapport": state.rapport,
        "previous_beats": state.previous_beats[-4:],
        "unlocked_tags": state.unlocked_tags[-6:],
        "last_mini_game_type": state.last_mini_game_type,
        "last_mini_game_success": state.last_mini_game_success,
        "last_mini_game_score": state.last_mini_game_score,
        "choices_since_last_minigame": state.choices_since_last_minigame,
        "min_choice_beats_before_minigame": MIN_CHOICE_BEATS_BETWEEN_MINIGAMES,
        "min_beats_before_repeat_same_minigame": MIN_BEATS_BEFORE_REPEAT_SAME_MINIGAME,
        "sect_influence": state.sect_influence,
        "intel_trade_log": state.intel_trade_log[-6:],
        "player_secrets": [
            {"id": s.id, "title": s.title, "tier": s.tier, "secret_type": s.secret_type.value}
            for s in filter_valid_secrets(state.player_secrets)[-12:]
        ],
        "expected_mini_game": expected_mini_game,
        "scene_instruction": scene_instruction,
        "action_summary": action_summary,
        "ensemble_cast": "莫红绫、南宫翊、谢扶摇、江潋、晏无秋（除 focus 外每回合须让至少一人实质性出场对白）",
    }

    output_schema = {
        "scene_title": "场景标题",
        "scene_phase": "夜局初起/暗流试探/风声骤紧等阶段名",
        "narration": "叙事正文（600–800 字）",
        "dialogue": [{"speaker": "角色名", "text": "台词", "mood": "情绪"}],
        "choices": [
            {"id": "choice-a", "label": "可点击选项文案", "intent": "steady", "risk_hint": "风险提示"}
        ],
        "focus_npc": "本场核心角色",
        "mini_game": {"type": "none", "reason": "触发原因", "stakes": "成败意义"},
        "location": "听风阁前厅",
        "intel_ledger": ["短标签一", "短标签二"],
        "state_commentary": "一句话告诉玩家当前局面变化",
        "beat_summary": "一句话概括这场推进",
    }

    return [
        {"role": "system", "content": rules},
        {
            "role": "user",
            "content": "请基于以下状态推进第一章。\n"
            + json.dumps(state_snapshot, ensure_ascii=False)
            + "\n输出 JSON 结构示意：\n"
            + json.dumps(output_schema, ensure_ascii=False),
        },
    ]


async def call_story_model(state: GameState, player_name: str, player_gender: str, action_summary: str) -> dict[str, Any]:
    if not AI_API_KEY:
        raise RuntimeError("AI_API_KEY is missing.")

    payload = {
        "model": AI_MODEL,
        "temperature": 0.72,
        "max_tokens": 3600,
        "messages": build_messages(state, player_name, player_gender, action_summary),
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{AI_BASE_URL}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if isinstance(content, list):
                    content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
                return extract_json_payload(content)
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, KeyError, ValueError) as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError("Story model returned no payload.")


def build_private_chat_system_prompt(
    character_record: dict[str, Any] | None,
    custom_npc: dict[str, str] | None,
    story_context: dict[str, str],
) -> str:
    story = load_story_system_prompt()
    private_rules = """
### 私聊回复专规（江湖传信 · 信笺体）
- 你写的是**密笺一封中的片段**：语短意长，可有停顿、留白、反问、轻嘲；像毛笔边批，不像现代聊天软件短讯。
- 单次回复 90–240 字（中文），2–6 句；禁止说明书腔、公文腔。
- 严格执行人设卡中的风格、禁区与扮演指令；禁止替听风阁掌柜代言其未说出口的话。
- 首句起势须贴合你独有的称呼与脾性，禁止与其他角色撞同一套「万能开场」。
- **严禁**出现：游戏、关卡、数值、经验、血条、副本、NPC、存档、读档、系统提示、AI、模型、小游戏、三消等破界词。
- 只输出 JSON：{"reply":"……"}，仅一个键，不要代码块或其它文字。
""".strip()
    ctx_block = ""
    if story_context:
        ctx_block = (
            "\n\n【当前主线语境（只供把握语气、关系与称呼，勿逐条复述给玩家）】\n"
            + json.dumps(story_context, ensure_ascii=False)
        )

    if character_record:
        card = format_character_cards({"characters": [character_record]})
        who = character_record.get("name", "该角色")
        return f"{story}\n\n{private_rules}\n\n你是「{who}」，以下为你在全文中的固定人设（必须逐条落实）：\n{card}{ctx_block}"
    if custom_npc:
        name = str(custom_npc.get("name", "无名")).strip() or "无名"
        personality = str(custom_npc.get("personality", "")).strip()
        backstory = str(custom_npc.get("backstory", "")).strip()
        block = "\n".join(
            [
                f"【{name}】（玩家自定义江湖人物）",
                f"- 性格：{personality or '未注明'}",
                f"- 来历与立场：{backstory or '未注明'}",
            ]
        )
        return f"{story}\n\n{private_rules}\n\n你必须严格按以下设定扮演，并保持活人感私信口吻：\n{block}{ctx_block}"
    return f"{story}\n\n{private_rules}\n\n（未匹配到具体人设卡，请按听风阁夜局中的江湖人口吻回复，仍须有活人感。）{ctx_block}"


def private_reply_fallback(character_record: dict[str, Any] | None, custom_npc: dict[str, str] | None) -> str:
    if custom_npc:
        n = custom_npc.get("name", "某人")
        return f"行，我先记着。你这会儿在阁里别声张，{n}这边替你盯着。"
    name = (character_record or {}).get("name", "我")
    fallbacks = {
        "莫红绫": "啧。你少在传书里写这么明白，外头眼睛多。……行了，我看过就行，回阁里当面说。",
        "南宫翊": "哈，你这话有意思。等我绕开随从，再找你说——今夜可别让我扑空。",
        "谢扶摇": "嗯。此事我记下了。你稳住，别让人从你话缝里听出破绽。",
        "江潋": "……看见了。别急着回，想清楚再开口。",
        "晏无秋": "你发得倒干脆。可惜传书留痕——下一句，想好了再说。",
    }
    return fallbacks.get(name, f"{name}：收到。回阁当面讲，别在这儿写太细。")


async def call_private_reply_model(system_prompt: str, api_messages: list[dict[str, str]]) -> str:
    if not AI_API_KEY:
        raise RuntimeError("AI_API_KEY is missing.")
    payload = {
        "model": AI_MODEL,
        "temperature": 0.82,
        "max_tokens": 650,
        "messages": [{"role": "system", "content": system_prompt}, *api_messages],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=CHAT_REPLY_TIMEOUT) as client:
        response = await client.post(
            f"{AI_BASE_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        parsed = extract_json_payload(content)
        reply = str(parsed.get("reply", "")).strip()
        if not reply:
            raise ValueError("Empty reply.")
        return reply[:800]


def intel_sale_fallback(intel_text: str, buyer: str) -> dict[str, Any]:
    _ = intel_text
    return {
        "value_tier": "中",
        "buyer_influence_delta": 4,
        "silver_delta": 28,
        "exposure_delta": 2,
        "verdict": f"{buyer}收了风声，价码还行。",
        "hook_story": f"{buyer}略占先手，阁里也有人记下了掌柜这笔生意。",
    }


def coerce_intel_sale_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "value_tier": str(parsed.get("value_tier", "中")).strip() or "中",
        "buyer_influence_delta": float(parsed.get("buyer_influence_delta", 3)),
        "silver_delta": float(parsed.get("silver_delta", 22)),
        "exposure_delta": float(parsed.get("exposure_delta", 1)),
        "verdict": str(parsed.get("verdict", "")).strip(),
        "hook_story": str(parsed.get("hook_story", "")).strip(),
    }


async def call_intel_sale_model(
    player_name: str,
    intel_text: str,
    buyer: str,
    sect_snapshot: dict[str, int],
    recent_log: list[str],
) -> dict[str, Any]:
    if not AI_API_KEY:
        raise RuntimeError("AI_API_KEY is missing.")
    system = """你是《江湖百晓生》的情报交易裁判。玩家把一条情报卖给某门派。
仅输出 JSON：{"value_tier":"高|中|低","buyer_influence_delta":整数,"silver_delta":整数,"exposure_delta":整数,"verdict":"一句成交评语（勿复述情报全文）","hook_story":"一句供下一段主线自然呼应的余波"}
数值约束：buyer_influence_delta 约 -8 至 12；silver_delta 0 至 120；exposure_delta -4 至 10。
逻辑：情报越对口买家立场、越独家，价与声势越高；卖给险棋或风声太野，可能加暴露；胡编则低价。
禁止元叙事词。"""
    user_payload = {
        "掌柜": player_name,
        "情报": intel_text.strip(),
        "买家门派": buyer,
        "当前七派声势": sect_snapshot,
        "近期售卖记录": recent_log[-4:],
    }
    payload = {
        "model": AI_MODEL,
        "temperature": 0.42,
        "max_tokens": 480,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=CHAT_REPLY_TIMEOUT) as client:
        response = await client.post(
            f"{AI_BASE_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        parsed = extract_json_payload(content)
        return coerce_intel_sale_payload(parsed)


def apply_intel_sale(state: GameState, secret_id: str, buyer: str, ai: dict[str, Any]) -> GameState:
    u = state.model_copy(deep=True)
    sold = next((s for s in u.player_secrets if s.id == secret_id), None)
    label = sold.title if sold else secret_id
    u.player_secrets = remove_secret_by_id(list(u.player_secrets), secret_id)
    bd = clamp_int(int(round(float(ai.get("buyer_influence_delta", 3)))), -8, 12)
    sd = clamp_int(int(round(float(ai.get("silver_delta", 22)))), 0, 120)
    ed = clamp_int(int(round(float(ai.get("exposure_delta", 1)))), -4, 14)
    u.sect_influence[buyer] = clamp_int(u.sect_influence[buyer] + bd, 0, 100)
    u.silver = clamp_int(u.silver + sd, 0, 99999)
    u.exposure = clamp_int(u.exposure + ed, 0, 100)
    verdict = str(ai.get("verdict", "")).strip() or "成交。"
    hook = str(ai.get("hook_story", "")).strip()
    short_intel = label.strip()[:40]
    line = f"{buyer}购「{short_intel}」：{verdict[:56]}"
    if hook:
        line = f"{line}丨余波：{hook[:56]}"
    u.intel_trade_log = (u.intel_trade_log + [line])[-8:]
    return u


def _gift_ack_text(character: dict[str, Any], gift: str, tier: str) -> str:
    name = character.get("name", "")
    if tier == "心仪":
        lines = {
            "莫红绫": f"……这「{gift}」你也舍得。（指节在笺边顿了顿）收下了。别指望我嘴上谢你。",
            "南宫翊": f"哈！「{gift}」？掌柜真懂我——本公子记你这份人情，改日加倍还你。",
            "谢扶摇": f"「{gift}」……劳你记挂。此物我收下，改日当面再谢。",
            "江潋": f"「{gift}」我收了。你这般用心，让我很难装作看不见。",
            "晏无秋": f"有趣。连「{gift}」都送得这么准——你是想让我欠你，还是让我信你？",
        }
        return lines.get(name, f"「{gift}」我收下。难得你记得我喜欢这些。")
    if tier == "合意":
        return f"「{gift}」我收下。心意领了，别总破费。"
    return f"东西我收了。往后少花这些冤枉钱。"


@app.get("/api/hub/character_brief")
async def hub_character_brief() -> dict[str, Any]:
    cfg = load_character_config()
    return {
        "characters": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "avatar_url": (c.get("avatar_url") or "").strip() or None,
                "chat_opening": (c.get("chat_opening") or "").strip(),
            }
            for c in cfg.get("characters", [])
            if isinstance(c, dict)
        ]
    }


@app.post("/api/hub/private_gift", response_model=PrivateGiftResponse)
async def hub_private_gift(request: PrivateGiftRequest) -> PrivateGiftResponse:
    cfg = load_character_config()
    char = get_character_by_config_id(cfg, request.character_config_id)
    if not char:
        raise HTTPException(status_code=400, detail="Unknown character_config_id.")
    st = request.state.model_copy(deep=True)
    if not is_private_chat_unlocked(st, request.character_config_id):
        raise HTTPException(status_code=403, detail="剧情尚未与此人照面，传书未通。")
    gift = request.gift_label.strip()
    pool = list(st.player_merge_gifts)
    if gift not in pool:
        raise HTTPException(status_code=400, detail="行囊中没有这件可赠之物。")
    pool.remove(gift)
    st.player_merge_gifts = pool
    loved = list(char.get("gift_loved") or [])
    liked = list(char.get("gift_liked") or [])
    nm = str(char.get("name", ""))
    if gift in loved:
        tier = "心仪"
        delta = 16
    elif gift in liked:
        tier = "合意"
        delta = 9
    else:
        tier = "寻常"
        delta = 4
    st.rapport[nm] = clamp(st.rapport.get(nm, 0) + delta)
    if not char.get("knows_player_identity"):
        bump_guess_identity(st, nm, 5 if tier == "心仪" else 2)
    reply = _gift_ack_text(char, gift, tier)
    append_private_memory(st, request.character_config_id, f"[赠礼] 掌柜赠「{gift}」。")
    append_private_memory(st, request.character_config_id, f"{nm}：{reply[:160]}")
    return PrivateGiftResponse(reply=reply, state=st, rapport_delta=delta)


@app.post("/api/hub/private_reply", response_model=PrivateReplyResponse)
async def hub_private_reply(request: PrivateReplyRequest) -> PrivateReplyResponse:
    character_config = load_character_config()
    all_chars = list(character_config.get("characters", []))
    character_record: dict[str, Any] | None = None
    if request.character_config_id:
        character_record = get_character_by_config_id(character_config, request.character_config_id)
    custom = request.custom_npc if request.custom_npc else None
    if custom and not str(custom.get("name", "")).strip():
        raise HTTPException(status_code=400, detail="custom_npc.name is required.")
    if not character_record and not custom:
        raise HTTPException(status_code=400, detail="Provide character_config_id or custom_npc.")

    if request.state is not None and request.character_config_id:
        if not is_private_chat_unlocked(request.state, request.character_config_id):
            raise HTTPException(status_code=403, detail="剧情尚未与此人照面，江湖传信未通。")

    system_prompt = build_private_chat_system_prompt(
        character_record,
        custom,
        request.story_context or {},
    )
    system_prompt += (
        f"\n\n对方听风阁掌柜自称：{request.player_name}（{request.player_gender}）。"
        "本轮是其来信，请以密笺口吻回复，勿称对方为「玩家」。"
    )

    st_work: GameState | None = request.state.model_copy(deep=True) if request.state is not None else None
    if st_work is not None and character_record and request.character_config_id:
        mem = format_private_memory_block(st_work, request.character_config_id)
        if mem:
            system_prompt += f"\n\n【仅你可回忆的往来碎影（勿对掌柜照本宣科列举）】\n{mem}"
        system_prompt += "\n\n" + build_identity_cognition_block(
            character_record,
            st_work,
            player_gender=request.player_gender,
        )

    api_messages: list[dict[str, str]] = []
    for turn in request.history[-12:]:
        api_messages.append({"role": turn.role, "content": turn.content})
    api_messages.append({"role": "user", "content": request.message.strip()})

    using_fallback = False
    reply = ""
    ooc_note = ""
    if character_record:
        got_clean = False
        for _attempt in range(3):
            extra = f"\n\n（重写要求：{ooc_note}）" if ooc_note else ""
            try:
                reply = await call_private_reply_model(system_prompt + extra, api_messages)
            except Exception:
                reply = ""
            if not reply.strip():
                continue
            ok, reason = ooc_check_reply(
                reply,
                speaker_name=str(character_record.get("name", "")),
                character_config=character_record,
                all_characters=all_chars,
            )
            if ok:
                got_clean = True
                break
            ooc_note = reason or "不得越界提及他人隐线或现代用语"
        if not got_clean or not reply.strip():
            reply = private_reply_fallback(character_record, custom)
            using_fallback = True
    else:
        try:
            reply = await call_private_reply_model(system_prompt, api_messages)
        except Exception:
            reply = private_reply_fallback(character_record, custom)
            using_fallback = True

    st_out: GameState | None = None
    if st_work is not None and character_record and request.character_config_id:
        append_private_memory(st_work, request.character_config_id, f"掌柜：{request.message.strip()[:120]}")
        append_private_memory(st_work, request.character_config_id, f"{character_record.get('name','')}：{reply[:160]}")
        if not character_record.get("knows_player_identity"):
            bump_guess_identity(st_work, str(character_record.get("name", "")), 2)
        st_out = st_work

    return PrivateReplyResponse(reply=reply, using_fallback=using_fallback, state=st_out)


@app.post("/api/hub/sell_intel", response_model=SellIntelResponse)
async def hub_sell_intel(request: SellIntelRequest) -> SellIntelResponse:
    buyer = resolve_buyer_sect(request.buyer_sect)
    st = request.state
    secret = next((s for s in st.player_secrets if s.id == request.secret_id.strip()), None)
    if not secret or secret.secret_type != SecretType.MERGED_SECRET:
        raise HTTPException(status_code=400, detail="无效的秘辛或不可售卖。")
    sale_brief = sale_summary_for_ai(
        secret,
        request.player_name.strip() or "言笑笑",
        st.chapter_id,
        list(st.player_secrets),
    )
    old_silver = st.silver
    old_exp = st.exposure
    old_buyer_power = st.sect_influence[buyer]
    using_fallback = False
    raw: dict[str, Any]
    try:
        raw = await call_intel_sale_model(
            request.player_name.strip() or "言笑笑",
            sale_brief,
            buyer,
            dict(st.sect_influence),
            list(st.intel_trade_log),
        )
    except Exception:
        raw = intel_sale_fallback(sale_brief, buyer)
        using_fallback = True
    new_state = apply_intel_sale(st, secret.id, buyer, raw)
    return SellIntelResponse(
        buyer_sect=buyer,
        verdict=str(raw.get("verdict", "")).strip(),
        value_tier=str(raw.get("value_tier", "中")).strip() or "中",
        silver_delta=new_state.silver - old_silver,
        buyer_influence_delta=new_state.sect_influence[buyer] - old_buyer_power,
        exposure_delta=new_state.exposure - old_exp,
        hook_story=str(raw.get("hook_story", "")).strip(),
        state=new_state,
        using_fallback=using_fallback,
    )


@app.post("/api/hub/secret_detail", response_model=SecretDetailResponse)
async def hub_secret_detail(request: SecretDetailRequest) -> SecretDetailResponse:
    st = request.state.model_copy(deep=True)
    sid = request.secret_id.strip()
    sec = next((s for s in st.player_secrets if s.id == sid), None)
    if not sec or sec.secret_type != SecretType.MERGED_SECRET:
        raise HTTPException(status_code=404, detail="未找到该秘辛。")
    pn = request.player_name.strip() or "言笑笑"
    body = SecretContentGenerator.build_body(
        sec,
        player_name=pn,
        chapter_id=st.chapter_id,
        all_secrets=list(st.player_secrets),
    )
    return SecretDetailResponse(
        id=sec.id,
        title=sec.title,
        tier=sec.tier,
        body=body,
        secret_type=sec.secret_type.value,
        state=st,
    )


def build_fallback_scene(state: GameState, action_summary: str) -> dict[str, Any]:
    if not state.opening_merge_resolved:
        return build_opening_merge_scene()

    if state.last_mini_game_type == "merge" and state.chapter_step <= 2:
        return build_opening_story_scene(
            state,
            MiniGameResult(
                type="merge",
                success=state.last_mini_game_success,
                score=state.last_mini_game_score,
                achieved_level=3 if state.sects_notice_unlocked else 2,
                triggered_event="sects_joined" if state.sects_notice_unlocked else "",
            ),
        )

    focus = state.focus_npc
    mini_game = choose_mini_game(state)
    lines = {
        "莫红绫": [
            {"speaker": "莫红绫", "text": "今夜来的客人眼神太杂，你最好别露出半点破绽。", "mood": "压低声音"},
            {"speaker": "南宫翊", "text": "我坐窗边替你数人头，谁多看了你一眼，我都能记下来。", "mood": "半真半假"},
            {"speaker": "谢扶摇", "text": "前厅若有口角，我先挡一挡，你别急着接话。", "mood": "冷静"},
            {"speaker": "江潋", "text": "……茶凉了再续。急的人，往往先露底。", "mood": "淡淡"},
        ],
        "南宫翊": [
            {"speaker": "南宫翊", "text": "掌柜，给我留个靠窗的位置。今夜我要看看，江湖人到底怎么谈风声。", "mood": "爽朗"},
            {"speaker": "莫红绫", "text": "你最好小心点，这位公子身后跟着的不只是银子。", "mood": "戒备"},
            {"speaker": "谢扶摇", "text": "公子若要听真话，就别让人听见你在听什么。", "mood": "提醒"},
            {"speaker": "晏无秋", "text": "窗边的位子好。亮处的人，最容易被人当戏看。", "mood": "不紧不慢"},
        ],
        "江潋": [
            {"speaker": "江潋", "text": "今夜这楼里，谁坐得近，谁坐得远，你心里要有数。", "mood": "沉稳"},
            {"speaker": "莫红绫", "text": "你看，又有人把旧事推到你面前来了。", "mood": "意味深长"},
            {"speaker": "南宫翊", "text": "盟主既然进城了，我这点小热闹也算凑得巧。", "mood": "笑"},
            {"speaker": "谢扶摇", "text": "峨嵋只望今夜别见血光，别的各凭分寸。", "mood": "端正"},
        ],
        "谢扶摇": [
            {"speaker": "谢扶摇", "text": "今夜入阁的人太杂，若有异动，我会先替你拦下。", "mood": "清冷"},
            {"speaker": "莫红绫", "text": "大师姐话少，但比谁都管用——你别逞能。", "mood": "低声"},
            {"speaker": "南宫翊", "text": "有大师姐在，我反倒想多听两句江湖规矩。", "mood": "好奇"},
            {"speaker": "晏无秋", "text": "规矩？规矩常常是拿来试探胆色的。", "mood": "轻飘飘"},
        ],
        "晏无秋": [
            {"speaker": "晏无秋", "text": "有些名字不该在灯下提起，但今夜偏偏有人在等那个名字。", "mood": "平静"},
            {"speaker": "莫红绫", "text": "别接他的眼神。", "mood": "警觉"},
            {"speaker": "南宫翊", "text": "掌柜，我替你挡一句——有事冲我来，别绕弯子。", "mood": "硬气"},
            {"speaker": "谢扶摇", "text": "阁里还要做生意，诸位若要算账，出去算。", "mood": "冷"},
        ],
    }

    return {
        "scene_title": "风起听风阁",
        "scene_phase": "夜局初起",
        "narration": f"夜色落下来后，听风阁反倒比白日还热闹。灶上温着酒，堂里说话声一阵高一阵低，谁都像在闲聊，谁都没真的放松。{action_summary} 你抬眼时，正看见{focus}把杯盏轻轻按在桌上，像是在提醒你，今夜这门生意没表面那么简单。",
        "dialogue": lines.get(focus, lines["莫红绫"]),
        "choices": [
            {"id": "steady-1", "label": "笑着把场面稳住", "intent": "steady", "risk_hint": "低风险，先保住身份"},
            {"id": "probe-1", "label": "顺口探一探来客来路", "intent": "probe", "risk_hint": "中风险，能换线索"},
            {"id": "conceal-1", "label": "让莫红绫先挡一挡", "intent": "conceal", "risk_hint": "低风险，先藏锋"},
        ],
        "focus_npc": focus,
        "mini_game": mini_game,
        "state_commentary": "这一回像是在试火候，说重了不行，说轻了也不行。",
        "beat_summary": f"你在听风阁夜局中把注意力落到了{focus}身上。",
        "location": infer_location(state, "夜局初起", mini_game["type"]),
        "character_status": infer_character_status(state, focus),
        "turn_report": f"*本回合事件：{focus}先给了你一个提醒。*\n*主要行动：{action_summary}*",
    }


def normalize_scene_payload(
    payload: dict[str, Any],
    state: GameState,
    using_fallback: bool,
    action_summary: str = "",
    player_name: str = "",
) -> ChapterResponse:
    mini_game = choose_mini_game(state)
    choices = payload.get("choices") or []
    dialogue = ensure_dialogue_quotes(payload.get("dialogue", []), player_name=player_name)
    if not dialogue:
        dialogue = ensure_dialogue_quotes(build_fallback_scene(state, action_summary).get("dialogue", []), player_name=player_name)
    normalized_choices: list[PlayerChoice] = []
    for idx, choice in enumerate(choices[:3]):
        intent = choice.get("intent", "steady")
        if intent not in INTENT_LABELS:
            intent = "steady"
        normalized_choices.append(
            PlayerChoice(
                id=choice.get("id") or f"choice-{idx + 1}",
                label=choice.get("label") or INTENT_LABELS[intent],
                intent=intent,
                risk_hint=choice.get("risk_hint") or "",
            )
        )
    while len(normalized_choices) < 3:
        fallback_intent = ["steady", "probe", "conceal"][len(normalized_choices)]
        normalized_choices.append(
            PlayerChoice(
                id=f"auto-{len(normalized_choices) + 1}",
                label=INTENT_LABELS[fallback_intent],
                intent=fallback_intent,
                risk_hint="系统补全选项",
            )
        )

    focus_npc = str(payload.get("focus_npc") or "").strip() or state.focus_npc
    if focus_npc not in state.rapport:
        for line in dialogue:
            speaker = line.get("speaker")
            if speaker in state.rapport:
                focus_npc = speaker
                break

    beat_summary = payload.get("beat_summary", "第一章正在展开。")
    scene_phase = payload.get("scene_phase", "夜局初起")
    location = payload.get("location") or infer_location(state, scene_phase, mini_game.get("type", "none"))
    if not state.opening_merge_resolved:
        scene_phase = "开局整编"
        location = "听风阁后账房"
    elif state.last_mini_game_type == "merge" and state.chapter_step <= 2:
        scene_phase = "异讯入楼"
        location = "听风阁前厅"
    turn_report = ""
    character_status = ""

    return ChapterResponse(
        scene_title=payload.get("scene_title", "风起听风阁"),
        scene_phase=scene_phase,
        narration=payload.get("narration", "听风阁的灯火亮了起来。"),
        dialogue=dialogue,
        choices=normalized_choices,
        focus_npc=focus_npc,
        mini_game={
            "type": mini_game.get("type", "none"),
            "reason": mini_game.get("reason", "无"),
            "stakes": mini_game.get("stakes", "无"),
        },
        state_commentary=payload.get("state_commentary", "局面仍在你的掌控边缘。"),
        beat_summary=beat_summary,
        updated_at=current_timestamp(),
        turn_label=build_turn_label(state.chapter_step),
        location=location,
        character_status=character_status,
        turn_report=turn_report,
        state=state,
        using_fallback=using_fallback,
    )


async def produce_scene(player_name: str, player_gender: str, state: GameState, action_summary: str) -> ChapterResponse:
    state.focus_npc = determine_focus_npc(state)
    using_fallback = False
    try:
        payload = await call_story_model(state, player_name, player_gender, action_summary)
    except Exception:
        payload = build_fallback_scene(state, action_summary)
        using_fallback = True
    scene = normalize_scene_payload(
        payload,
        state,
        using_fallback,
        action_summary=action_summary,
        player_name=player_name,
    )
    apply_intel_ledger_to_state(scene.state, payload)
    register_npc_encounter(scene.state, scene.focus_npc)
    scene.state.focus_npc = scene.focus_npc
    scene.state.previous_beats.append(scene.beat_summary)
    scene.state.previous_beats = scene.state.previous_beats[-8:]
    scene.state.unlocked_tags = scene.state.unlocked_tags[-12:]
    return scene


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    config_ready = True
    config_error = ""
    try:
        load_story_system_prompt()
        load_character_config()
    except Exception as exc:
        config_ready = False
        config_error = str(exc)
    return {
        "ok": True,
        "ai_base_url": AI_BASE_URL,
        "ai_model": AI_MODEL,
        "has_api_key": bool(AI_API_KEY),
        "config_ready": config_ready,
        "config_error": config_error,
        "story_system_prompt_path": str(STORY_SYSTEM_PROMPT_PATH),
        "character_config_path": str(CHARACTER_CONFIG_PATH),
    }


@app.post("/api/chapter/start", response_model=ChapterResponse)
async def chapter_start(request: StartRequest) -> ChapterResponse:
    state = GameState()
    state.previous_beats.append("第一章开始，听风阁迎来武林大比前夜。")
    return await produce_scene(
        player_name=request.player_name,
        player_gender=request.player_gender,
        state=state,
        action_summary="第一章刚开场，你坐进后账房，准备先理清今晚第一批送来的风声。",
    )


@app.post("/api/chapter/advance", response_model=ChapterResponse)
async def chapter_advance(request: AdvanceRequest) -> ChapterResponse:
    if request.state.chapter_id != "chapter-01":
        raise HTTPException(status_code=400, detail="Only chapter-01 is available in this prototype.")

    updated_state = apply_rule_delta(request.state, request.choice, request.player_input)
    return await produce_scene(
        player_name=request.player_name,
        player_gender=request.player_gender,
        state=updated_state,
        action_summary=summarize_action(request.choice, request.player_input),
    )


@app.post("/api/chapter/minigame", response_model=ChapterResponse)
async def chapter_minigame(request: MiniGameRequest) -> ChapterResponse:
    if request.state.chapter_id != "chapter-01":
        raise HTTPException(status_code=400, detail="Only chapter-01 is available in this prototype.")

    updated_state = apply_mini_game_result(request.state, request.result)
    materialize_roster_for_secrets(
        updated_state.player_secrets,
        request.player_name,
        updated_state.chapter_id,
    )
    return await produce_scene(
        player_name=request.player_name,
        player_gender=request.player_gender,
        state=updated_state,
        action_summary=summarize_minigame_result(request.result),
    )
