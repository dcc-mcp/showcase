/* Observation-only full-clip acceptance. This file is never shipped as a player.
 * No play(), pause(), seek assignment, event substitution or policy override.
 * It also exports the exact pixel/receipt guards to browser-free Node tests. */
(function (root) {
  "use strict";
  const LIMITS = Object.freeze({mean: 6, p95: 22, nearestSlack: 1.5,
    minimumCallbacks: 108, maximumFrameGap: 6, minimumChanges: 48});
  // Coordinates are in the 160 x 120 reference, enclosing the rod and bob.
  // Static floor/background cannot dilute the moving-object error.
  const ROI = Object.freeze({x: 43, y: 27, width: 65, height: 52});

  function motionMask(frames, width, height) {
    if (frames.length !== 144 || width !== 160 || height !== 120 ||
        frames.some(frame => frame.length !== width * height * 4)) {
      throw new Error("Missing or malformed complete reference sequence");
    }
    const mask = [];
    for (let y = ROI.y; y < ROI.y + ROI.height; y++) {
      for (let x = ROI.x; x < ROI.x + ROI.width; x++) {
        const offset = (y * width + x) * 4;
        let changing = false;
        for (let channel = 0; channel < 3; channel++) {
          let low = 255, high = 0;
          for (const frame of frames) {
            low = Math.min(low, frame[offset + channel]);
            high = Math.max(high, frame[offset + channel]);
          }
          changing ||= high - low >= 24;
        }
        if (changing) mask.push(offset);
      }
    }
    if (mask.length < 100) throw new Error("Reference sequence has insufficient visible motion");
    return mask;
  }

  function difference(actual, expected, mask) {
    if (!actual || !expected || actual.length !== expected.length || !mask.length) {
      throw new Error("Missing pixels or motion mask");
    }
    let sum = 0, maximum = 0;
    const histogram = new Uint32Array(256);
    for (const offset of mask) for (let channel = 0; channel < 3; channel++) {
      const error = Math.abs(actual[offset + channel] - expected[offset + channel]);
      sum += error;
      maximum = Math.max(maximum, error);
      histogram[error]++;
    }
    const count = mask.length * 3;
    let accumulated = 0, p95 = 0;
    for (; p95 < 255; p95++) {
      accumulated += histogram[p95];
      if (accumulated >= Math.ceil(count * 0.95)) break;
    }
    return {mean: sum / count, p95, maximum};
  }

  function compare(actual, expectedIndex, references, mask) {
    const target = difference(actual, references[expectedIndex], mask);
    let nearestIndex = -1, nearestMean = Infinity;
    references.forEach((reference, index) => {
      const mean = difference(actual, reference, mask).mean;
      if (mean < nearestMean) { nearestMean = mean; nearestIndex = index; }
    });
    return {frame: expectedIndex + 1, ...target, nearestFrame: nearestIndex + 1, nearestMean,
      passed: target.mean <= LIMITS.mean && target.p95 <= LIMITS.p95 &&
        target.mean <= nearestMean + LIMITS.nearestSlack};
  }

  function validateKeyframeRecords(records) {
    if (!Array.isArray(records) || records.length !== 3 ||
        new Set(records.map(record => record?.frame)).size !== 3 ||
        records.some(record => ![1, 73, 144].includes(record?.frame))) {
      throw new Error("Missing, duplicate or invalid PNG keyframe numbers");
    }
  }

  function compareKeyframe(actual, frame, keyframes, mask) {
    const numbers = [1, 73, 144];
    if (!numbers.includes(frame)) throw new Error("Invalid PNG keyframe number");
    // Keep the absolute and nearest limits within this same-encoding PNG set.
    // Never mix its error baseline into the all-JPEG sequence's search.
    const result = compare(actual, numbers.indexOf(frame), numbers.map(number => keyframes[number]), mask);
    return {...result, frame, nearestFrame: numbers[result.nearestFrame - 1]};
  }

  function validate(receipt) {
    const errors = [...(receipt.errors || [])];
    if (!receipt.done || receipt.ended !== 1) errors.push("Natural playback did not reach ended exactly once");
    if (receipt.playEvents !== 1 || receipt.seeks !== 0 || receipt.rates.some(rate => rate !== 1)) {
      errors.push("Playback was interrupted, sought, repeated or retimed");
    }
    if (receipt.duration !== 6.006 || receipt.width !== 960 || receipt.height !== 720) {
      errors.push("Unexpected decoded format");
    }
    if (!(receipt.elapsedMs >= 5756 && receipt.elapsedMs <= 25000)) errors.push("Not complete natural-speed playback");
    if (!receipt.start?.passed || !receipt.end?.passed) errors.push("First or final decoded picture mismatch");
    if (!receipt.displayedEnd?.passed) errors.push("Final displayed screenshot mismatch");
    if ((receipt.keyframeSamples || []).some(sample => !sample.passed)) {
      errors.push("Independently observed PNG keyframe mismatch");
    }
    const samples = receipt.samples || [];
    if (samples.length < LIMITS.minimumCallbacks || samples.some(sample => !sample.passed)) {
      errors.push("Insufficient or mismatching presented pictures");
    }
    if (!samples.length || samples[0].frame > 2 || samples.at(-1).frame !== 144) {
      errors.push("Presented pictures do not cover the beginning and final frame");
    }
    for (let i = 1; i < samples.length; i++) {
      const gap = samples[i].frame - samples[i - 1].frame;
      if (gap <= 0 || gap > LIMITS.maximumFrameGap ||
          samples[i].presentedFrames <= samples[i - 1].presentedFrames ||
          samples[i].mediaTime <= samples[i - 1].mediaTime) {
        errors.push("Decoded/presented frame progression stalled or skipped too far");
        break;
      }
    }
    if (!(receipt.visibleChanges >= LIMITS.minimumChanges)) errors.push("Pictures are frozen or have insufficient motion");
    if (!(receipt.quality?.totalVideoFrames >= 144) || receipt.quality?.corruptedVideoFrames > 0) {
      errors.push("Incomplete or corrupted browser decode");
    }
    return {passed: errors.length === 0, errors};
  }

  async function install(video, spec) {
    if (typeof video.requestVideoFrameCallback !== "function" ||
        typeof video.getVideoPlaybackQuality !== "function") throw new Error("Required decoded-frame APIs unavailable");
    validateKeyframeRecords(spec.keyframes);
    const canvas = document.createElement("canvas");
    canvas.width = 160; canvas.height = 120;
    const context = canvas.getContext("2d", {willReadFrequently: true});
    if (!context) throw new Error("Canvas is unavailable");
    context.imageSmoothingQuality = "high";
    const load = async url => {
      const image = new Image();
      image.src = url;
      await image.decode();
      if (!image.naturalWidth || !image.naturalHeight) throw new Error("Reference image did not decode");
      return image;
    };
    const atlas = await load(spec.atlas.url);
    if (atlas.naturalWidth !== 1280 || atlas.naturalHeight !== 2160) throw new Error("Unexpected atlas dimensions");
    const atlasReferences = [];
    for (let index = 0; index < 144; index++) {
      context.drawImage(atlas, (index % 8) * 160, Math.floor(index / 8) * 120, 160, 120, 0, 0, 160, 120);
      atlasReferences.push(context.getImageData(0, 0, 160, 120).data);
    }
    const keyframes = {};
    for (const reference of spec.keyframes) {
      const image = await load(reference.url);
      if (image.naturalWidth !== 960 || image.naturalHeight !== 720) throw new Error("Unexpected keyframe dimensions");
      context.drawImage(image, 0, 0, 160, 120);
      keyframes[reference.frame] = context.getImageData(0, 0, 160, 120).data;
    }
    const mask = motionMask(atlasReferences, 160, 120);
    const receipt = {done: false, errors: [], samples: [], keyframeSamples: [], rates: [video.playbackRate],
      playEvents: 0, seeks: 0, ended: 0, visibleChanges: 0, motionMaskPixels: mask.length,
      motionRoi: ROI, pixelLimits: LIMITS, referenceBasis: spec.reference_basis,
      comparisonResolution: [160, 120], fullKeyframeResolution: [960, 720],
      sequenceReference: "All 144 same-encoding JPEG atlas tiles; no PNG substitutions",
      keyframeReference: "Separate unprofiled PNG set with absolute and same-set nearest limits; frame73 checked when naturally observed",
      middleKeyframe: {frame: 73, status: "not_observed"}};
    const pictures = {};
    let lastPixels, playStarted, callback;
    const snapshot = (stage, metadata) => ({stage, readyState: video.readyState, networkState: video.networkState,
      width: video.videoWidth, height: video.videoHeight, currentTime: video.currentTime,
      paused: video.paused, ended: video.ended, seeking: video.seeking,
      sourceName: (video.currentSrc || "").split(/[?#]/)[0].split("/").pop(),
      mediaErrorCode: video.error?.code || null,
      ...(metadata ? {callback: {mediaTime: metadata.mediaTime, presentedFrames: metadata.presentedFrames,
        width: metadata.width, height: metadata.height, expectedDisplayTime: metadata.expectedDisplayTime}} : {})});
    receipt.observations = {installed: snapshot("installed")};
    const fail = (error, stage, metadata) => {
      receipt.observations.failure = snapshot(stage, metadata);
      receipt.errors.push(String(error?.message || error)); receipt.done = true;
    };
    const pixels = () => {
      if (video.readyState < 2 || video.videoWidth !== 960 || video.videoHeight !== 720) {
        throw new Error("Video has no correctly sized decoded picture");
      }
      context.drawImage(video, 0, 0, 160, 120);
      return context.getImageData(0, 0, 160, 120).data; // CORS/security errors fail closed.
    };
    const fullPicture = name => {
      const full = document.createElement("canvas");
      full.width = video.videoWidth; full.height = video.videoHeight;
      full.getContext("2d").drawImage(video, 0, 0);
      pictures[name] = full.toDataURL("image/png");
    };
    video.addEventListener("play", () => { receipt.playEvents++; playStarted ??= performance.now(); });
    video.addEventListener("seeking", () => receipt.seeks++);
    video.addEventListener("ratechange", () => receipt.rates.push(video.playbackRate));
    video.addEventListener("error", () => fail("Media decode/network error " + video.error?.code, "media-error"));
    video.addEventListener("loadeddata", () => {
      if (receipt.done) return;
      receipt.observations.loadeddata = snapshot("loadeddata");
      try {
        if (video.currentTime > 1001 / 24000 / 2) throw new Error("Initial actual frame was not observed");
        receipt.start = compareKeyframe(pixels(), 1, keyframes, mask);
        if (!receipt.start.passed) throw new Error("Initial decoded picture mismatch");
        fullPicture("first-decoded");
        // Arm only after this actual first picture is available and verified.
        // Compositor callbacks are not a loadeddata/readyState barrier. The
        // unchanged coverage gate still requires the first presented frame <=2.
        callback = video.requestVideoFrameCallback(observe);
      } catch (error) { fail(error, "loadeddata"); }
    }, {once: true});
    const observe = (_now, metadata) => {
      if (receipt.done) return;
      receipt.observations.firstCallback ??= snapshot("rVFC", metadata);
      try {
        const index = Math.round(metadata.mediaTime * 24000 / 1001);
        if (index < 0 || index >= 144) throw new Error("Presented frame timestamp out of range");
        const actual = pixels();
        if (lastPixels && difference(actual, lastPixels, mask).mean > 0.35) receipt.visibleChanges++;
        lastPixels = actual;
        receipt.samples.push({...compare(actual, index, atlasReferences, mask), mediaTime: metadata.mediaTime,
          presentedFrames: metadata.presentedFrames, expectedDisplayTime: metadata.expectedDisplayTime});
        if (keyframes[index + 1]) {
          const checked = {...compareKeyframe(actual, index + 1, keyframes, mask), mediaTime: metadata.mediaTime};
          receipt.keyframeSamples.push(checked);
          if (index === 72) {
            receipt.middleKeyframe = {...checked, status: checked.passed ? "pass" : "fail"};
            fullPicture("middle-decoded");
          }
        }
        receipt.rates.push(video.playbackRate);
        callback = video.requestVideoFrameCallback(observe);
      } catch (error) { fail(error, "rVFC", metadata); }
    };
    video.addEventListener("ended", () => {
      if (receipt.done) return;
      receipt.observations.ended = snapshot("ended");
      try {
        receipt.ended++;
        receipt.elapsedMs = performance.now() - playStarted;
        receipt.duration = Math.round(video.duration * 1000000) / 1000000;
        receipt.width = video.videoWidth; receipt.height = video.videoHeight;
        receipt.end = compareKeyframe(pixels(), 144, keyframes, mask);
        fullPicture("last-decoded");
        const quality = video.getVideoPlaybackQuality();
        receipt.quality = {totalVideoFrames: quality.totalVideoFrames, droppedVideoFrames: quality.droppedVideoFrames,
          corruptedVideoFrames: quality.corruptedVideoFrames};
        receipt.done = true;
        if (callback !== undefined) video.cancelVideoFrameCallback(callback);
      } catch (error) { fail(error, "ended"); }
    }, {once: true});
    window.__pendulumPlayback = {receipt, pictures,
      async compareDisplayedEnd(dataUrl) {
        const image = await load(dataUrl);
        // The production player uses object-fit: contain in a 16:9 element.
        // Strip only the symmetric letterbox, leaving the visible image itself.
        const scale = Math.min(image.naturalWidth / 960, image.naturalHeight / 720);
        const width = 960 * scale, height = 720 * scale;
        context.drawImage(image, (image.naturalWidth - width) / 2, (image.naturalHeight - height) / 2,
          width, height, 0, 0, 160, 120);
        receipt.displayedEnd = compareKeyframe(context.getImageData(0, 0, 160, 120).data, 144, keyframes, mask);
        return receipt.displayedEnd;
      }};
  }
  const api = {LIMITS, ROI, motionMask, difference, compare, compareKeyframe, validateKeyframeRecords, validate, install};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PendulumPlayback = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
