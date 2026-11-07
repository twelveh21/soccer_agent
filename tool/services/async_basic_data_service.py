"""供 LangGraph 节点调用的异步足球基础数据业务方法。"""

from __future__ import annotations

import asyncio
from typing import Any

from tool.clients.async_football_data_client import AsyncFootballDataClient, AsyncFootballDataError
from tool.shared.data_models import build_tool_error, build_tool_success


def normalize_competition_code(competition_code: str) -> str:
    """规范化官方赛事代码，例如 pl 会转为 PL。"""
    # 异步服务先只接收官方代码；中文赛事别名仍由现有 LangChain Tool 负责解析。
    normalized = competition_code.strip().upper()
    if not normalized:
        raise ValueError("competition_code 不能为空，例如 PL、PD、BL1 或 CL。")
    return normalized


def compact_standings(payload: dict[str, Any]) -> tuple[str, str | None, list[dict[str, Any]]]:
    """从积分榜 API 原始响应中提取联赛名、赛季和总积分榜。"""
    # 接口可能同时返回总榜、主场榜和客场榜；此处只保留最常用的 TOTAL 总榜。
    all_standings = payload.get("standings", [])
    total_table = next(
        (standing.get("table", []) for standing in all_standings if standing.get("type") == "TOTAL"),
        [],
    )
    competition_name = payload.get("competition", {}).get("name", "未知赛事")
    season_start = payload.get("season", {}).get("startDate")
    standings = [
        {
            "rank": item.get("position"),
            "team": item.get("team", {}).get("name"),
            "played": item.get("playedGames"),
            "won": item.get("won"),
            "draw": item.get("draw"),
            "lost": item.get("lost"),
            "goal_difference": item.get("goalDifference"),
            "points": item.get("points"),
        }
        for item in total_table
    ]
    return competition_name, season_start, standings


def compact_teams(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从球队列表 API 原始响应中提取后续展示和二次查询所需字段。"""
    # 不保存整份原始 JSON，避免无关字段占用 Graph State 和模型上下文。
    return [
        {
            "id": team.get("id"),
            "name": team.get("name"),
            "short_name": team.get("shortName"),
            "code": team.get("tla"),
        }
        for team in payload.get("teams", [])
    ]


def build_competition_claims(
    competition_code: str,
    season_start: str | None,
    standings: list[dict[str, Any]] | None,
    teams: list[dict[str, Any]] | None,
    source_url: str,
) -> list[dict[str, Any]]:
    """把联赛概览中的关键事实转换为可跨来源比对的 claims。"""
    # claim_key 是稳定的事实标识；value 才是会随赛季或实时赛况改变的内容。
    season_key = season_start or "current"
    claims: list[dict[str, Any]] = []

    for item in standings or []:
        rank = item.get("rank")
        if rank is None:
            continue
        claims.append(
            {
                "claim_key": f"competition:{competition_code}:season:{season_key}:standing:{rank}",
                "value": {
                    "team": item.get("team"),
                    "points": item.get("points"),
                    "played": item.get("played"),
                    "goal_difference": item.get("goal_difference"),
                },
                "source_url": source_url,
            }
        )

    for item in teams or []:
        team_id = item.get("id")
        if team_id is None:
            continue
        claims.append(
            {
                "claim_key": f"competition:{competition_code}:season:{season_key}:team:{team_id}",
                "value": {
                    "name": item.get("name"),
                    "short_name": item.get("short_name"),
                    "code": item.get("code"),
                },
                "source_url": source_url,
            }
        )

    return claims


async def get_competition_overview(
    competition_code: str,
    *,
    client: AsyncFootballDataClient | None = None,
) -> dict[str, Any]:
    """并发查询一个赛事的积分榜和球队列表，并返回统一数据契约。"""
    # client 可注入到测试或未来 Graph 生命周期中；未注入时本方法自行创建并关闭客户端。
    own_client = client is None
    active_client = client or AsyncFootballDataClient()
    code = normalize_competition_code(competition_code)

    try:
        # 两个 Endpoint 互不依赖，因此用 gather 同时发出，整体耗时接近较慢的那个请求。
        standings_result, teams_result = await asyncio.gather(
            active_client.get(
                f"competitions/{code}/standings",
                ttl_seconds=15 * 60,
            ),
            active_client.get(
                f"competitions/{code}/teams",
                ttl_seconds=24 * 60 * 60,
            ),
            return_exceptions=True,
        )

        warnings: list[str] = []
        data: dict[str, Any] = {"competition_code": code}
        successful_source_count = 0
        season_start: str | None = None
        standings: list[dict[str, Any]] | None = None
        teams: list[dict[str, Any]] | None = None
        source_url = f"{active_client.base_url}/competitions/{code}"

        if isinstance(standings_result, Exception):
            warnings.append(f"积分榜查询失败：{standings_result}")
        else:
            competition_name, season_start, standings = compact_standings(standings_result)
            data.update(
                {
                    "competition": competition_name,
                    "season_start": season_start,
                    "standings": standings,
                }
            )
            successful_source_count += 1

        if isinstance(teams_result, Exception):
            warnings.append(f"球队列表查询失败：{teams_result}")
        else:
            teams = compact_teams(teams_result)
            data["teams"] = teams
            successful_source_count += 1

        if successful_source_count == 0:
            # 两个并发请求都失败时，统一返回可被 Graph 和最终回答节点理解的错误结构。
            return build_tool_error(
                source="football-data.org",
                error="积分榜和球队列表均无法取得。",
                data=data,
                warnings=warnings,
            )

        # 只成功一项时仍返回可用部分数据，但将可信度下调并向上层暴露警告。
        confidence = "high" if successful_source_count == 2 else "medium"
        if successful_source_count == 1:
            warnings.append("仅取得部分结构化数据，回答时应说明缺失部分。")

        # claims 既保留在统一 data 内，也带着来源链接，供证据核验节点比较不同数据源。
        data["claims"] = build_competition_claims(
            code,
            season_start,
            standings,
            teams,
            source_url,
        )

        return build_tool_success(
            source="football-data.org",
            source_url=source_url,
            freshness="recent",
            confidence=confidence,
            data=data,
            warnings=warnings,
        )
    except (AsyncFootballDataError, ValueError) as error:
        # 参数错误或客户端配置错误在此统一为 Tool 风格错误，而不是中断 LangGraph。
        return build_tool_error(source="football-data.org", error=error)
    finally:
        # 自行创建的 Client 必须关闭；外部传入的 Client 由调用方管理其生命周期。
        if own_client:
            await active_client.aclose()
