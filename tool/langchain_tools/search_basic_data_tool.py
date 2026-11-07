"""football-data.org 的基础足球数据工具。

免费层适合主流赛事的赛程、赛果、积分榜和球队阵容。
所有 Tool 都先把供应商数据转换成统一的简洁 JSON，再交给 Agent。
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Literal

import requests
from langchain_core.tools import tool

from tool.shared.data_models import build_tool_error, build_tool_success
from tool.shared.sqlite_cache import SqliteTtlCache, make_cache_key


class FootballDataError(Exception):
    """football-data.org 的配置、网络或响应错误。"""


# 这些是 football-data.org 免费层覆盖的主流赛事代码。
COMPETITION_ALIASES = {
    "pl": "PL",
    "premier league": "PL",
    "英超": "PL",
    "pd": "PD",
    "la liga": "PD",
    "西甲": "PD",
    "bl1": "BL1",
    "bundesliga": "BL1",
    "德甲": "BL1",
    "sa": "SA",
    "serie a": "SA",
    "意甲": "SA",
    "fl1": "FL1",
    "ligue 1": "FL1",
    "法甲": "FL1",
    "cl": "CL",
    "champions league": "CL",
    "欧冠": "CL",
    "ppl": "PPL",
    "primeira liga": "PPL",
    "葡超": "PPL",
    "ded": "DED",
    "eredivisie": "DED",
    "荷甲": "DED",
    "elc": "ELC",
    "championship": "ELC",
    "英冠": "ELC",
    "bsa": "BSA",
    "campeonato brasileiro série a": "BSA",
    "巴甲": "BSA",
}


def cache_ttl_seconds(endpoint: str) -> int:
    """按足球数据的变化速度，为不同接口选择合适的缓存时间。"""
    # 阵容和球队清单变化较慢；积分榜和赛程可能受补赛、延期影响，缓存时间更短。
    normalized_endpoint = endpoint.strip("/")
    if normalized_endpoint.endswith("/standings"):
        return 15 * 60
    if normalized_endpoint.endswith("/matches"):
        return 10 * 60
    if normalized_endpoint.startswith("competitions/") and normalized_endpoint.endswith("/teams"):
        return 24 * 60 * 60
    if normalized_endpoint.startswith("teams/"):
        return 6 * 60 * 60
    return 30 * 60


class FootballDataClient:
    """封装 football-data.org 的认证、网络请求和错误处理。"""

    def __init__(self) -> None:
        """从 .env 读取服务地址和 API Key，并创建可复用 HTTP 会话。"""
        # 地址不写死在 Tool 内，未来替换供应商或网关时只需改 .env。
        self.base_url = os.getenv("FOOTBALL_DATA_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("FOOTBALL_DATA_API_KEY")
        self.session = requests.Session()
        self.cache = SqliteTtlCache()

    def get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        """向 football-data.org 发 GET 请求，并返回完整 JSON 对象。"""
        # 在实际请求前验证配置，防止示例 Key 被误用于网络调用。
        if not self.api_key or self.api_key == "你的_football_data_Key":
            raise FootballDataError("尚未配置 FOOTBALL_DATA_API_KEY，无法查询足球数据。")
        if not self.base_url:
            raise FootballDataError("尚未配置 FOOTBALL_DATA_BASE_URL，无法查询足球数据。")

        # Endpoint 与实际请求参数共同决定缓存键，避免不同赛事或日期范围错误复用结果。
        clean_params = {key: value for key, value in params.items() if value is not None}
        cache_key = make_cache_key(
            "football-data.org", {"endpoint": endpoint.lstrip("/"), "params": clean_params}
        )
        cached_payload = self.cache.get(cache_key)
        if cached_payload is not None:
            return cached_payload

        # football-data.org 使用 X-Auth-Token 作为请求头中的认证字段。
        response = self.session.get(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            headers={"X-Auth-Token": self.api_key},
            params=clean_params,
            timeout=15,
        )
        # HTTP 401、403、429、500 等失败会在这里变成异常。
        response.raise_for_status()
        payload = response.json()
        # 仅缓存成功 JSON；失败响应绝不写入缓存，避免短暂故障被持续放大。
        self.cache.set(cache_key, payload, cache_ttl_seconds(endpoint))
        return payload


client = FootballDataClient()


def tool_result(data: dict[str, Any]) -> str:
    """把成功或失败的数据统一编码为 Agent 易读的 JSON 文本。"""
    # 保留中文并缩进，便于模型读取以及开发时查看日志。
    return json.dumps(data, ensure_ascii=False, indent=2)


def tool_error(error: Exception) -> str:
    """将异常转换为结构化 Tool 错误，避免让整个 Agent 流程中断。"""
    # 失败结果也遵守统一契约，后续路由和日志不必额外判断字段结构。
    return tool_result(build_tool_error(source="football-data.org", error=error))


def ensure_date(value: str | None, argument_name: str) -> None:
    """校验可选日期是否符合 API 所需的 YYYY-MM-DD 格式。"""
    # 日期不传是合法情况，由调用方的默认时间范围处理。
    if value is None:
        return
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError(f"{argument_name} 必须是 YYYY-MM-DD 格式。") from error


def normalize(value: str) -> str:
    """标准化名称，用于消除大小写、空格和标点带来的匹配差异。"""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def resolve_competition(competition: str) -> str:
    """把中文赛事名、英文赛事名或官方代码转换为官方赛事代码。"""
    # 未命中别名时允许直接传官方代码，例如 PL、PD、BL1。
    return COMPETITION_ALIASES.get(competition.strip().lower(), competition.strip().upper())


@lru_cache(maxsize=16)
def competition_teams(competition_code: str) -> list[dict[str, Any]]:
    """读取指定赛事的球队列表，并在当前进程内缓存以节约免费额度。"""
    # Team 列表是球队名称解析的来源；缓存避免每一次 Tool 调用都重复请求。
    payload = client.get(f"competitions/{competition_code}/teams")
    return payload.get("teams", [])


def resolve_team(team_name: str, competition: str) -> dict[str, Any] | None:
    """在指定赛事内按球队名称定位唯一 team id。"""
    competition_code = resolve_competition(competition)
    requested_name = normalize(team_name)
    teams = competition_teams(competition_code)

    # 依次比较全名、简称和三字母缩写，降低模型转写名称的失败概率。
    for team in teams:
        candidates = [team.get("name", ""), team.get("shortName", ""), team.get("tla", "")]
        if requested_name in {normalize(candidate) for candidate in candidates if candidate}:
            return team
    return None


def compact_team(team: dict[str, Any]) -> dict[str, Any]:
    """裁剪球队原始数据，只保留后续查询和展示所需字段。"""
    return {
        "id": team.get("id"),
        "name": team.get("name"),
        "short_name": team.get("shortName"),
        "code": team.get("tla"),
        "area": team.get("area", {}).get("name"),
        "founded": team.get("founded"),
        "venue": team.get("venue"),
        "crest": team.get("crest"),
    }


def compact_match(match: dict[str, Any]) -> dict[str, Any]:
    """把比赛原始对象转换为赛程/赛果回答所需的统一结构。"""
    score = match.get("score", {})
    full_time = score.get("fullTime", {})
    return {
        "match_id": match.get("id"),
        "utc_date": match.get("utcDate"),
        "status": match.get("status"),
        "competition": match.get("competition", {}).get("name"),
        "matchday": match.get("matchday"),
        "home": match.get("homeTeam", {}).get("name"),
        "away": match.get("awayTeam", {}).get("name"),
        "score": {"home": full_time.get("home"), "away": full_time.get("away")},
    }


@tool
def search_team(team_name: str, competition: str) -> str:
    """在指定赛事中查询球队基本资料与稳定 ID。

    competition 可传英超/PL、西甲/PD、德甲/BL1、意甲/SA、法甲/FL1、欧冠/CL 等。
    """
    try:
        # 先转换赛事别名，再通过赛事球队列表定位目标球队。
        competition_code = resolve_competition(competition)
        team = resolve_team(team_name, competition_code)
        return tool_result(
            build_tool_success(
                source="football-data.org",
                freshness="recent",
                confidence="high",
                data={
                "competition": competition_code,
                "team": compact_team(team) if team else None,
                "message": None if team else "未在该赛事当前球队列表中找到目标球队。",
                },
                warnings=[] if team else ["球队名称仅在该赛事的当前球队列表中匹配。"],
            )
        )
    except Exception as error:
        return tool_error(error)


@tool
def get_team_fixtures(
    team_name: str,
    competition: str,
    status: Literal["upcoming", "finished", "live", "all"] = "all",
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """查询球队在指定赛事中的未来赛程、已结束赛果或进行中比赛。

    date_from/date_to 格式为 YYYY-MM-DD；未提供时默认查今天前后各 180 天。
    football-data.org 返回 UTC 时间，最终回答时应明确时区。
    """
    try:
        ensure_date(date_from, "date_from")
        ensure_date(date_to, "date_to")
        competition_code = resolve_competition(competition)
        team = resolve_team(team_name, competition_code)
        if not team:
            return tool_result(build_tool_success(
                source="football-data.org", freshness="unknown", confidence="low",
                data={"matches": [], "message": "未找到球队。"},
                warnings=["无法确认球队名称，因此没有查询到赛程。"],
            ))

        # 免费层按日期查询；默认范围兼顾近期赛果与未来赛程。
        today = datetime.now(timezone.utc).date()
        payload = client.get(
            f"teams/{team['id']}/matches",
            dateFrom=date_from or (today - timedelta(days=180)).isoformat(),
            dateTo=date_to or (today + timedelta(days=180)).isoformat(),
            competitions=competition_code,
        )
        matches = payload.get("matches", [])
        status_groups = {
            "upcoming": {"SCHEDULED", "TIMED", "POSTPONED"},
            "finished": {"FINISHED", "AWARDED"},
            "live": {"IN_PLAY", "PAUSED"},
        }
        # 接口的状态过滤在不同套餐/端点间能力不同，因此本地再次保证筛选语义。
        if status in status_groups:
            matches = [match for match in matches if match.get("status") in status_groups[status]]

        return tool_result(
            build_tool_success(
                source="football-data.org",
                freshness="recent" if status != "live" else "realtime",
                confidence="high",
                data={
                "team": compact_team(team),
                "competition": competition_code,
                "time_basis": "UTC",
                "matches": [compact_match(match) for match in matches],
                },
                warnings=["赛程时间为 UTC；免费数据源的实时状态可能存在延迟。"] if status == "live" else [],
            )
        )
    except Exception as error:
        return tool_error(error)


@tool
def get_team_squad(team_name: str, competition: str) -> str:
    """查询指定赛事中的球队当前阵容，返回姓名、位置、球衣号码和国籍。"""
    try:
        # 先通过赛事球队列表取得 team id，再读取单支球队完整资料和 squad。
        competition_code = resolve_competition(competition)
        team = resolve_team(team_name, competition_code)
        if not team:
            return tool_result(build_tool_success(
                source="football-data.org", freshness="unknown", confidence="low",
                data={"players": [], "message": "未找到球队。"},
                warnings=["无法确认球队名称，因此没有查询到阵容。"],
            ))
        payload = client.get(f"teams/{team['id']}")
        squad = payload.get("squad", [])
        return tool_result(
            build_tool_success(
                source="football-data.org",
                freshness="recent",
                confidence="high",
                data={
                "team": compact_team(payload),
                "players": [
                    {
                        "id": player.get("id"),
                        "name": player.get("name"),
                        "position": player.get("position"),
                        "shirt_number": player.get("shirtNumber"),
                        "nationality": player.get("nationality"),
                        "date_of_birth": player.get("dateOfBirth"),
                    }
                    for player in squad
                    if player.get("role") == "PLAYER"
                ],
                },
                warnings=["阵容为当前 API 返回结果，转会窗口期间可能与俱乐部即时公告有短暂差异。"],
            )
        )
    except Exception as error:
        return tool_error(error)


@tool
def search_player(player_name: str, team_name: str, competition: str) -> str:
    """在已知球队和赛事范围内查找球员，避免免费层无法全库搜索球员的问题。"""
    try:
        # 复用球队名单查询，之后只保留名称包含用户输入的候选球员。
        team = resolve_team(team_name, resolve_competition(competition))
        if not team:
            return tool_result(build_tool_success(
                source="football-data.org", freshness="unknown", confidence="low",
                data={"players": []},
                warnings=["无法确认球队名称，因此没有查询到球员。"],
            ))
        squad = client.get(f"teams/{team['id']}").get("squad", [])
        requested_name = normalize(player_name)
        candidates = [
            player
            for player in squad
            if requested_name in normalize(player.get("name", ""))
        ]
        return tool_result(
            build_tool_success(
                source="football-data.org",
                freshness="recent",
                confidence="high",
                data={
                "team": compact_team(team),
                "players": [
                    {
                        "id": player.get("id"),
                        "name": player.get("name"),
                        "position": player.get("position"),
                        "shirt_number": player.get("shirtNumber"),
                        "nationality": player.get("nationality"),
                    }
                    for player in candidates
                ],
                },
                warnings=["球员搜索仅在该球队当前阵容内进行。"],
            )
        )
    except Exception as error:
        return tool_error(error)


@tool
def get_player_profile(player_name: str, team_name: str, competition: str) -> str:
    """查询某球队范围内球员的基础资料、位置、号码和国籍。

    该免费数据源不提供可靠的全库球员检索，因此 team_name 和 competition 是必填参数。
    """
    try:
        # 在球队当前 squad 中匹配球员，避免同名球员被错误识别。
        team = resolve_team(team_name, resolve_competition(competition))
        if not team:
            return tool_result(build_tool_error(
                source="football-data.org", error="未找到球队。",
                warnings=["请核对球队名称与赛事范围。"],
            ))
        squad = client.get(f"teams/{team['id']}").get("squad", [])
        requested_name = normalize(player_name)
        exact_match = next(
            (player for player in squad if normalize(player.get("name", "")) == requested_name), None
        )
        if not exact_match:
            candidates = [player.get("name") for player in squad if requested_name in normalize(player.get("name", ""))]
            return tool_result(
                build_tool_error(
                    source="football-data.org",
                    error="未找到精确匹配球员，请补充或修正姓名。",
                    data={"candidates": candidates},
                    warnings=["候选姓名已放在 data.candidates 中。"],
                )
            )
        return tool_result(
            build_tool_success(
                source="football-data.org",
                freshness="recent",
                confidence="high",
                data={
                "team": compact_team(team),
                "player": {
                    "id": exact_match.get("id"),
                    "name": exact_match.get("name"),
                    "position": exact_match.get("position"),
                    "shirt_number": exact_match.get("shirtNumber"),
                    "date_of_birth": exact_match.get("dateOfBirth"),
                    "nationality": exact_match.get("nationality"),
                    "country_of_birth": exact_match.get("countryOfBirth"),
                },
                },
                warnings=["球员资料来自当前球队阵容，非全库历史档案。"],
            )
        )
    except Exception as error:
        return tool_error(error)


@tool
def get_league_standings(competition: str) -> str:
    """查询免费覆盖赛事的当前积分榜，例如英超/PL、欧冠/CL、德甲/BL1。"""
    try:
        # standings 响应可能包含总榜、主场榜和客场榜；优先取总榜 TOTAL。
        competition_code = resolve_competition(competition)
        payload = client.get(f"competitions/{competition_code}/standings")
        all_standings = payload.get("standings", [])
        total_table = next(
            (standing.get("table", []) for standing in all_standings if standing.get("type") == "TOTAL"),
            [],
        )
        return tool_result(
            build_tool_success(
                source="football-data.org",
                freshness="recent",
                confidence="high",
                data={
                "competition": payload.get("competition", {}).get("name", competition_code),
                "season": payload.get("season", {}).get("startDate"),
                "standings": [
                    {
                        "rank": item.get("position"),
                        "team": item.get("team", {}).get("name"),
                        "played": item.get("playedGames"),
                        "won": item.get("won"),
                        "draw": item.get("draw"),
                        "lost": item.get("lost"),
                        "goals_for": item.get("goalsFor"),
                        "goals_against": item.get("goalsAgainst"),
                        "goal_difference": item.get("goalDifference"),
                        "points": item.get("points"),
                        "form": item.get("form"),
                    }
                    for item in total_table
                ],
                },
                warnings=["积分榜为请求时 API 返回的当前赛季数据。"],
            )
        )
    except Exception as error:
        return tool_error(error)


# Agent 只需导入这一份列表；新增 Tool 时也在此处集中注册。
BASIC_DATA_TOOLS = [
    search_team,
    get_team_fixtures,
    get_team_squad,
    search_player,
    get_player_profile,
    get_league_standings,
]
