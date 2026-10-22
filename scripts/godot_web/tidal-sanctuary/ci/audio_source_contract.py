"""Historical source/bus contracts for genuine audio-thread PCM receipts.

This intentionally supports the shipped simple cue graph, not arbitrary Web
Audio automation. It never assigns present-day graph state to older PCM.
"""
from __future__ import annotations

import math

from audio_thread import meter_stream, pcm_interval, pcm_signal


_CUES = {"chart_read": .72, "key_pickup": 1.05,
         "pearl_pickup": 1.65, "beacon_resolve": 4.8}
_LIMIT = 4096


def _number(value, label, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError("Invalid source-contract " + label)
    return value


def _identifier(value, label):
    if type(value) is not int or value < 1:
        raise ValueError("Invalid source-contract " + label)
    return value


def _history(snapshot, field, context, nodes):
    records = snapshot.get(field)
    if not isinstance(records, list) or not records or len(records) > _LIMIT:
        raise ValueError("Missing or unbounded " + field)
    clock = _number(context.get("context_time"), "context clock")
    wall = _number(snapshot.get("wall_ms"), "snapshot wall clock")
    previous_clock = previous_wall = -1
    for index, event in enumerate(records, 1):
        if (not isinstance(event, dict) or type(event.get("sequence")) is not int
                or event["sequence"] != index or event.get("context") != context["id"]
                or type(event.get("context")) is not int):
            raise ValueError("Incomplete or cross-context " + field)
        at = _number(event.get("context_time"), field + " clock")
        at_wall = _number(event.get("wall_ms"), field + " wall clock")
        if at < previous_clock or at_wall < previous_wall or at > clock or at_wall > wall:
            raise ValueError("Nonchronological " + field)
        previous_clock, previous_wall = at, at_wall
        identifiers = ("node",) if field == "gain_events" else ("from", "to")
        for key in identifiers:
            if _identifier(event.get(key), field + " node") not in nodes:
                raise ValueError("Unknown node in " + field)
    return records


def _edge(item):
    for field in ("output", "input"):
        if type(item.get(field)) is not int or item[field] < 0:
            raise ValueError("Invalid observed graph port")
    return (item["from"], item["to"], item["output"], item["input"])


def _graph_during(snapshot, context, nodes, path, begin, end):
    """Replay the event log; the final edge list is only a consistency check."""
    events = _history(snapshot, "graph_events", context, nodes)
    active, at_begin = set(), set()
    source, bus, master, destination = path
    relevant = {source, bus, master}
    for event in events:
        edge = _edge(event)
        action = event.get("event")
        if action == "connect":
            if edge in active:
                raise ValueError("Duplicate graph connect history")
            active.add(edge)
        elif action == "disconnect":
            if edge not in active:
                raise ValueError("Graph disconnect lacks its original connect")
            active.remove(edge)
        else:
            raise ValueError("Unsupported graph history event")
        at = event["context_time"]
        if at <= begin:
            at_begin = set(active)
        elif at < end and (edge[0] in relevant or edge[1] in relevant
                           or edge[1] == destination):
            # Even disconnect/reconnect at one audio-clock value is a real
            # topology change. Never erase it with the final graph snapshot.
            raise ValueError("Source destination graph changed during its lifetime")
    current = snapshot.get("edges")
    if not isinstance(current, list) or len(current) > _LIMIT:
        raise ValueError("Missing bounded graph snapshot")
    current_active = set()
    for item in current:
        if not isinstance(item, dict) or type(item.get("active")) is not bool:
            raise ValueError("Malformed graph snapshot")
        if any(_identifier(item.get(key), "edge node") not in nodes for key in ("from", "to")):
            raise ValueError("Unknown graph snapshot node")
        edge = _edge(item)
        if item["active"]:
            if edge in current_active:
                raise ValueError("Duplicate live graph edge")
            current_active.add(edge)
    if current_active != active:
        raise ValueError("Graph history does not account for the actual edge snapshot")

    expected = {(source, bus, 0, 0), (bus, master, 0, 0), (master, destination, 0, 0)}
    if not expected <= at_begin:
        raise ValueError("Source lacks its complete genuine destination path")
    for node, target in ((source, bus), (bus, master), (master, destination)):
        if {edge for edge in at_begin if edge[0] == node} != {(node, target, 0, 0)}:
            raise ValueError("Source path has an ambiguous or unsupported outgoing edge")
    if {edge for edge in at_begin if edge[1] == bus} != {(source, bus, 0, 0)}:
        raise ValueError("Cue bus has a competing or unsupported input")
    master_inputs = [edge for edge in at_begin if edge[1] == master]
    if (len(master_inputs) != 2 or any(nodes[edge[0]] != "GainNode" or edge[2:] != (0, 0)
                                      for edge in master_inputs)):
        raise ValueError("Master does not retain its two genuine simple gain buses")
    if {edge for edge in at_begin if edge[1] == destination} != {(master, destination, 0, 0)}:
        raise ValueError("Destination has an unknown or duplicate terminal path")
    return len(events)


def _gain_during(events, node, begin, end):
    """Only default, direct-value and immediate SetValue writes are supported.

    Scheduled method arguments describe the event; a queued setValueAtTime's
    current .value is deliberately NOT substituted for that scheduled value.
    """
    records = [event for event in events if event["node"] == node]
    if (not records or records[0].get("method") != "initial"
            or sum(event.get("method") == "initial" for event in records) != 1
            or records[0]["context_time"] > begin):
        raise ValueError("Gain lacks its original complete parameter history")
    value = None
    initial_value = None
    for event in records:
        if event["context_time"] >= end:
            continue  # Later writes cannot change already-rendered PCM.
        method, args = event.get("method"), event.get("args")
        raw = _number(event.get("value"), "observed gain value", -math.inf)
        if not isinstance(args, list):
            raise ValueError("Gain event lacks original arguments")
        if method == "initial" and not args:
            next_value = raw
        elif method == "value" and len(args) == 1:
            next_value = _number(args[0], "gain assignment", -math.inf)
            if next_value != raw:
                raise ValueError("Gain assignment differs from its native observed value")
        elif method == "setValueAtTime" and len(args) == 2:
            next_value = _number(args[0], "scheduled gain", -math.inf)
            scheduled = _number(args[1], "scheduled gain time")
            if scheduled > event["context_time"]:
                raise ValueError("Future gain automation is outside the static-bus contract")
        else:
            raise ValueError("Unsupported gain automation in source destination path")
        if event["context_time"] <= begin:
            value = next_value
            initial_value = value
        elif next_value != value:
            raise ValueError("Gain changed during source lifetime")
        if event["context_time"] > begin and next_value <= 1e-6:
            raise ValueError("Source destination gain was muted during its lifetime")
    if value is None or value <= 1e-6:
        raise ValueError("Source destination lacks an observed nonzero gain")
    return initial_value


def _source_end(source, fallback):
    values = [_number(source[key], "source lifetime") for key in
              ("planned_end", "stopped_context_time", "ended_context_time")
              if source.get(key) is not None]
    return min(values or [fallback])


def validate_source_bus(snapshot, source, context, begin, end, *, check_bus_gain=True):
    """Prove one simple source->bus->master->destination history and bus tap.

    The returned path/lifetime fields are CONTROL evidence, never PCM samples.
    Present graph/gain snapshots are not used to backfill historical metadata.
    Only music may skip bus-gain reconstruction: callers must independently
    require its actual post-bus PCM, rather than approximate its authored fade.
    """
    begin, end = _number(begin, "interval start"), _number(end, "interval end")
    if end <= begin:
        raise ValueError("Empty source-contract interval")
    if type(check_bus_gain) is not bool or (not check_bus_gain and source.get("name") != "music"):
        raise ValueError("Only measured music may omit bus-gain reconstruction")
    if (snapshot.get("errors") != [] or snapshot.get("history_overflow") is not False
            or type(snapshot.get("schema")) is not int or snapshot["schema"] != 1
            or snapshot.get("contexts") != [context]):
        raise ValueError("Missing, ambiguous or failed source graph observation")
    context_id = _identifier(context.get("id"), "context ID")
    if _number(context.get("context_time"), "context clock") < end:
        raise ValueError("Source lifetime has not actually elapsed")
    source_id = _identifier(source.get("id"), "source ID")
    source_clock = _number(source.get("context_time"), "source start observation clock")
    source_wall = _number(source.get("wall_ms"), "source start observation wall clock")
    scheduled = _number(source.get("scheduled_start"), "source scheduled start")
    # The public getter may advance one render quantum between the original
    # start call and its observation. Retain the existing two-quantum allowance;
    # do not demand an impossible atomic main-thread/audio-thread timestamp.
    if (source_clock > begin + .006 or scheduled > begin or source_wall > snapshot["wall_ms"]
            or _source_end(source, context["context_time"]) < end - .03):
        raise ValueError("Source was not observed before the required lifetime")
    starts = snapshot.get("starts")
    if (not isinstance(starts, list) or len(starts) > _LIMIT
            or [item for item in starts if isinstance(item, dict) and item.get("id") == source_id] != [source]
            or type(source.get("context")) is not int or source["context"] != context_id):
        raise ValueError("Source is absent, duplicated or belongs to another context")
    raw_nodes = snapshot.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes or len(raw_nodes) > _LIMIT:
        raise ValueError("Missing bounded observed nodes")
    nodes = {}
    for item in raw_nodes:
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str):
            raise ValueError("Malformed observed node")
        identifier = _identifier(item.get("id"), "node ID")
        if identifier in nodes:
            raise ValueError("Duplicate observed node ID")
        nodes[identifier] = item["kind"]
    start_ids = set()
    for item in starts:
        if not isinstance(item, dict):
            raise ValueError("Malformed source history")
        identifier = _identifier(item.get("id"), "started source ID")
        if (identifier in start_ids or nodes.get(identifier) != "AudioBufferSourceNode"
                or type(item.get("context")) is not int or item["context"] != context_id):
            raise ValueError("Duplicate, unknown or cross-context source history")
        start_ids.add(identifier)
    path = source.get("path_at_start")
    if (not isinstance(path, list) or len(path) != 4 or any(type(item) is not int for item in path)
            or len(set(path)) != 4 or path[0] != source_id or path[-1] != context.get("destination")
            or [nodes.get(item) for item in path] !=
            ["AudioBufferSourceNode", "GainNode", "GainNode", "AudioDestinationNode"]):
        raise ValueError("Source does not have the exact simple gain-bus path")
    _, bus, master, destination = path
    event_count = _graph_during(snapshot, context, nodes, path, begin, end)
    gain_events = _history(snapshot, "gain_events", context, nodes)
    bus_gain = _gain_during(gain_events, bus, begin, end) if check_bus_gain else None
    master_gain = _gain_during(gain_events, master, begin, end)

    for other in starts:
        if not isinstance(other, dict):
            raise ValueError("Malformed source history")
        if other.get("id") == source_id or other.get("context") != context_id:
            continue
        other_path = other.get("path_at_start")
        if isinstance(other_path, list) and bus in other_path:
            at = _number(other.get("scheduled_start"), "competing source start")
            if at < end and _source_end(other, context["context_time"]) > begin:
                raise ValueError("Competing source overlaps the cue bus lifetime")

    bus_meter, mix_meter = meter_stream(context, bus), meter_stream(context)
    taps = source.get("meter_taps")
    if not isinstance(taps, list) or len(taps) != 2 or any(not isinstance(item, dict) for item in taps):
        raise ValueError("Source lacks its two original pre-armed meter bindings")
    for meter, tap_source, role in ((bus_meter, bus, "bus"), (mix_meter, None, "mix")):
        tap_id = meter.get("tap_id")
        matching = [item for item in taps if item.get("source") == tap_source and item.get("role") == role]
        if (not isinstance(tap_id, str) or not tap_id or len(matching) != 1
                or matching[0].get("tap_id") != tap_id or meter.get("source") != tap_source
                or meter.get("role") != role
                or _number(meter.get("ready_context_time"), "meter ready clock") > min(source_clock, scheduled)
                or _number(meter.get("ready_wall_ms"), "meter ready wall clock") > source_wall):
            raise ValueError("Source meter was missing, ambiguous or armed after source start")
    if bus_meter["tap_id"] == mix_meter["tap_id"]:
        raise ValueError("Bus and mix PCM cannot share an observation identity")
    return {"source_id": source_id, "bus_id": bus, "master_id": master, "destination_id": destination,
            "bus_tap_id": bus_meter["tap_id"], "mix_tap_id": mix_meter["tap_id"],
            "begin_context_time": begin, "end_context_time": end,
            "bus_gain": bus_gain, "master_gain": master_gain, "graph_events_checked": event_count,
            "bus_gain_checked": check_bus_gain,
            "proof": "observed graph and parameter event history; separate from actual PCM"}


def validate_cue_pcm(snapshot, source, context):
    """Require genuine isolated cue-bus AND post-master PCM for a full cue."""
    expected = _CUES.get(source.get("name"))
    begin = _number(source.get("scheduled_start"), "cue start")
    duration = _number(source.get("duration"), "cue duration")
    offset = _number(source.get("offset"), "cue offset")
    rate = _number(source.get("rate"), "cue playback rate")
    detune = _number(source.get("detune"), "cue detune", -math.inf)
    clock = _number(context.get("context_time"), "context clock")
    end = begin + duration
    if (expected is None or abs(duration - expected) >= .005
            or offset != 0 or rate != 1 or detune != 0
            or source.get("looping") is not False or source.get("mutations") != []
            or source.get("parameter_automation") != []
            or abs(_number(source.get("planned_end"), "planned cue end") - end) > .006
            or _source_end(source, clock) < end - .03 or clock < end):
        raise ValueError("Cue did not retain its original origin, pitch and authored lifetime")
    proof = validate_source_bus(snapshot, source, context, begin, end)
    reports = {}
    for name, bus in (("bus_pcm", proof["bus_id"]), ("mix_pcm", None)):
        windows = pcm_interval(context, begin, end, max(.1, duration - .4), source=bus,
                               minimum_windows=3, edge_seconds=.2)
        rate = context["sample_rate"]
        if any((right["start_frame"] - left["start_frame"]) / rate > .25
               for left, right in zip(windows, windows[1:])):
            raise ValueError("Cue PCM lacks its original dense lifetime coverage")
        reports[name] = pcm_signal(windows, audible=True, minimum_fraction=1)
    bus_report = reports["bus_pcm"]
    return {**proof, **reports,
            "first_active_context_time": bus_report["first_frame"] / context["sample_rate"],
            "last_active_context_time": bus_report["last_frame"] / context["sample_rate"],
            "active_meter_samples": bus_report["pcm_windows"], "authored_end_context_time": end}
