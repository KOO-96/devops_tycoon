"""Typed accessors for services stored on app.state."""

from __future__ import annotations

from dataclasses import dataclass

from starlette.requests import HTTPConnection, Request

from backend.adapters.event_broker import EventBroker
from backend.application.command_service import CommandService
from backend.application.event_service import EventQueryService
from backend.application.game_session_service import GameSessionService
from backend.config import Settings


@dataclass
class Services:
    settings: Settings
    session_service: GameSessionService
    command_service: CommandService
    event_query_service: EventQueryService
    broker: EventBroker


def get_services(connection: HTTPConnection) -> Services:
    services: Services = connection.app.state.services
    return services


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")
