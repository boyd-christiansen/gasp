"use strict";
const $ = (id) => document.getElementById(id);
const escapeHTML = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let state = {},
  sessions = [],
  decks = [],
  trials = [],
  activeSession = null,
  activeRecord = null,
  busy = false,
  polling = false,
  reviewTrials = [],
  selectedTrial = null;
let offsetMs = 0,
  uncertaintyMs = 0,
  audioActive = false,
  audioStopped = false,
  browserRecorder = null,
  browserAudio = null,
  browserBlob = null,
  browserAudioStart = 0;
const native = !!window.webkit?.messageHandlers?.subvocal,
  replies = new Map();
window.nativeReply = (id, result, error) => {
  const p = replies.get(id);
  if (!p) return;
  clearTimeout(p.timer);
  replies.delete(id);
  error ? p.reject(new Error(error)) : p.resolve(result);
};
function bridge(action, data = {}) {
  if (!native)
    return Promise.reject(
      new Error("Open the installed Mac app for this feature."),
    );
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID();
    const timer = setTimeout(() => {
      replies.delete(id);
      reject(new Error("The Mac app did not respond."));
    }, 60000);
    replies.set(id, { resolve, reject, timer });
    window.webkit.messageHandlers.subvocal.postMessage({ id, action, ...data });
  });
}
async function api(path, method = "GET", body) {
  const response = await fetch("/api/" + path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : JSON.stringify(result.detail),
    );
  return result;
}
function notice(text, error = false) {
  $("notice").hidden = false;
  $("notice").className = error ? "error" : "";
  $("notice").textContent = text;
}
function act(id, fn) {
  $(id).onclick = async (e) => {
    e.preventDefault();
    try {
      await fn();
    } catch (e) {
      notice(e.message, true);
    }
  };
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function page(name) {
  document
    .querySelectorAll(".page")
    .forEach((e) => (e.hidden = e.id !== "page-" + name));
  document
    .querySelectorAll("nav button")
    .forEach((e) => e.classList.toggle("selected", e.dataset.page === name));
  const region = $("page-" + name);
  region.focus({ preventScroll: true });
  window.scrollTo(0, 0);
  $("pageTitle").textContent = {
    collect: "Build your training set.",
    setup: "Make yourself comfortable.",
    review: "Good data starts with review.",
    train: "Train a personal baseline.",
  }[name];
  if (name === "train") loadTraining().catch((e) => notice(e.message, true));
  if (name === "review") loadReview().catch((e) => notice(e.message, true));
}
document
  .querySelectorAll("nav button")
  .forEach((e) => (e.onclick = () => page(e.dataset.page)));
function overlay(status, detail = "") {
  if (native)
    bridge("status", { status, detail, active: !!activeRecord }).catch(
      () => {},
    );
}
function currentStep() {
  return activeSession?.collection?.plan.steps.find(
    (s) =>
      !trials.some(
        (t) =>
          t.plan_step_id === s.step_id &&
          t.accepted &&
          t.review_status === "verified",
      ),
  );
}
function pendingTake() {
  const s = currentStep();
  return (
    s &&
    [...trials]
      .reverse()
      .find(
        (t) => t.plan_step_id === s.step_id && t.review_status === "pending",
      )
  );
}
function renderCollection() {
  const plan = activeSession?.collection?.plan,
    step = currentStep(),
    kept = trials.filter(
      (t) => t.accepted && t.review_status === "verified",
    ).length;
  $("keptCount").textContent = kept;
  $("visitName").textContent = activeSession
    ? activeSession.name
    : "Start a new visit to begin";
  $("deckName").textContent = plan?.deck_name || "YOUR FIRST SESSION";
  $("modeBadge").textContent = step
    ? {
        voiced: "SPEAK ALOUD",
        silent: "MOUTH SILENTLY",
        rest: "REST",
        negative: "MOVEMENT",
      }[step.articulation]
    : plan
      ? "COMPLETE"
      : "SETUP";
  $("modeBadge").className = "mode " + (step?.articulation || "");
  const completed = plan
    ? plan.steps.filter((s) =>
        trials.some(
          (t) =>
            t.plan_step_id === s.step_id &&
            t.accepted &&
            t.review_status === "verified",
        ),
      ).length
    : 0;
  $("progressFill").style.width = plan
    ? (100 * completed) / plan.steps.length + "%"
    : "0%";
  $("stepCount").textContent = plan
    ? `${completed} OF ${plan.steps.length} STEPS VERIFIED`
    : "A SMALL START, A USEFUL DATASET";
  $("promptText").textContent =
    step?.prompt_text ||
    (plan ? "This visit is complete." : "Start with a personal calibration.");
  $("promptInstruction").textContent = step
    ? step.instruction ||
      (step.articulation === "silent"
        ? "Mouth the words naturally, without voicing or whispering."
        : "Speak naturally. You can finish early with the recording key.")
    : plan
      ? "Come back for another visit with the same deck. A new position or a new day makes a stronger test."
      : "We’ll check your position, record a few sounds, and capture everyday movements.";
  if (step?.pair_id)
    $("promptInstruction").textContent +=
      " Paired takes share the text; their timing is independent.";
  if (!activeRecord) {
    $("recordButton").textContent = !plan
      ? "Set up a visit ↗"
      : !step
        ? "Start another visit ↗"
        : pendingTake()
          ? "Review your last take →"
          : "Record this take";
    $("recordButton").className = "primary";
    $("recordButton").disabled = busy;
    $("cancelButton").hidden = true;
    $("recordingState").className = "record-state";
    $("recordingState").textContent = pendingTake()
      ? "Saved · review before moving on"
      : step
        ? `Up to ${step.duration_s} seconds · finish early when you’re done`
        : "Ready when you are";
  }
  const p = pendingTake();
  $("latestTake").hidden = !p;
  if (p) {
    $("latestTake").innerHTML =
      `<div><strong>Your take is saved, awaiting review.</strong><p>${p.frames} radar samples · ${p.duration_s.toFixed(1)} seconds · ${p.articulation}${p.synthetic ? " · SYNTHETIC" : ""}</p></div><button class="quiet" id="reviewLatest">Review take →</button>`;
    $("reviewLatest").onclick = () => openReview(activeSession.id, p.id);
  }
}
async function refreshVisits() {
  sessions = await api("sessions");
  $("visits").innerHTML =
    sessions
      .filter((s) => s.collection)
      .map(
        (s) =>
          `<button class="visit" data-id="${s.id}"><strong>${escapeHTML(s.name)}</strong><small>${s.accepted_count} verified · ${escapeHTML(s.collection.visit_role)}${s.synthetic ? " · SIM" : ""}</small></button>`,
      )
      .join("") ||
    '<p class="small">Your collection visits will appear here.</p>';
  $("visits")
    .querySelectorAll("button")
    .forEach(
      (b) =>
        (b.onclick = () =>
          resume(b.dataset.id).catch((e) => notice(e.message, true))),
    );
  const previous = $("reviewSession").value;
  $("reviewSession").innerHTML = sessions
    .filter((s) => s.collection)
    .map(
      (s) =>
        `<option value="${s.id}">${escapeHTML(s.name)}${s.synthetic ? " · SIM" : ""}</option>`,
    )
    .join("");
  if (sessions.some((s) => s.id === previous))
    $("reviewSession").value = previous;
  else if (activeSession) $("reviewSession").value = activeSession.id;
  $("calibration").innerHTML =
    '<option value="">No reference linked yet</option>' +
    sessions
      .filter(
        (s) =>
          s.collection?.plan?.calibration &&
          s.accepted_count > 0 &&
          s.subject === $("subject").value &&
          s.source === $("source").value,
      )
      .map((s) => `<option value="${s.id}">${escapeHTML(s.name)}</option>`)
      .join("");
  $("reviewBadge").textContent = sessions
    .filter((s) => s.collection)
    .reduce((n, s) => n + (s.pending_count || 0), 0);
}
async function resume(sid) {
  if (busy) throw new Error("Finish the current take first.");
  activeSession = await api("sessions/" + sid);
  trials = await api("sessions/" + sid + "/trials");
  renderCollection();
  page("collect");
  if (state.status === "connected") {
    try {
      await api("sessions/" + sid + "/resume", "POST");
      notice("Resumed this visit. Approved steps are already checked off.");
    } catch (e) {
      notice(e.message + " You can still review saved takes.", true);
    }
  } else
    notice(
      "Visit loaded. Connect its source in Session setup before recording.",
    );
}
act("refreshVisits", refreshVisits);
async function ports() {
  const ps = await api("ports");
  for (const id of ["cliPort", "dataPort"]) {
    const old = $(id).value;
    $(id).innerHTML =
      '<option value="">Choose a port…</option>' +
      ps
        .map(
          (p) =>
            `<option value="${escapeHTML(p.device)}">${escapeHTML(p.device)} · ${escapeHTML(p.interface || p.description)}</option>`,
        )
        .join("");
    $(id).value = old;
  }
  if (!ps.length)
    notice(
      "No radar serial ports found. You can practice with the simulator now.",
    );
}
function sourceChanged() {
  const kind = $("source").value,
    dca = kind === "dca1000";
  $("hardwareFields").hidden = kind === "simulator";
  $("dcaFields").hidden = !dca;
  $("dataPortLabel").hidden = dca;
  $("profile").innerHTML = dca
    ? '<option value="dca-raw">DCA raw ADC · 50 frames/s in bursts</option>'
    : '<option value="usb-phase-20hz">USB phase · 20 Hz</option><option value="usb-phase-10hz">USB phase · 10 Hz</option>';
  $("sourceHelp").textContent =
    kind === "simulator"
      ? "Synthetic waveforms test the app. They cannot train a speech recognizer."
      : dca
        ? "DCA needs the carrier board, radar USB command port, Ethernet, and compatible firmware."
        : "Compatible SDK 3.x OOB AOP firmware is required. Select both observed USB port roles.";
  if (kind !== "simulator") ports().catch((e) => notice(e.message, true));
  refreshVisits().catch(() => {});
}
$("source").onchange = sourceChanged;
act("refreshPorts", ports);
act("connectButton", async () => {
  if (busy) throw new Error("Finish the take first.");
  $("connectButton").disabled = true;
  try {
    await api("connect", "POST", {
      source: $("source").value,
      profile: $("profile").value,
      cli_port: $("cliPort").value || null,
      data_port: $("dataPort").value || null,
      host_ip: $("hostIp").value,
      board_ip: $("boardIp").value,
      confirm_layout: $("confirmLayout").checked,
    });
    notice(
      $("source").value === "simulator"
        ? "Simulator connected. All recordings will be marked synthetic."
        : "Source connected. Validate the signal before collecting speech.",
    );
    await poll();
  } finally {
    $("connectButton").disabled = false;
  }
});
act("disconnectButton", async () => {
  await api("disconnect", "POST");
  await poll();
  notice("Disconnected. All saved takes remain on this Mac.");
});
function deckChanged() {
  const deck = decks.find((d) => d.id === $("deck").value);
  $("deckDescription").textContent = deck.description;
  $("visitRole").value = deck.calibration ? "calibration" : "train";
  $("visitRole").disabled = deck.calibration;
  $("repetitions").disabled = deck.calibration;
}
$("deck").onchange = deckChanged;
$("subject").onchange = () => {
  localStorage.setItem("subvocal.subject", $("subject").value);
  refreshVisits().catch(() => {});
};
$("visitForm").onsubmit = async (e) => {
  e.preventDefault();
  try {
    if (busy) throw new Error("Finish the current take first.");
    activeSession = await api("sessions", "POST", {
      name: $("sessionName").value.trim(),
      subject: $("subject").value.trim(),
      collection: {
        deck_id: $("deck").value,
        mode: $("mode").value,
        repetitions: Number($("repetitions").value),
        visit_role: $("visitRole").value,
        calibration_id: $("calibration").value || null,
        distance_cm: Number($("distance").value),
        position_notes: $("positionNotes").value,
      },
    });
    trials = [];
    renderCollection();
    await refreshVisits();
    page("collect");
    notice("Visit created. Record a take, then verify it before moving on.");
    await poll();
  } catch (e) {
    notice(e.message, true);
  }
};
async function clock() {
  const a = performance.now(),
    r = await api("clock"),
    b = performance.now();
  offsetMs = r.monotonic_ns / 1e6 - (a + b) / 2;
  uncertaintyMs = (b - a) / 2;
}
$("referenceAudio").onchange = async () => {
  try {
    if (busy) throw new Error("Change reference audio between takes.");
    if ($("referenceAudio").checked) {
      if (native) {
        await bridge("audioPermission");
      } else {
        browserAudio = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
      }
      $("audioHelp").textContent =
        "Enabled · audio stays with the take on this Mac. No speech recognition.";
    } else {
      browserAudio?.getTracks().forEach((t) => t.stop());
      browserAudio = null;
      $("audioHelp").textContent = "Reference audio is off.";
    }
  } catch (e) {
    $("referenceAudio").checked = false;
    notice(e.message, true);
  }
};
async function startAudio() {
  audioActive = false;
  audioStopped = false;
  browserBlob = null;
  if (!$("referenceAudio").checked) return;
  if (native) {
    await bridge("audioStart");
  } else {
    if (!browserAudio) throw new Error("Enable reference audio again.");
    const chunks = [];
    browserRecorder = new MediaRecorder(browserAudio);
    browserRecorder.addEventListener("dataavailable", (e) => {
      if (e.data.size) chunks.push(e.data);
    });
    browserBlob = new Promise((resolve) => {
      browserRecorder.onstop = () =>
        resolve(new Blob(chunks, { type: browserRecorder.mimeType }));
    });
    browserAudioStart = (performance.now() + offsetMs) * 1e6;
    browserRecorder.start();
  }
  audioActive = true;
}
async function stopAudio() {
  if (!audioActive || audioStopped) return;
  audioStopped = true;
  if (native) await bridge("audioStop");
  else if (browserRecorder?.state === "recording") browserRecorder.stop();
}
async function discardAudio() {
  if (!audioActive) return;
  try {
    await stopAudio();
    if (native) await bridge("audioDiscard");
  } finally {
    audioActive = false;
  }
}
async function attachAudio(sid, tid) {
  if (!audioActive) return;
  await stopAudio();
  if (native) await bridge("audioAttach", { sid, tid });
  else {
    const blob = await browserBlob;
    const r = await fetch(`/api/sessions/${sid}/trials/${tid}/media`, {
      method: "PUT",
      headers: {
        "Content-Type": blob.type,
        "X-Media-Start-Server-Ns": String(browserAudioStart),
        "X-Clock-Uncertainty-Ms": String(uncertaintyMs),
      },
      body: blob,
    });
    if (!r.ok) throw new Error("Reference audio could not be attached.");
  }
  audioActive = false;
}
async function toggleRecording() {
  if (activeRecord) {
    const r = await api("record/" + activeRecord.id);
    if (r.status === "recording")
      await api("record/" + activeRecord.id + "/stop", "POST");
    return;
  }
  if (busy) return;
  if (!activeSession?.collection || !currentStep()) {
    page("setup");
    return;
  }
  if (pendingTake()) {
    await openReview(activeSession.id, pendingTake().id);
    return;
  }
  busy = true;
  renderCollection();
  let rid;
  try {
    await api("sessions/" + activeSession.id + "/resume", "POST");
    await clock();
    await startAudio();
    const rec = await api("collect", "POST", {
      step_id: currentStep().step_id,
      reference_expected: $("referenceAudio").checked,
    });
    activeRecord = rec;
    rid = rec.id;
    let cued = false;
    $("cancelButton").hidden = false;
    while (true) {
      const r = await api("record/" + rid);
      if (r.status === "recording" && !cued) {
        cued = true;
        api("record/" + rid + "/events", "POST", {
          name: "cue_shown",
          estimated_server_ns: Math.round((performance.now() + offsetMs) * 1e6),
          uncertainty_ms: uncertaintyMs,
        }).catch(() => {});
        if (native) await bridge("cue");
        else {
          try {
            const a = new AudioContext(),
              o = a.createOscillator(),
              g = a.createGain();
            o.connect(g);
            g.connect(a.destination);
            g.gain.value = 0.06;
            o.frequency.value = 660;
            o.start();
            o.stop(a.currentTime + 0.09);
            o.onended = () => a.close();
          } catch {}
        }
      }
      const status =
        r.status === "arming"
          ? "Arming sensor…"
          : r.status === "recording"
            ? "Recording · finish when you’re done"
            : r.status === "processing"
              ? "Saving radar data…"
              : r.status === "cancelling"
                ? "Cancelling…"
                : r.status;
      $("recordingState").textContent = status;
      $("recordingState").className =
        "record-state " + (r.status === "recording" ? "recording" : "");
      $("recordButton").textContent =
        r.status === "recording" ? "Finish take ■" : status;
      $("recordButton").disabled = r.status !== "recording";
      $("recordButton").className =
        "primary " + (r.status === "recording" ? "recording" : "");
      overlay(status, currentStep()?.prompt_text || "");
      $("cancelButton").disabled =
        r.status === "processing" || r.status === "cancelling";
      if (r.status === "processing") await stopAudio();
      if (["complete", "failed", "cancelled"].includes(r.status)) {
        await stopAudio();
        if (r.status === "complete") {
          try {
            await attachAudio(r.session_id, r.trial.id);
          } catch (e) {
            notice("Radar saved. Reference audio failed: " + e.message, true);
            await discardAudio();
          }
          trials = await api("sessions/" + activeSession.id + "/trials");
          await refreshVisits();
          overlay("Saved · review take", r.trial.prompt_text);
          notice(
            "Take saved locally. Confirm the actual text before adding it to training.",
          );
        } else {
          await discardAudio();
          if (r.status === "failed")
            throw new Error(r.error || "Capture failed.");
          notice("Take cancelled. It will not be used for training.");
        }
        break;
      }
      await sleep(120);
    }
  } catch (e) {
    if (rid) {
      try {
        await api("record/" + rid + "/cancel", "POST");
      } catch {}
    }
    await discardAudio();
    notice(e.message, true);
    overlay("Capture needs attention", e.message);
  } finally {
    activeRecord = null;
    busy = false;
    renderCollection();
  }
}
act("recordButton", toggleRecording);
act("cancelButton", async () => {
  if (activeRecord) await api("record/" + activeRecord.id + "/cancel", "POST");
});
window.addEventListener("subvocal-toggle", () =>
  toggleRecording().catch((e) => notice(e.message, true)),
);
window.addEventListener("subvocal-cancel", () => {
  if (activeRecord)
    api("record/" + activeRecord.id + "/cancel", "POST").catch((e) =>
      notice(e.message, true),
    );
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && activeRecord && !native)
    api("record/" + activeRecord.id + "/cancel", "POST").catch(() => {});
});
act("enableShortcut", async () => {
  const r = await bridge("enableShortcut", {
    keyCode: Number($("hotkey").value),
  });
  $("hotkeyHelp").textContent = r.message;
  $("shortcutHint").textContent = r.enabled
    ? `Double-tap ${$("hotkey").selectedOptions[0].text} to record · press again to finish`
    : "Enable the recording shortcut in Session setup";
});
$("hotkey").onchange = () => {
  if (native)
    bridge("setShortcut", { keyCode: Number($("hotkey").value) }).catch((e) =>
      notice(e.message, true),
    );
};
async function loadReview(tid) {
  const sid = $("reviewSession").value;
  if (!sid) {
    $("takeList").innerHTML = '<p class="empty">No collection takes yet.</p>';
    return;
  }
  reviewTrials = await api("sessions/" + sid + "/trials");
  $("takeList").innerHTML =
    [...reviewTrials]
      .reverse()
      .map(
        (t) =>
          `<button class="take-item" data-id="${t.id}"><strong>${escapeHTML(t.prompt_text || t.label)}</strong><small>${escapeHTML(t.articulation)} · ${escapeHTML(t.review_status || "legacy")} · ${t.duration_s.toFixed(1)}s${t.synthetic ? " · SIM" : ""}</small></button>`,
      )
      .join("") || '<p class="empty">Record your first take.</p>';
  $("takeList")
    .querySelectorAll("button")
    .forEach(
      (b) =>
        (b.onclick = () =>
          showTake(b.dataset.id).catch((e) => notice(e.message, true))),
    );
  const selected =
    tid ||
    reviewTrials.find((t) => t.review_status === "pending")?.id ||
    reviewTrials.at(-1)?.id;
  if (selected) await showTake(selected);
  else
    $("reviewDetail").innerHTML =
      '<p class="empty">No takes in this visit yet.</p>';
}
async function openReview(sid, tid) {
  $("reviewSession").value = sid;
  page("review");
  await loadReview(tid);
}
$("reviewSession").onchange = () =>
  loadReview().catch((e) => notice(e.message, true));
async function showTake(tid) {
  const t = reviewTrials.find((t) => t.id === tid);
  if (!t) return;
  selectedTrial = t;
  $("takeList")
    .querySelectorAll("button")
    .forEach((b) => b.classList.toggle("active", b.dataset.id === tid));
  const sid = $("reviewSession").value;
  const negative = ["rest", "negative"].includes(t.articulation);
  const loss = t.adc_quality
    ? t.adc_quality.dropped_frames / Math.max(1, t.adc_quality.complete_frames)
    : t.frame_gaps / Math.max(1, t.frames);
  $("reviewDetail").innerHTML =
    `<span class="eyebrow">ORIGINAL PROMPT · ${escapeHTML(t.articulation).toUpperCase()}</span><h2>${escapeHTML(t.prompt_text || t.label)}</h2><div class="metadata">${t.frames} radar samples · ${t.duration_s.toFixed(2)} seconds · ${(loss * 100).toFixed(1)}% missing frames${t.synthetic ? " · SYNTHETIC — software practice only" : ""}</div>${loss > 0.05 ? '<p class="warning">High frame loss. Retake this sample; training will exclude it.</p>' : ""}${t.media ? `<audio controls preload="metadata" src="/api/sessions/${sid}/trials/${tid}/media"></audio><p class="small">${escapeHTML(t.media.synchronization)}</p>` : `<p class="small">${t.reference_expected ? "Reference audio was requested but is missing." : "No reference audio was recorded."}</p>`}<canvas id="reviewSignal" height="100" aria-label="Saved radar phase signal" style="width:100%;height:100px;margin:15px 0"></canvas><label>${negative ? "Confirmed movement / rest label" : "What did you actually say or silently mouth?"}<textarea id="confirmedText" rows="3" maxlength="200" placeholder="Confirm the script or enter the actual words">${escapeHTML(t.confirmed_text || "")}</textarea></label><button class="quiet" id="useScript">${negative ? "Use the movement label" : "I followed the script exactly"}</button><p class="small">Keep repetitions and fillers. Don’t rewrite or polish. For silent takes, confirm your intended words; reject the take if you lost your place.</p><details><summary class="small">Optional utterance boundaries</summary><p class="small">Seconds from the first saved radar sample. These are manual trim points, not word alignment.</p><div class="two"><label>Start (s)<input id="trimStart" type="number" step=".01" min="0" value="${t.utterance_start_s || 0}"></label><label>End (s)<input id="trimEnd" type="number" step=".01" max="${t.duration_s}" value="${t.utterance_end_s || t.duration_s}"></label></div></details><label>Take notes<textarea id="reviewNotes" rows="2" maxlength="4000">${escapeHTML(t.notes || "")}</textarea></label><div class="button-row"><button class="primary" id="keepTake">Verify & keep →</button><button class="quiet" id="rejectTake">Reject take</button></div><p class="small">Status: ${escapeHTML(t.review_status)} · Raw radar and original prompt are preserved.</p>`;
  $("useScript").onclick = () =>
    ($("confirmedText").value = t.target_text || t.prompt_text || t.label);
  act("keepTake", () => saveReview(true));
  act("rejectTake", () => saveReview(false));
  const signal = await api(`sessions/${sid}/trials/${tid}/signal`);
  plot("reviewSignal", signal.phase);
}
async function saveReview(accepted) {
  const sid = $("reviewSession").value,
    t = selectedTrial;
  await api(`sessions/${sid}/trials/${t.id}`, "PATCH", {
    accepted,
    confirmed_text: $("confirmedText").value.trim(),
    notes: $("reviewNotes").value,
    utterance_start_s: Number($("trimStart").value),
    utterance_end_s: Number($("trimEnd").value),
  });
  await refreshVisits();
  if (activeSession?.id === sid) {
    trials = await api(`sessions/${sid}/trials`);
    renderCollection();
  }
  await loadReview(t.id);
  notice(
    accepted
      ? "Verified and kept. This take is eligible for training."
      : "Take rejected. You can record this step again.",
  );
  if (activeSession?.id === sid) {
    page("collect");
    overlay(accepted ? "Ready for next take" : "Ready to retake");
  }
}
function plot(id, values = []) {
  const c = $(id);
  if (!c) return;
  const rect = c.getBoundingClientRect();
  if (!rect.width) return;
  const ratio = devicePixelRatio || 1,
    w = rect.width,
    h = rect.height;
  c.width = w * ratio;
  c.height = h * ratio;
  const x = c.getContext("2d");
  x.scale(ratio, ratio);
  x.strokeStyle = "#dce4d5";
  x.lineWidth = 0.7;
  for (let i = 1; i < 4; i++) {
    x.beginPath();
    x.moveTo(0, (i * h) / 4);
    x.lineTo(w, (i * h) / 4);
    x.stroke();
  }
  if (values.length < 2) return;
  const lo = Math.min(...values),
    span = Math.max(0.01, Math.max(...values) - lo);
  x.beginPath();
  values.forEach((v, i) => {
    const a = (i / (values.length - 1)) * w,
      b = h - 9 - ((v - lo) / span) * (h - 18);
    i ? x.lineTo(a, b) : x.moveTo(a, b);
  });
  x.strokeStyle = "#71936b";
  x.lineWidth = 1.5;
  x.stroke();
}
async function poll() {
  if (polling) return;
  polling = true;
  try {
    state = await api("live");
    const on = state.status === "connected";
    $("connectionStatus").textContent = state.synthetic
      ? "◉ Simulator · synthetic"
      : on
        ? "● Radar connected"
        : state.status === "error"
          ? "○ Source needs attention"
          : "○ Not connected";
    $("connectionStatus").className =
      "status " + (state.synthetic ? "synthetic" : on ? "on" : "");
    $("signalKind").textContent =
      state.source === "dca1000"
        ? "DCA · AFTER TAKE"
        : on
          ? "PHASE"
          : "OFFLINE";
    plot("signal", state.phase || []);
    $("signalFrames").textContent = state.frames + " frames";
    $("signalLoss").textContent = state.frame_gaps + " missing";
    $("signalNote").textContent =
      state.error ||
      (state.source === "dca1000"
        ? "DCA previews update after a completed take."
        : state.synthetic
          ? "Synthetic movement · does not represent speech."
          : state.complex_available
            ? `${state.measured_hz.toFixed(1)} samples/s · signal presence does not establish speech quality.`
            : "Connect a source in Session setup.");
    if (!activeRecord)
      overlay(
        on ? "Ready to collect" : "Connect a source",
        state.synthetic
          ? "Simulator · synthetic"
          : activeSession?.name || "Session setup",
      );
  } catch (e) {
    notice("Capture service unavailable: " + e.message, true);
  } finally {
    polling = false;
  }
}
async function init() {
  const h = await api("health");
  decks = await api("decks");
  $("deck").innerHTML = decks
    .map((d) => `<option value="${d.id}">${escapeHTML(d.name)}</option>`)
    .join("");
  deckChanged();
  $("subject").value = localStorage.getItem("subvocal.subject") || "Boyd";
  $("sessionName").value =
    "Visit · " +
    new Date().toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  await refreshVisits();
  await poll();
  if (state.session?.collection) {
    activeSession = state.session;
    trials = await api("sessions/" + activeSession.id + "/trials");
  }
  renderCollection();
  if (!native) {
    $("enableShortcut").disabled = true;
    $("hotkeyHelp").textContent =
      "Open the installed Mac app for the system-wide shortcut. On-screen capture works here.";
  } else {
    const r = await bridge("info");
    $("hotkey").value = String(r.keyCode);
    $("hotkeyHelp").textContent = r.shortcutMessage;
    $("shortcutHint").textContent = r.shortcutEnabled
      ? `Double-tap ${$("hotkey").selectedOptions[0].text} to record · press again to finish`
      : "Enable the recording shortcut in Session setup";
  }
  $("pageTitle").title = h.data_root;
  setInterval(poll, 700);
}
init().catch((e) => notice(e.message, true));

async function loadTraining() {
  await refreshVisits();
  $("trainVisits").innerHTML =
    sessions
      .filter((s) => s.collection && !s.collection.plan.calibration)
      .map(
        (s) =>
          `<label>${escapeHTML(s.name)} · ${s.accepted_count} verified${s.synthetic ? " · SIM" : ""}<select data-train-id="${s.id}"><option value="">Exclude visit</option>${!["validation", "test"].includes(s.collection.visit_role) ? '<option value="fit">Use for fitting</option>' : ""}${s.collection.visit_role !== "calibration" ? '<option value="test">Hold out for evaluation</option>' : ""}</select></label>`,
      )
      .join("") ||
    '<p class="small">Collect and verify your first visits to begin.</p>';
  await loadReports();
}
async function loadReports() {
  const reports = await api("models");
  $("modelReports").innerHTML =
    reports
      .map(
        (r) =>
          `<div class="report"><h3>${escapeHTML(r.articulation || "legacy")} phrase baseline${r.synthetic ? " · SYNTHETIC" : ""}</h3><p class="small">${r.train_examples} fitting / ${r.test_examples} held-out examples<br>${r.labels.length} labels · ${(r.accuracy * 100).toFixed(1)}% accuracy · ${(r.majority_baseline * 100).toFixed(1)}% majority baseline<br>Macro F1 ${r.macro_f1.toFixed(3)} · ${escapeHTML(r.source)}</p><p class="small">${r.synthetic ? "Synthetic metrics verify software only. They provide no speech-recognition evidence." : "Closed-set phrase evaluation only. Accuracy does not establish general dictation or idle false-activation performance."}</p><div class="metadata">${escapeHTML(r.id)}</div></div>`,
      )
      .join(
        '<hr style="border:0;border-top:1px solid #e2e7df;margin:24px 0">',
      ) || '<p class="empty">Your training reports will appear here.</p>';
}
act("trainButton", async () => {
  const selections = [...document.querySelectorAll("[data-train-id]")];
  const selected = selections.filter((e) => e.value);
  const held = selected
    .filter((e) => e.value === "test")
    .map((e) => e.dataset.trainId);
  if (selected.length < 2 || !held.length || held.length === selected.length)
    throw new Error(
      "Choose at least one fitting visit and one whole held-out visit.",
    );
  $("trainButton").disabled = true;
  try {
    const job = await api("train", "POST", {
      session_ids: selected.map((e) => e.dataset.trainId),
      test_session_ids: held,
      articulation: $("trainMode").value,
      range_min_m: Number($("rangeMin").value),
      range_max_m: Number($("rangeMax").value),
    });
    while (true) {
      const r = await api("jobs/" + job.id);
      $("trainState").textContent =
        r.status === "failed"
          ? r.error
          : r.status === "complete"
            ? "Complete · report saved locally."
            : "Training the local baseline…";
      if (r.status === "failed") throw new Error(r.error);
      if (r.status === "complete") {
        await loadReports();
        break;
      }
      await sleep(400);
    }
  } finally {
    $("trainButton").disabled = false;
  }
});
