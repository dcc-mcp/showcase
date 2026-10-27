"""Fail-closed validation of real AudioWorklet PCM; never creates sample evidence."""
from __future__ import annotations
import math

QUIET_RMS = 1e-5
AUDIBLE_RMS = 1e-4


def number(value, name, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError("Invalid audio-thread " + name)
    return value


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("Invalid audio-thread " + name)
    return value


def close(actual, expected, name):
    if not math.isclose(number(actual, name), expected, rel_tol=1e-7, abs_tol=1e-10):
        raise ValueError("Inconsistent audio-thread " + name)


def meter_stream(context, source=None):
    integer(context.get("id"), "context ID", 1)
    meter = context.get("audio_thread")
    if not isinstance(meter, dict) or meter.get("schema") != 1 or type(meter.get("schema")) is not int:
        raise ValueError("Missing actual audio-thread PCM observer")
    if source is not None:
        matches = [item for item in meter.get("streams", []) if item.get("source") == source]
        if len(matches) != 1:
            raise ValueError("Audio source lacks one unambiguous pre-armed bus meter")
        meter = matches[0]
    if (meter.get("source") != source or meter.get("role") != ("mix" if source is None else "bus")
            or not isinstance(meter.get("tap_id"), str) or not meter["tap_id"]
            or meter.get("status") != "ready" or meter.get("overflow") is not False
            or meter.get("errors") != [] or type(meter.get("schema")) is not int or meter["schema"] != 1):
        raise ValueError("Audio-thread PCM observer is incomplete, overflowed or failed")
    rate = integer(meter.get("sample_rate"), "sample rate", 8000)
    if rate > 192000 or rate != context.get("sample_rate"):
        raise ValueError("Audio-thread sample rate differs from the genuine context")
    window_frames = integer(meter.get("window_frames"), "window length", 1)
    if window_frames != round(rate / 10):
        raise ValueError("Audio-thread window is not the declared 100 ms frame count")
    records = []
    windows = meter.get("windows")
    gaps = meter.get("gaps")
    if not isinstance(windows, list) or not isinstance(gaps, list) or len(windows) + len(gaps) > 24000:
        raise ValueError("Unbounded or missing audio-thread records")
    for values in (windows, gaps):
        if any(type(item) is not dict for item in values):
            raise ValueError("Malformed audio-thread record")
        sequences = [integer(item.get("sequence"), "sequence", 1) for item in values]
        if any(right <= left for left, right in zip(sequences, sequences[1:])):
            raise ValueError("Reordered or duplicate audio-thread records")
    for item in windows:
        if not isinstance(item, dict):
            raise ValueError("Malformed audio-thread PCM window")
        start = integer(item.get("start_frame"), "window start")
        end = integer(item.get("end_frame"), "window end", start + 1)
        frames = integer(item.get("frames"), "PCM frames", 1)
        channels = integer(item.get("channels"), "PCM channels", 1)
        samples = integer(item.get("samples"), "PCM samples", 1)
        if (channels > 32 or end - start != frames or samples != frames * channels or frames > window_frames
                or type(item.get("complete")) is not bool or item["complete"] != (frames == window_frames)):
            raise ValueError("Audio-thread PCM frame/channel coverage is inconsistent")
        vectors = [item.get(key) for key in ("channel_samples", "channel_square_sum", "channel_rms", "channel_peak", "channel_clipped_samples")]
        if any(not isinstance(values, list) or len(values) != channels for values in vectors):
            raise ValueError("Audio-thread channel evidence is incomplete")
        counts, squares, rms, peaks, clipped = vectors
        for index in range(channels):
            if integer(counts[index], "channel samples", 1) != frames:
                raise ValueError("An audio channel contains missing frames")
            square = number(squares[index], "channel square sum")
            peak = number(peaks[index], "channel peak")
            close(rms[index], math.sqrt(square / frames), "channel RMS")
            if rms[index] > peak + 1e-8 or integer(clipped[index], "channel clipped samples") > frames:
                raise ValueError("Audio-thread channel statistics are impossible")
        close(item.get("square_sum"), sum(squares), "square sum")
        close(item.get("rms"), math.sqrt(sum(squares) / samples), "RMS")
        close(item.get("peak"), max(peaks), "peak")
        if integer(item.get("clipped_samples"), "clipped samples") != sum(clipped):
            raise ValueError("Audio-thread clipping counts are inconsistent")
        close(item.get("clipped_fraction"), sum(clipped) / samples, "clipping fraction")
        if item["peak"] > 1.01 or item["clipped_fraction"] > .001:
            raise ValueError("Observed audio-thread PCM contains sustained clipping")
        records.append((integer(item.get("sequence"), "sequence", 1), start, end, "pcm", item))
    for item in gaps:
        if not isinstance(item, dict) or item.get("reason") != "no-input":
            raise ValueError("Unknown audio-thread gap")
        start = integer(item.get("start_frame"), "gap start")
        end = integer(item.get("end_frame"), "gap end", start + 1)
        if integer(item.get("frames"), "gap frames", 1) != end - start:
            raise ValueError("Audio-thread gap frame count is inconsistent")
        records.append((integer(item.get("sequence"), "sequence", 1), start, end, "gap", item))
    records.sort(key=lambda item: item[0])
    for index, item in enumerate(records):
        if item[0] != index + 1 or (index and item[1] != records[index - 1][2]):
            raise ValueError("Audio-thread PCM has a dropped, duplicated or discontinuous record")
    clock = number(context.get("context_time"), "context clock")
    if records and records[-1][2] > clock * rate + 256:
        raise ValueError("Audio-thread PCM extends beyond the actual context clock")
    return meter


def pcm_interval(context, begin, end, minimum_seconds, source=None, minimum_windows=5, edge_seconds=.2):
    """Select fully contained complete PCM records; never interpolate/trim PCM."""
    begin = number(begin, "interval start")
    end = number(end, "interval end", begin)
    minimum_seconds = number(minimum_seconds, "minimum duration")
    if end <= begin or minimum_seconds <= 0:
        raise ValueError("Audio-thread interval is empty")
    meter = meter_stream(context, source)
    rate = meter["sample_rate"]
    windows = [item for item in meter["windows"] if item["complete"] and item["start_frame"] >= math.ceil(begin * rate - 1e-6)
               and item["end_frame"] <= math.floor(end * rate + 1e-6)]
    if (len(windows) < minimum_windows or windows[0]["start_frame"] / rate > begin + edge_seconds
            or windows[-1]["end_frame"] / rate < end - edge_seconds
            or sum(item["frames"] for item in windows) / rate + 1e-9 < minimum_seconds
            or any(right["start_frame"] != left["end_frame"] for left, right in zip(windows, windows[1:]))):
        raise ValueError("Audio-thread window lacks sustained contiguous real PCM coverage")
    # A gap can never be repaired with assumed silence or manufactured samples.
    if any(item["start_frame"] < windows[-1]["end_frame"] and item["end_frame"] > windows[0]["start_frame"]
           for item in meter["gaps"]):
        raise ValueError("Audio-thread interval contains missing input PCM")
    return windows


def pcm_signal(windows, audible, minimum_fraction=.8):
    frames = sum(item["frames"] for item in windows)
    if not frames:
        raise ValueError("No original PCM frames were observed")
    if audible:
        if sum(item["frames"] for item in windows if item["rms"] >= AUDIBLE_RMS) < frames * minimum_fraction:
            raise ValueError("Actual audio-thread PCM was silent during the required audible interval")
    elif max(item["rms"] for item in windows) > QUIET_RMS:
        raise ValueError("Expected quiet audio-thread PCM contains signal")
    return {"pcm_windows": len(windows), "pcm_frames": frames,
            "first_frame": windows[0]["start_frame"], "last_frame": windows[-1]["end_frame"],
            "maximum_rms": max(item["rms"] for item in windows),
            "mean_rms": sum(item["rms"] * item["frames"] for item in windows) / frames,
            "audible": audible, "proof": "actual same-context audio-thread PCM with contiguous sample-frame coverage"}


def marked_pcm_window(snapshot, context, begin_ms, end_ms, minimum_seconds, audible):
    if (number(end_ms, "wall interval end") - number(begin_ms, "wall interval start") < minimum_seconds * 1000
            or end_ms != snapshot.get("wall_ms")):
        raise ValueError("Audio-thread interval lacks an independent actual wall-clock boundary")
    marks = [item for item in snapshot.get("marks", []) if item.get("wall_ms") == begin_ms]
    if len(marks) != 1:
        raise ValueError("Audio-thread interval lacks its actual context-clock mark")
    clocks = [item for item in marks[0].get("context_times", []) if item.get("id") == context.get("id")]
    if len(clocks) != 1 or context.get("state") != "running":
        raise ValueError("Audio-thread interval does not retain the running context")
    begin = number(clocks[0].get("time"), "marked context clock")
    cutoff = snapshot.get("pcm_cutoff")
    if not isinstance(cutoff, dict):
        raise ValueError("Audio-thread snapshot lacks its frozen pre-drain cutoff")
    cutoff_wall = number(cutoff.get("wall_ms"), "cutoff wall clock")
    cutoff_clocks = [item for item in cutoff.get("context_times", []) if item.get("id") == context.get("id")]
    if len(cutoff_clocks) != 1 or not begin_ms + minimum_seconds * 1000 <= cutoff_wall <= end_ms:
        raise ValueError("Audio-thread cutoff does not establish independent elapsed wall time")
    end = number(cutoff_clocks[0].get("time"), "frozen cutoff context clock")
    if end > number(context.get("context_time"), "snapshot context clock"):
        raise ValueError("Audio-thread cutoff is ahead of its genuine context")
    barriers = [item for item in snapshot.get("pcm_barriers", []) if item.get("context") == context.get("id")
                and item.get("tap_id") == context.get("audio_thread", {}).get("tap_id")]
    if (len(barriers) != 1 or integer(barriers[0].get("processed_end_frame"), "drain watermark")
            < math.floor(end * context["sample_rate"])):
        raise ValueError("Audio-thread PCM drain did not reach the frozen cutoff")
    if end - begin < minimum_seconds * .9:
        raise ValueError("Actual audio context clock stalled")
    windows = pcm_interval(context, begin, end, minimum_seconds)
    result = pcm_signal(windows, audible)
    result.update({"first_ms": begin_ms, "last_ms": cutoff_wall, "delivery_snapshot_ms": end_ms, "sample_rate": context["sample_rate"],
                   "context_start": begin, "context_end": end, "wall_seconds": (cutoff_wall - begin_ms) / 1000})
    return result
