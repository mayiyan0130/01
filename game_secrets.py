"""秘辛类型、过滤、详情正文生成（与 GameDatabase.json 联动）。"""

from __future__ import annotations

import hashlib
import json
import random
import re
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
GAME_DB_PATH = BASE_DIR / "config" / "GameDatabase.json"

_db_cache: dict[str, Any] | None = None


class SecretType(str, Enum):
    RAW_RUMOR = "raw_rumor"
    MERGED_SECRET = "merged_secret"
    STORY_LOG = "story_log"


class PlayerSecret(BaseModel):
    id: str
    secret_type: SecretType = SecretType.MERGED_SECRET
    title: str = Field(..., min_length=1, max_length=80)
    tier: int = Field(default=2, ge=1, le=6)
    generator_key: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


def load_game_database() -> dict[str, Any]:
    global _db_cache
    if _db_cache is None:
        _db_cache = json.loads(GAME_DB_PATH.read_text(encoding="utf-8"))
    return _db_cache


def reload_game_database() -> None:
    global _db_cache
    _db_cache = None
    load_game_database()


def _stable_seed(*parts: str) -> int:
    h = hashlib.sha256("｜".join(parts).encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def is_player_or_pc_fluff(text: str) -> bool:
    s = text.strip()
    return bool(re.match(r"^(玩家|言笑|言笑笑)", s))


def is_progress_fluff_title(title: str) -> bool:
    t = title.strip()
    if len(t) < 4:
        return True
    fluff = (
        "夜局刚稳",
        "局面刚稳",
        "场子刚稳",
        "先稳住",
        "这一回合",
        "本回合",
        "剧情",
        "氛围",
    )
    return any(x in t for x in fluff)


def is_fluff_intel_line(text: str) -> bool:
    if not text or len(text) < 4:
        return True
    if is_player_or_pc_fluff(text):
        return True
    bad = (
        "成功带回",
        "带回线索",
        "获得线索",
        "玩家选择",
        "本回合事件",
        "主要行动",
        "小游戏",
        "三消",
    )
    return any(b in text for b in bad)


def filter_valid_secrets(secrets: list[PlayerSecret]) -> list[PlayerSecret]:
    """仅保留可上架道具栏的 MERGED_SECRET，去重并剔除进度废话。"""
    out: list[PlayerSecret] = []
    seen: set[str] = set()
    for s in secrets:
        if s.secret_type != SecretType.MERGED_SECRET:
            continue
        if is_progress_fluff_title(s.title) or is_fluff_intel_line(s.title):
            continue
        if is_player_or_pc_fluff(s.title):
            continue
        sid = s.id.strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(s)
    return out[-28:]


def _slug_ledger_id(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"ledger_{digest}"


def migrate_legacy_intel_string(text: str) -> PlayerSecret:
    t = text.strip()
    return PlayerSecret(
        id=_slug_ledger_id(t),
        secret_type=SecretType.MERGED_SECRET,
        title=t[:80],
        tier=2,
        generator_key=None,
        data={},
    )


def migrate_legacy_player_intel_items(data: dict[str, Any]) -> None:
    """从旧字段 player_intel_items（字符串列表）迁入 player_secrets。"""
    raw = data.get("player_intel_items")
    if not isinstance(raw, list):
        return
    data.pop("player_intel_items", None)
    existing = data.get("player_secrets")
    if not isinstance(existing, list):
        existing = []
    seen: set[str] = set()
    for x in existing:
        if isinstance(x, dict) and x.get("id"):
            seen.add(str(x["id"]))
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        ps = migrate_legacy_intel_string(item)
        if ps.id not in seen:
            existing.append(ps.model_dump(mode="json"))
            seen.add(ps.id)
    data["player_secrets"] = existing


def _find_link(db: dict[str, Any], name: str) -> dict[str, Any] | None:
    for row in db.get("character_links", []):
        if row.get("name") == name:
            return row
    return None


def _ensure_roster_data(
    secret: PlayerSecret,
    player_name: str,
    chapter_id: str,
    db: dict[str, Any],
) -> list[dict[str, Any]]:
    if secret.data.get("roster"):
        return secret.data["roster"]
    pool = list(db.get("roster_pool_by_faction", {}).get("拜月", []))
    fixed = db.get("character_links", [])
    yan = next((x for x in fixed if x.get("id") == "yan_wuqiu"), None)
    seed = _stable_seed(player_name, chapter_id, secret.id, "baiyue_roster")
    rng = random.Random(seed)
    k = rng.randint(3, 5)
    picks: list[dict[str, Any]] = []
    if yan:
        picks.append(
            {
                "name": yan["name"],
                "role": yan.get("role", "圣子"),
                "link_id": yan.get("id", "yan_wuqiu"),
            }
        )
    pool_rest = [p for p in pool if p.get("name") != (yan or {}).get("name")]
    rng.shuffle(pool_rest)
    for p in pool_rest:
        if len(picks) >= k:
            break
        picks.append(
            {
                "name": p["name"],
                "role": p.get("role", ""),
                "link_id": p.get("link_id", ""),
            }
        )
    secret.data["roster"] = picks
    secret.data["roster_seed"] = str(seed)
    return picks


def _pick_from_roster(
    roster: list[dict[str, Any]],
    player_name: str,
    secret_id: str,
    role: str,
) -> dict[str, Any]:
    if not roster:
        return {"name": "幽影", "role": "暗卫首领"}
    seed = _stable_seed(player_name, secret_id, role, "pick")
    rng = random.Random(seed)
    # 不选圣子当受害者，优先执事、暗卫
    pool = [r for r in roster if "圣子" not in str(r.get("role", ""))]
    use = pool or roster
    return dict(rng.choice(use))


class SecretContentGenerator:
    """根据秘辛 id / generator_key 与存档种子生成正文（模板字符串）。"""

    @staticmethod
    def build_body(
        secret: PlayerSecret,
        *,
        player_name: str,
        chapter_id: str,
        all_secrets: list[PlayerSecret],
    ) -> str:
        db = load_game_database()
        gk = secret.generator_key or ""
        defs = db.get("secret_definitions", {}).get(secret.id, {})
        tier = secret.tier

        if gk == "baiyue_roster" or secret.id == "secret_baiyue_roster":
            roster = _ensure_roster_data(secret, player_name, chapter_id, db)
            lines: list[str] = [
                "封蜡笺角有朱笔小批，所录乃拜月赴会弟子之职名。今夜若有人对不上号，便是破绽。",
                "",
                "—— 名录 ——",
            ]
            for row in roster:
                link = _find_link(db, row["name"]) or {}
                snippet = link.get("bio_snippet", "案头未详。")
                lines.append(f"· {row['name']} —— {row['role']}。{snippet}")
            lines.append("")
            lines.append(f"（情报等级 Lv.{tier}，笺上笔迹与听风阁旧档可互证。）")
            return "\n".join(lines)

        if gk == "sect_entry_notice":
            fac = defs.get("faction") or secret.data.get("faction") or "邪派"
            roster_secret = next(
                (s for s in all_secrets if s.id == "secret_baiyue_roster" and s.data.get("roster")),
                None,
            )
            extra = ""
            if fac == "拜月" and roster_secret and roster_secret.data.get("roster"):
                names = "、".join(r["name"] for r in roster_secret.data["roster"][:4])
                extra = f"\n与阁中另册「拜月教赴会弟子名录」互参，前列诸名：{names}。"
            return (
                f"「{secret.title}」\n\n"
                f"武林大会客席异动：{fac}一脉已列今届名录，非虚报。各派眼线多已动身，听风阁宜早定要价。\n"
                f"此事牵动正邪席次，等级 Lv.{tier}。{extra}"
            ).strip()

        if gk == "baiyue_intrigue" or secret.id == "secret_baiyue_intrigue":
            roster_src = next(
                (s for s in all_secrets if s.id == "secret_baiyue_roster"),
                None,
            )
            roster = (roster_src.data.get("roster") if roster_src else []) or []
            victim = _pick_from_roster(roster, player_name, secret.id, "victim")
            leader = _pick_from_roster(roster, player_name, secret.id, "leader")
            if victim["name"] == leader["name"] and len(roster) > 1:
                leader = next((r for r in roster if r["name"] != victim["name"]), leader)
            vlink = _find_link(db, victim["name"]) or {}
            llink = _find_link(db, leader["name"]) or {}
            return (
                f"「{secret.title}」\n\n"
                f"风闻拜月内部已分两势：一方以「{leader['name']}」（{leader.get('role','')}）为首施压席次；"
                f"另一方则疑「{victim['name']}」（{victim.get('role','')}）泄密于外，已遭软禁问话。\n\n"
                f"与先前置信名录对照：{victim['name']}确在赴会册上——{vlink.get('bio_snippet','案头语焉不详。')}\n"
                f"领头争势者亦在册——{llink.get('bio_snippet','')}\n\n"
                f"（Lv.{tier} 秘辛，后续若得「魔教调令」类物证，可再验领头人笔迹。）"
            )

        if gk == "mojiao_order" or secret.id == "secret_mojiao_order":
            roster_src = next((s for s in all_secrets if s.id == "secret_baiyue_roster"), None)
            roster = (roster_src.data.get("roster") if roster_src else []) or []
            signer = _pick_from_roster(roster, player_name, secret.id, "signer")
            slink = _find_link(db, signer["name"]) or {}
            return (
                f"「{secret.title}」\n\n"
                f"密令残简署押与「{signer['name']}」（{signer.get('role','')}）职权相合；"
                f"此人亦见于先前置信之拜月名录。\n"
                f"{slink.get('bio_snippet','')}\n\n"
                f"令文调遣暗线截听风阁外送之信，等级 Lv.{tier}；与「内斗风声」并读，可知谁在下令、谁在背锅。"
            )

        # 动态对白秘辛（无专用 generator）
        return (
            f"「{secret.title}」\n\n"
            f"此条来自席间明确点名的要紧话，已剔去场面铺陈。\n"
            f"（情报等级 Lv.{tier}）"
        )


def classify_ledger_line(text: str) -> SecretType:
    raw = text.strip()
    if is_fluff_intel_line(raw) or is_progress_fluff_title(raw):
        return SecretType.STORY_LOG
    if is_player_or_pc_fluff(raw):
        return SecretType.STORY_LOG
    # 极短且无实体多作剧情日志
    if len(raw) <= 6 and not re.search(r"[教派门会盟]", raw):
        return SecretType.STORY_LOG
    return SecretType.MERGED_SECRET


def try_bind_ledger_to_secret(text: str, db: dict[str, Any]) -> PlayerSecret | None:
    raw = text.strip()
    for bind in db.get("ledger_bindings", []):
        keys = bind.get("match") or []
        if keys and all(k in raw for k in keys):
            sid = bind.get("secret_id")
            if not sid:
                continue
            defn = db.get("secret_definitions", {}).get(sid)
            if not defn:
                continue
            return PlayerSecret(
                id=sid,
                secret_type=SecretType.MERGED_SECRET,
                title=str(defn.get("title", sid)),
                tier=int(defn.get("tier", 4)),
                generator_key=str(defn.get("generator_key", "")),
                data={"faction": defn.get("faction", "")},
            )
    return None


def ledger_line_to_secret(text: str) -> PlayerSecret | None:
    """将一条对白 intel 转为秘辛对象；无法绑定则生成动态 MERGED。"""
    raw = text.strip()
    if classify_ledger_line(raw) != SecretType.MERGED_SECRET:
        return None
    db = load_game_database()
    bound = try_bind_ledger_to_secret(raw, db)
    if bound:
        return bound
    return PlayerSecret(
        id=_slug_ledger_id(raw),
        secret_type=SecretType.MERGED_SECRET,
        title=raw[:72],
        tier=2,
        generator_key=None,
        data={"source_line": raw},
    )


def apply_intel_ledger_to_state(state: Any, payload: dict[str, Any]) -> None:
    secrets, logs = merge_intel_ledger_into_state(
        list(state.player_secrets),
        list(state.story_logs),
        payload.get("intel_ledger"),
    )
    state.player_secrets = secrets
    state.story_logs = logs


def materialize_roster_for_secrets(
    secrets: list[PlayerSecret],
    player_name: str,
    chapter_id: str,
) -> None:
    db = load_game_database()
    pn = (player_name or "掌柜").strip()
    for s in secrets:
        if s.id == "secret_baiyue_roster" and not s.data.get("roster"):
            _ensure_roster_data(s, pn, chapter_id, db)


def merge_intel_ledger_into_state(
    player_secrets: list[PlayerSecret],
    story_logs: list[str],
    ledger: list[Any],
) -> tuple[list[PlayerSecret], list[str]]:
    if not isinstance(ledger, list):
        return player_secrets, story_logs
    secrets = list(player_secrets)
    logs = list(story_logs)
    seen_ids = {s.id for s in secrets}
    for item in ledger[:6]:
        raw = str(item).strip()
        if len(raw) < 4 or len(raw) > 80:
            continue
        st = classify_ledger_line(raw)
        if st == SecretType.STORY_LOG:
            if raw not in logs:
                logs.append(raw)
            logs = logs[-40:]
            continue
        ps = ledger_line_to_secret(raw)
        if ps and ps.id not in seen_ids:
            secrets.append(ps)
            seen_ids.add(ps.id)
    return secrets, logs


def append_definition_secrets(
    secrets: list[PlayerSecret],
    *definition_ids: str,
) -> list[PlayerSecret]:
    db = load_game_database()
    defs = db.get("secret_definitions", {})
    seen = {s.id for s in secrets}
    out = list(secrets)
    for did in definition_ids:
        if did in seen:
            continue
        d = defs.get(did)
        if not d:
            continue
        out.append(
            PlayerSecret(
                id=did,
                secret_type=SecretType.MERGED_SECRET,
                title=str(d["title"]),
                tier=int(d.get("tier", 3)),
                generator_key=d.get("generator_key"),
                data={"faction": d.get("faction", "")},
            )
        )
        seen.add(did)
    return out


def sale_summary_for_ai(secret: PlayerSecret, player_name: str, chapter_id: str, all_secrets: list[PlayerSecret]) -> str:
    body = SecretContentGenerator.build_body(
        secret,
        player_name=player_name,
        chapter_id=chapter_id,
        all_secrets=all_secrets,
    )
    return f"{secret.title}\n{body[:400]}"


def remove_secret_by_id(secrets: list[PlayerSecret], secret_id: str) -> list[PlayerSecret]:
    return [s for s in secrets if s.id != secret_id]


def get_merged_for_client(secrets: list[PlayerSecret]) -> list[PlayerSecret]:
    return filter_valid_secrets(secrets)
