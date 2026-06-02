"""
calendar_server.py

MCP server exposing Odysseus calendar CRUD: list calendars, list/create/update/delete events.
Runs as a stdio subprocess; imports the DB layer directly (same pattern as memory_server).
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

server = Server("calendar")

OWNER = os.environ.get("ODYSSEUS_FALLBACK_OWNER", "owner@localhost")


def _db():
    from core.database import SessionLocal
    return SessionLocal()


def _ensure_default_calendar(db):
    from core.database import CalendarCal
    cal = db.query(CalendarCal).filter(CalendarCal.owner == OWNER).first()
    if not cal:
        cal = CalendarCal(
            id=str(uuid.uuid4()),
            owner=OWNER,
            name="Personal",
            color="#5b8abf",
            source="local",
        )
        db.add(cal)
        db.commit()
        db.refresh(cal)
    return cal


def _parse_dt(s: str) -> datetime:
    """Parse ISO or natural-language datetime string."""
    from routes.calendar_routes import _parse_dt as _cal_parse_dt
    return _cal_parse_dt(s)


def _fmt(ev) -> str:
    """Format a CalendarEvent for text output."""
    start = ev.dtstart.strftime("%Y-%m-%d %H:%M") if not ev.all_day else ev.dtstart.strftime("%Y-%m-%d")
    end   = ev.dtend.strftime("%Y-%m-%d %H:%M")   if not ev.all_day else ev.dtend.strftime("%Y-%m-%d")
    parts = [f"[{ev.uid[:8]}] {ev.summary or '(no title)'} | {start} → {end}"]
    if ev.location:
        parts.append(f"  Location: {ev.location}")
    if ev.description:
        snippet = ev.description[:100] + ("…" if len(ev.description) > 100 else "")
        parts.append(f"  Notes: {snippet}")
    if ev.rrule:
        parts.append(f"  Repeats: {ev.rrule}")
    return "\n".join(parts)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="manage_calendar",
            description=(
                "Interact with the Odysseus calendar. "
                "Actions: list_calendars, list_events, create_event, update_event, delete_event."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list_calendars", "list_events", "create_event", "update_event", "delete_event"],
                        "description": "The calendar operation to perform.",
                    },
                    # list_events
                    "start": {
                        "type": "string",
                        "description": "Start of the date range (ISO 8601 or natural language like 'today', 'next monday'). Required for list_events.",
                    },
                    "end": {
                        "type": "string",
                        "description": "End of the date range (ISO 8601 or natural language). Required for list_events.",
                    },
                    "calendar": {
                        "type": "string",
                        "description": "Filter by calendar name or ID (optional, list_events).",
                    },
                    # create_event / update_event
                    "uid": {
                        "type": "string",
                        "description": "Event UID — required for update_event and delete_event. Use the first 8 chars from list_events or the full UID.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Event title.",
                    },
                    "dtstart": {
                        "type": "string",
                        "description": "Event start (ISO 8601 or natural language). Required for create_event.",
                    },
                    "dtend": {
                        "type": "string",
                        "description": "Event end (ISO 8601 or natural language). Defaults to start + 1 hour.",
                    },
                    "all_day": {
                        "type": "boolean",
                        "description": "True for all-day events.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Event notes / description.",
                    },
                    "location": {
                        "type": "string",
                        "description": "Event location.",
                    },
                    "rrule": {
                        "type": "string",
                        "description": (
                            "Recurrence rule in RFC 5545 RRULE format. "
                            "Works with BOTH create_event and update_event. "
                            "To make an event repeat weekly pass rrule='FREQ=WEEKLY'. "
                            "Examples: weekly on Wednesday: 'FREQ=WEEKLY;BYDAY=WE', "
                            "weekly on Saturday: 'FREQ=WEEKLY;BYDAY=SA', "
                            "weekdays only: 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR', "
                            "monthly: 'FREQ=MONTHLY'. "
                            "To remove recurrence pass rrule=''."
                        ),
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID to create the event in (optional, defaults to Personal).",
                    },
                },
                "required": ["action"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "manage_calendar":
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    action = arguments.get("action", "")

    # ── list_calendars ──────────────────────────────────────────────────────
    if action == "list_calendars":
        from core.database import CalendarCal
        db = _db()
        try:
            cals = db.query(CalendarCal).filter(CalendarCal.owner == OWNER).all()
            if not cals:
                return [TextContent(type="text", text="No calendars found.")]
            lines = [f"Calendars ({len(cals)}):"]
            for c in cals:
                lines.append(f"  [{c.id}] {c.name}  color={c.color}  source={c.source}")
            return [TextContent(type="text", text="\n".join(lines))]
        finally:
            db.close()

    # ── list_events ─────────────────────────────────────────────────────────
    elif action == "list_events":
        start_s = arguments.get("start")
        end_s = arguments.get("end")
        if not start_s or not end_s:
            return [TextContent(type="text", text="Error: list_events requires 'start' and 'end'.")]
        try:
            start_dt = _parse_dt(start_s)
            end_dt = _parse_dt(end_s)
        except ValueError as e:
            return [TextContent(type="text", text=f"Error parsing dates: {e}")]

        from core.database import CalendarCal, CalendarEvent
        from sqlalchemy import or_, and_
        db = _db()
        try:
            cal_filter = arguments.get("calendar", "")
            q = db.query(CalendarEvent).join(CalendarCal).filter(
                CalendarEvent.status != "cancelled",
                CalendarCal.owner == OWNER,
                or_(
                    and_(
                        or_(CalendarEvent.rrule == "", CalendarEvent.rrule.is_(None)),
                        CalendarEvent.dtstart < end_dt,
                        CalendarEvent.dtend > start_dt,
                    ),
                    and_(
                        CalendarEvent.rrule.isnot(None),
                        CalendarEvent.rrule != "",
                        CalendarEvent.dtstart < end_dt,
                    ),
                ),
            )
            if cal_filter:
                q = q.filter(
                    or_(CalendarEvent.calendar_id == cal_filter, CalendarCal.name == cal_filter)
                )
            events = q.order_by(CalendarEvent.dtstart).all()
            if not events:
                return [TextContent(type="text", text=f"No events found between {start_s} and {end_s}.")]
            lines = [f"Events ({len(events)}):"]
            for ev in events:
                lines.append(_fmt(ev))
            return [TextContent(type="text", text="\n\n".join(lines))]
        finally:
            db.close()

    # ── create_event ─────────────────────────────────────────────────────────
    elif action == "create_event":
        summary = arguments.get("summary", "").strip()
        dtstart_s = arguments.get("dtstart", "").strip()
        if not summary:
            return [TextContent(type="text", text="Error: 'summary' is required for create_event.")]
        if not dtstart_s:
            return [TextContent(type="text", text="Error: 'dtstart' is required for create_event.")]
        try:
            dtstart = _parse_dt(dtstart_s)
        except ValueError as e:
            return [TextContent(type="text", text=f"Error parsing dtstart: {e}")]

        all_day = bool(arguments.get("all_day", False))
        dtend_s = arguments.get("dtend", "")
        if dtend_s:
            try:
                dtend = _parse_dt(dtend_s)
            except ValueError as e:
                return [TextContent(type="text", text=f"Error parsing dtend: {e}")]
        elif all_day:
            dtend = dtstart + timedelta(days=1)
        else:
            dtend = dtstart + timedelta(hours=1)

        from core.database import CalendarCal, CalendarEvent
        db = _db()
        try:
            cal_id = arguments.get("calendar_id", "")
            if cal_id:
                cal = db.query(CalendarCal).filter(CalendarCal.id == cal_id, CalendarCal.owner == OWNER).first()
                if not cal:
                    return [TextContent(type="text", text=f"Error: calendar '{cal_id}' not found.")]
            else:
                cal = _ensure_default_calendar(db)

            ev = CalendarEvent(
                uid=str(uuid.uuid4()),
                calendar_id=cal.id,
                summary=summary,
                description=arguments.get("description", ""),
                location=arguments.get("location", ""),
                dtstart=dtstart,
                dtend=dtend,
                all_day=all_day,
                is_utc=False,
                rrule=arguments.get("rrule", "") or "",
            )
            db.add(ev)
            db.commit()
            start_fmt = dtstart.strftime("%Y-%m-%d %H:%M") if not all_day else dtstart.strftime("%Y-%m-%d")
            return [TextContent(type="text", text=f"Created event '{summary}' on {start_fmt} (uid: {ev.uid}).")]
        except Exception as e:
            db.rollback()
            return [TextContent(type="text", text=f"Error creating event: {e}")]
        finally:
            db.close()

    # ── update_event ─────────────────────────────────────────────────────────
    elif action == "update_event":
        uid = arguments.get("uid", "").strip()
        if not uid:
            return [TextContent(type="text", text="Error: 'uid' is required for update_event.")]

        from core.database import CalendarCal, CalendarEvent
        db = _db()
        try:
            # Support partial UID match (first 8 chars shown in list_events)
            ev = db.query(CalendarEvent).join(CalendarCal).filter(
                CalendarCal.owner == OWNER,
                or_(CalendarEvent.uid == uid, CalendarEvent.uid.like(f"{uid}%")),
            ).first()
            if not ev:
                return [TextContent(type="text", text=f"Error: event '{uid}' not found.")]

            if arguments.get("summary") is not None:
                ev.summary = arguments["summary"]
            if arguments.get("description") is not None:
                ev.description = arguments["description"]
            if arguments.get("location") is not None:
                ev.location = arguments["location"]
            if arguments.get("dtstart"):
                ev.dtstart = _parse_dt(arguments["dtstart"])
            if arguments.get("dtend"):
                ev.dtend = _parse_dt(arguments["dtend"])
            if arguments.get("all_day") is not None:
                ev.all_day = arguments["all_day"]
            if arguments.get("rrule") is not None:
                ev.rrule = arguments["rrule"]
            db.commit()
            return [TextContent(type="text", text=f"Updated event '{ev.summary}' (uid: {ev.uid}).")]
        except Exception as e:
            db.rollback()
            return [TextContent(type="text", text=f"Error updating event: {e}")]
        finally:
            db.close()

    # ── delete_event ─────────────────────────────────────────────────────────
    elif action == "delete_event":
        uid = arguments.get("uid", "").strip()
        if not uid:
            return [TextContent(type="text", text="Error: 'uid' is required for delete_event.")]

        from core.database import CalendarCal, CalendarEvent
        from sqlalchemy import or_
        db = _db()
        try:
            ev = db.query(CalendarEvent).join(CalendarCal).filter(
                CalendarCal.owner == OWNER,
                or_(CalendarEvent.uid == uid, CalendarEvent.uid.like(f"{uid}%")),
            ).first()
            if not ev:
                return [TextContent(type="text", text=f"Error: event '{uid}' not found.")]
            summary = ev.summary
            db.delete(ev)
            db.commit()
            return [TextContent(type="text", text=f"Deleted event '{summary}' (uid: {uid}).")]
        except Exception as e:
            db.rollback()
            return [TextContent(type="text", text=f"Error deleting event: {e}")]
        finally:
            db.close()

    else:
        return [TextContent(type="text", text=f"Unknown action '{action}'. Use: list_calendars, list_events, create_event, update_event, delete_event.")]


async def run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run())
